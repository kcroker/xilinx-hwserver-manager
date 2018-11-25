#!/usr/bin/python3

import os
import sys
import time

# We assume that each JTAG USB line connects to a single board
# And we want to have hw_server's dedicated to each board
# This way:
#  1) To debug a specific board, just chose a specific port
#  2) To sdk a specific board, just choose a specific port
#     (no more annoying manual device selection in debug configurations)
#  3) If a board is glitchy (power or bad cable or something), it won't
#     interfere with other people's hw_server experience

# Start a hw_server that talks to everything
os.system('%s/hw_server -d' % os.environ['VIVADO_PATH'])

# Get the hardware targets
# Notice we need to use script to trick vivado's shell into thinking that
# we're an actual terminal.  xsdb is faster and gives full chains,
# but it crashes on non-tty *input* ...
os.system('echo "open_hw\nconnect_hw_server\nget_hw_targets\nquit" | script -c "%s/vivado -mode tcl" vivado_xscript.tmp' % os.environ['VIVADO_PATH'])

# Kill all hardware servers that we can kill
os.system('pkill hw_server')

# Now parse out the cable identifiers
os.system('grep "Digilent" vivado_xscript.tmp > hw_targets.tmp')

# Get em
with open('hw_targets.tmp') as f:
    targets = f.readline().split()

# See em
print(targets)

# Start up HW servers for each device
# Will be sane ports for N < 10
port_base = 35000
gdb_port_base = 36000

for N,target in enumerate(targets):
    # Remove the leading hostname garbage
    devid = target[target.find("Digilent"):].split('/')[1]

    print("Serving device %s...\n" % devid)
    
    # Get ports
    port = port_base + N
    # gdb_port = gdb_port_base + N*100

    # Start the dedicated server
    # We don't use GDB (why not...) and the stupid hw_server won't spawn
    # gdb listeners if run with -d.  It also spawns gdb listeners on 3000-3004 always
    # even if you tell it not too.  Pretty retarded Xilinx.
    #
    #os.system('%s/hw_server -d -g%d:arm -g%d:arm64 -g%d:microblaze -g%d:microblazex -s tcp:192.168.153.189:%d -e "set jtag-port-filter %s"' % (os.environ['VIVADO_PATH'], gdb_port + 1, gdb_port + 2, gdb_port + 3, gdb_port + 4, port, devid))

    os.system('%s/hw_server -d -s tcp:192.168.153.189:%d -e "set jtag-port-filter %s"' % (os.environ['VIVADO_PATH'], port, devid))

    # Chill a bit so we don't race
    time.sleep(1)
