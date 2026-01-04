LINKER_SCRIPT = """
ENTRY(start)

SECTIONS {
    . = 0x100000; /* Tells GRUB to load the kernel starting at the 1MB */

    .boot :
    {
        /* Ensure that the multiboot header is at the beginning */
        *(.multiboot_header)
    }

    .text :
    {
        *(.text)
    }

}
"""

NASM_MULTIBOOT = """
; Multiboot v1 - Compliant Header for QEMU 
; We use multiboot v1 since Qemu "-kernel" doesn't support 
; multiboot v2

; This part MUST be 4-byte aligned, so we solve that issue using 'ALIGN 4'
ALIGN 4
section .multiboot_header
    ; Multiboot macros to make a few lines later more readable
    MULTIBOOT_PAGE_ALIGN	equ 1<<0
    MULTIBOOT_MEMORY_INFO	equ 1<<1                                         
    MULTIBOOT_HEADER_MAGIC	equ 0x1BADB002                                   ; magic number 
    MULTIBOOT_HEADER_FLAGS	equ MULTIBOOT_PAGE_ALIGN | MULTIBOOT_MEMORY_INFO ; flags
    MULTIBOOT_CHECKSUM	equ - (MULTIBOOT_HEADER_MAGIC + MULTIBOOT_HEADER_FLAGS)  ; checksum 
                                ; (magic number + checksum + flags should equal 0)

    ; This is the GRUB Multiboot header. A boot signature
    dd MULTIBOOT_HEADER_MAGIC
    dd MULTIBOOT_HEADER_FLAGS
    dd MULTIBOOT_CHECKSUM
"""

BUILD_SCRIPT = """
nasm -felf32 "{dir}/multiboot_header.asm" -o "{dir}/multiboot_header.o"
nasm -felf32 "{dir}/boot.asm" -o "{dir}/boot.o"
ld -m elf_i386 -n -T "{dir}/linker.ld" -o "{output}" "{dir}/boot.o" "{dir}/multiboot_header.o"
"""

import gdt
from os.path import join
from dataclasses import dataclass, field
import subprocess

def gen_default_gdt():
    return [
        0,
	    0x00cf9b000000ffff, # flat 32-bit code segment
	    0x00cf93000000ffff, # flat 32-bit data segment
	    0x00cf1b000000ffff, # flat 32-bit code segment, not present
	    0,                  # TSS for task gates
	    0x008f9b000000FFFF, # 16-bit code segment
	    0x008f93000000FFFF, # 16-bit data segment
	    0x00cffb000000ffff, # 32-bit code segment (user)
	    0x00cff3000000ffff, # 32-bit data segment (user)
	    0,                  # unused
	    0,			        # 6 spare selectors
	    0,
	    0,
	    0,
	    0,
        0,
    ]

@dataclass
class Kernel:
    stack_base: int = 0x80_0000
    control_transfer_address: int = 0x84_0000
    directory_temp: str = "/tmp/kernelbuild"
    output: str = 'kernel.bin'


kern_environment = Kernel()

_gdt = gen_default_gdt()
def insert_gdt_entry(index, base, limit, access, flags):
    global _gdt
    to_insert = index - len(_gdt) + 1
    if to_insert > 0:
        _gdt += [0] * to_insert
    _gdt[index] = gdt.create_gdt_entry(base, limit, access, flags)

_selectors_bound = [] # List of tuples (register, value)

def bind_register_to_selector(reg: str, index: int, flags: int):
    global _selectors_bound
    _selectors_bound.append((reg, gdt.create_selector(index, flags)))


def build_kernel():
    global kern_environment
    global _selectors_bound
    global _gdt
    with open(join(kern_environment.directory_temp, 'linker.ld'), 'w') as e: e.write(LINKER_SCRIPT)
    print("Written linker script.")
    with open(join(kern_environment.directory_temp, 'multiboot_header.asm'), 'w') as e: e.write(NASM_MULTIBOOT)
    print("Written multiboot header.")
    with open(join(kern_environment.directory_temp, 'make.sh'), 'w') as e: e.write(BUILD_SCRIPT.format(output=kern_environment.output, dir=kern_environment.directory_temp))
    print("Written buildscript.")
    segment_regs = ""
    for reg_name, value in _selectors_bound:
        segment_regs += f"""
mov ax, {value}
mov {reg_name}, ax
        """
    KERNEL = f"""
global start

section .text
bits 32
start:
    lgdt [gdt32_descr]
{segment_regs}
	mov eax, {hex(kern_environment.stack_base)}
	mov esp, eax
    jmp [{hex(kern_environment.control_transfer_address)}]

gdt32:
	{'\n'.join(f'dq {a:#018x}' for a in _gdt)}
tss_descr:
        times 64
        dq 0x000089000000ffff
gdt32_end:
gdt32_descr:
	dw gdt32_end - gdt32 - 1
	dd gdt32
    """
    with open(join(kern_environment.directory_temp, 'boot.asm'), 'w') as e: e.write(KERNEL)
    print("Written kernel.")
    subprocess.run(["bash", join(kern_environment.directory_temp, 'make.sh')])
    print("Kernel built.")

