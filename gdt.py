F_GRANULARITY = 0x8 # If set block=4KiB otherwise block=1B
F_PROT_32 = 0x4     # Protected Mode 32 bit
F_LONG = 0x2        # Long Mode
F_AVAILABLE = 0x1   # Free Use
A_PRESENT = 0x80    # Segment active
A_PRIV_3 = 0x60     # Ring 3 Privs
A_PRIV_2 = 0x40     # Ring 2 Privs
A_PRIV_1 = 0x20     # Ring 1 Privs
A_PRIV_0 = 0x0      # Ring 0 Privs
A_CODE = 0x10       # Code Segment
A_DATA = 0x10       # Data Segment
A_TSS = 0x0         # TSS
A_GATE = 0x0        # GATE
A_EXEC = 0x8        # Executable
A_DATA_WRITABLE = 0x2
A_CODE_READABLE = 0x2
A_DIR_CON_BIT = 0x4
S_GDT = 0x0         # Index points to GDT
S_LDT = 0x4         # Index points to LDT
S_PRIV_3 = 0x3      # Ring 3 Privs
S_PRIV_2 = 0x2      # Ring 2 Privs
S_PRIV_1 = 0x1      # Ring 1 Privs
S_PRIV_0 = 0x0      # Ring 0 Privs


def create_selector(idx, flags):
    to_ret = flags
    to_ret |= idx << 3
    return to_ret

def create_gdt_entry(base, limit, access, flags):
    to_ret = limit & 0xffff
    to_ret |= (base & 0xffffff) << 16
    to_ret |= (access & 0xff) << 40
    to_ret |= ((limit >> 16) & 0xf) << 48
    to_ret |= (flags & 0xff) << 52
    to_ret |= ((base >> 24) & 0xff) << 56
    return to_ret
