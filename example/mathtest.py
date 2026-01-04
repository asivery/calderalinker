# Add Calderalinker to the path
import sys
sys.path.append('..')

# Use the linker:
from linker import *

# Use the kernel builder:
from kernel import *

u = environment
k = kern_environment
# Set the name of the project:
u.result = 'mathtest'
# Define where to write the output files:
u.outdir = 'mathtest/page/output'
# And define what URL the files will be rooted in:
u.avail_url_base = 'output'
# Also, declare where the kernel should be placed:
k.output = 'mathtest/page/output/kernel.bin'

# Linker: Position self at address 0x840000
# Kernel: Set control transfer address to 0x840000
k.control_transfer_address = u.org = 0x84_0000
# Linker: Place the control transfer section at current address
entry_section()

# Linker: At address 0x400000 place mathtest/program.so, mathtest/helper.so, /usr/lib32/libm.so.6
u.org = 0x40_0000
library = linksofile('mathtest/program.so')
helper = linksofile('mathtest/helper.so')
math = linksofile('/usr/lib32/libm.so.6')

# Link the following symbols:
# program.so:print ==> helper.so:print
# program.so:printNumber ==> helper.so:printNumber
# program.so:_sqrt ==> libm.so:sqrt
# program.so:_sin ==> libm.so:sin
linkundef(library, 'print', helper)
linkundef(library, 'printNumber', helper)
linkundef(library, '_sqrt', math, 'sqrt')
linkundef(library, '_sin', math, 'sin')

# Build the JS entrypoint test ==> program.so:test
jsentry('test', library, 'test')

# Include the helperio.py file (eval in place here)
include("helperio.py")

# Link the system image and build the kernel:
finish()
build_kernel()
