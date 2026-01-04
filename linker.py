from dataclasses import dataclass
import elftools.elf.elffile
from typing import Any
from os.path import join
from os import makedirs
from keystone import *
from struct import pack

@dataclass
class Environment:
    org: int = 0
    result: str = ""
    outdir: str = "output"
    avail_url_base: str = ''
    supress_js: bool = False

@dataclass
class Output:
    address: int
    data: list

@dataclass
class RawData:
    base: int
    linkedmem: list[int]

@dataclass
class SOExternalLinkage:
    sofile: Any = None
    undefs: dict[str, list[int]] = None
    undef_assignments: dict[str, int] = None
    base: int = 0
    base_offset: int = 0
    got: int = 0
    linkedmem: list[int] = None
    name: str = ''

    def endhook(self):
        for undef, lst in self.undefs.items():
            if undef in self.undef_assignments:
                for entry in lst:
                    print(f"Rewrite in {self.name} addr {entry:#x}")
                    self.linkedmem[entry:entry + 4] = self.undef_assignments[undef].to_bytes(4, 'little')
            else:
                print(f"Warning: Symbol {undef} marked by {self.name} as undefined hasn't been defined by the script!")

    def symbol(self, name):
        for section_number in range(self.sofile.header.e_shnum):
            try:
                return self.sofile.get_section(section_number).get_symbol_by_name(name)[0].entry.st_value + self.base_offset + self.base
            except:
                pass
        raise BaseException(f"No symbol {name} in {self.name}")
environment = Environment()
_finishhooks = []
_synthesis_sections = []
_exposed = []
_entry_section = None
_entry_section_bridging_address = None
_postconstruct = ""

def entry_section():
    global _entry_section
    global _entry_section_bridging_address
    if _entry_section is None:
        _entry_section = RawData(environment.org, [])
        _entry_section_bridging_address = environment.org
        _entry_section.linkedmem += list(pack("<I", _entry_section_bridging_address + 8)) + [0] * 4
        _entry_section.linkedmem += _assemble(
            "HLT"
        )
        _synthesis_sections.append(_entry_section)
    else: raise BaseException("Already created!")

def postconstruct(data: str):
    global _postconstruct
    _postconstruct += data + '\n'

def expose(data: str):
    _exposed.append(data)

def jsentry(name: str, parent, symbol, **kwargs):
    address = parent.symbol(symbol)
    got = parent.got
    jsinvoc(name, 
    f"""

    PUSH {address}
    POP EAX
    PUSH {got}
    POP EBX
    CALL EAX
    HLT

    """, **kwargs)

def _assemble(code: str):
    ks = Ks(KS_ARCH_X86, KS_MODE_32)
    encoding, count = ks.asm(code)
    print(f"Assembled: \n{code} \nInto: {encoding}")
    return list(encoding)

def jsinvoc(name: str, code: str, args='', prologue='', epilogue='return this.emulator.v86.cpu.reg32.valueOf()[0];'):
    global _entry_section
    encoding = _assemble(code)
    startaddr = _entry_section.base + len(_entry_section.linkedmem)
    _entry_section.linkedmem += encoding
    expose(
f"""
    async {name}({args}){{
        {prologue}
        this.emulator.v86.cpu.mem32s[{hex(_entry_section_bridging_address // 4)}] = {hex(startaddr)};
        this.emulator.v86.cpu.reset_cpu();
        await this._cpuStop();
        {epilogue}
    }}
"""
    )

def linkallundef(so1: SOExternalLinkage, so2: SOExternalLinkage):
    count = 0
    for undef_name in so1.undefs.keys():
        try:
            so1.undef_assignments[undef_name] = so2.symbol(undef_name)
            count += 1
        except BaseException as e:
            print(e)
    print(f"Bound {count} undefined symbols in {so1.name} to {so2.name}")

def linkundef(so1: SOExternalLinkage, name1: str, so2: SOExternalLinkage, name2: str = None):
    if name2 is None:
        name2 = name1
    if name1 not in so1.undefs:
        print(f"No such undefined {name1} in {so1.name}!")
        return
    so1.undef_assignments[name1] = so2.symbol(name2)

def finish():
    for hook in _finishhooks:
        hook()
    # Synthesize all sections and write outputs
    makedirs(environment.outdir, exist_ok=True)
    loaded = []
    system_memory = b'CalderalinkerMemoryImage'
    print('==== Synthesis ====')
    sorted_sections = sorted(_synthesis_sections, key=lambda e: e.base)
    for i, section in enumerate(sorted_sections):
        if all(x == 0 for x in section.linkedmem):
            # Zero-fill
            system_memory += pack('<BII', 0, section.base, len(section.linkedmem))
        else:
            system_memory += pack('<BII', 1, section.base, len(section.linkedmem)) + bytes(section.linkedmem)
        print(f"Section at {section.base:x}")
    with open(join(environment.outdir, 'system.cmi'), 'wb') as e:
        e.write(system_memory)

    output_js = f"""


function parseImage(data) {{
    const dv = new DataView(data.buffer);
    const image = [];
    let cursor = 24;
    while(cursor < dv.byteLength) {{
        const blockType = dv.getUint8(cursor++);
        const start = dv.getUint32(cursor, true);
        cursor += 4;
        const length = dv.getUint32(cursor, true);
        cursor += 4;
        if(blockType === 0) {{
            // Fill zero
            image.push({{ start, fill: {{ value: 0, length }}}})
        }} else if(blockType === 1) {{
            const block = data.subarray(cursor, cursor + length);
            cursor += length;
            image.push({{ start, data: block }});
        }}
    }}
    return image;
}}

function applyImage(data, image) {{
    for(const section of image) {{
        if(section.data) data.set(section.data, section.start);
        else data.subarray(section.start, section.fill.length).fill(section.fill.value);
    }}
}}

class Caldera{environment.result} {{
    initialRAM = null;
    emulator = null;
    constructor(emulator) {{ this.emulator = emulator; }}
    async init() {{
        this.initialRAM = parseImage(new Uint8Array(await (await fetch("{environment.avail_url_base}/system.cmi")).arrayBuffer()));
        {_postconstruct}
        this.reset();
        this.emulator.run();
        await this._cpuStop();
    }}

    reset() {{
        applyImage(this.emulator.v86.cpu.mem8, this.initialRAM);
    }}

    _cpuStop() {{
        return new Promise(res => {{
            const interval = setInterval(() => {{
                if(this.emulator.v86.cpu.in_hlt.valueOf()[0] == 1) {{
                    clearInterval(interval);
                    res();
                }}
            }}, 1000);
        }});
    }}

    {'\n'.join(_exposed)}
}}
"""
    if not environment.supress_js:
        with open(join(environment.outdir, f'{environment.result}.js'), 'w') as e:
            e.write(output_js)

def linksofile(file_name):
    elffile = elftools.elf.elffile.ELFFile(open(file_name, 'rb'))
    ext = SOExternalLinkage(elffile)
    ext.undefs = {}
    ext.undef_assignments = {}
    ext.name = file_name
    _finishhooks.append(lambda: ext.endhook())
    # Start linking the program into the current output section.
    progbits_sections = []
    reloc_sections = []
    # Find ranges of memory to allocate and make a note of all the progbits sections
    min_mem, max_mem = elffile.stream_len, 0
    for section_number in range(elffile.header.e_shnum):
        section = elffile.get_section(section_number)
        print(f"Section #{section_number} of file {file_name} is called {section.name} ({section.header.sh_type})")
        if section.header.sh_addr == 0: continue
        progbits_sections.append(section)
        if section.header.sh_type == 'SHT_REL':
            reloc_sections.append(section)
        min_mem = min(min_mem, section.header.sh_addr)
        max_mem = max(max_mem, section.header.sh_addr + section.header.sh_size)
    # Allocate a region
    print(f"Actual start offset of file is {min_mem}")
    elffile_out_region = [0 for x in range(max_mem - min_mem + 1)]
    ext.linkedmem = elffile_out_region
    print(f"SOFile {file_name} takes up {max_mem - min_mem + 1:x} bytes of contiguous space")
    # Fill in the region with the data
    for program_section in progbits_sections:
        start = program_section.header.sh_addr - min_mem
        end = program_section.header.sh_addr + program_section.header.sh_size - min_mem
        print(f"Linking {file_name}->{program_section.name} to region {start:x}-{end:x} of local addr space")
        raw_data = program_section.data()
        print(len(raw_data))
        elffile_out_region[start:end] = list(raw_data) if len(raw_data) else [0 for _ in range(program_section.header.sh_size)]
    ext.base = environment.org
    ext.base_offset = -min_mem
    ext.got = elffile.get_section_by_name('.got').header.sh_addr + ext.base + ext.base_offset

    # Apply relocations
    def add_undef(name, addr_local):
        if name not in ext.undefs:
            ext.undefs[name] = []
        ext.undefs[name].append(addr_local)
    for relocation_section in reloc_sections:
        sym_section = elffile.get_section(relocation_section.header.sh_link)
        for reloc in relocation_section.iter_relocations():
            info_type = reloc.entry.r_info_type
            info_sym = reloc.entry.r_info_sym
            r_val = int.from_bytes(bytes(elffile_out_region[reloc.entry.r_offset - min_mem:reloc.entry.r_offset - min_mem + 4]), 'little')
            if info_type == 8: # R_386_RELATIVE - Base + value
                r_val += environment.org - min_mem
            elif info_type == 7: # R_386_JMP_SLOT - symbol value
                if sym_section.get_symbol(info_sym).entry.st_shndx == 'SHN_UNDEF':
                    name = sym_section.get_symbol(info_sym).name
                    add_undef(name, reloc.entry.r_offset - min_mem)
                    r_val = 0xF00FBA11
                else:
                    r_val = sym_section.get_symbol(info_sym).entry.st_value + environment.org - min_mem
            elif info_type == 6: # R_386_GLOB_DAT - symbol value
                if sym_section.get_symbol(info_sym).entry.st_shndx == 'SHN_UNDEF':
                    name = sym_section.get_symbol(info_sym).name
                    add_undef(name, reloc.entry.r_offset - min_mem)
                    r_val = 0xF00DBA11
                else:
                    r_val = sym_section.get_symbol(info_sym).entry.st_value + environment.org - min_mem
            elif info_type == 1: # R_386_32 - symbol value + base
                r_val += sym_section.get_symbol(info_sym).entry.st_value + environment.org - min_mem
            else:
                print(f"Info type: {info_type}, {reloc.entry.r_info_sym}, {relocation_section.header.sh_link}")
            elffile_out_region[reloc.entry.r_offset - min_mem:reloc.entry.r_offset - min_mem + 4] = list(r_val.to_bytes(4, 'little'))
    _synthesis_sections.append(ext)
    environment.org += len(elffile_out_region) + 4096 * 4
    environment.org = (environment.org & ~4095) + 4096
    return ext


def include(fname):
    with open(fname, 'r') as e:
        exec(e.read())

def rawsection(section):
    _synthesis_sections.append(section)
