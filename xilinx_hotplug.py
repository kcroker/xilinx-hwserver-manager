#!/usr/bin/python3

import os
import sys
import subprocess
import signal
import syslog

# This way:
#  1) To debug a cable, just chose a specific port
#  2) To sdk a cable, just choose a specific port
#     (no more annoying manual device selection in debug configurations)
#  3) If a cable is glitchy (power or bad cable or something), it won't
#     interfere with other people's hw_server experience

# Some default values
address = "127.0.0.1"
base_port = 35000
vivado_path = None
cable_leases = {}

# Load /etc/xilinx_hotplug.conf
with open("/etc/xilinx_hotplug.conf", "r") as f:
    for N,line in enumerate(f):

        directives = line.strip().split()

        if not directives:
            continue
        
        # Otherwise parse
        try:
            if directives[0] == '#':
                pass
            elif directives[0] == 'address':
                address = directives[1]
            elif directives[0] == 'vivado_path':
                vivado_path = directives[1]
            elif directives[0] == 'base_port':
                base_port = directives[1]
            elif directives[0] == 'cable_lease':
                # Reassemble a single string from all the split human readable 
                cable_leases[directives[1]] = (directives[2], (" ".join(directives[3:])))

        except IndexError as e:
            syslog.syslog(syslog.LOG_WARNING, "Line %d of configuration file could not be parsed, ignoring" % N)

    # Bail if we don't know where to find the hw_server executable
    if vivado_path is None:
        syslog.syslog(syslog.LOG_ERR, "Vivado path not specified, quitting")
        exit(1)
        
# Start an hw_server to get the available cables.
# Notice we have to setgid because Xilinx commands are all shell wrappers which make architecture-dependent decisions
# So we get shit spawning shit, and its hard to reliably kill it all
#
# We have to exec(), so we inherit the foreground process (no -d), change its group, and then kill the entire group.
# Ugh.
server = subprocess.Popen(["exec %s/hw_server" % vivado_path, "-s 127.0.0.1", "-q"],
                          preexec_fn=os.setpgrp,
                          shell=True,
                          stdout=subprocess.DEVNULL,
                          stderr=subprocess.DEVNULL)

os.system('echo "connect -host 127.0.0.1\nset logfile [open \"/tmp/hw_targets.tmp\" \"w\"]\nputs \$logfile [jtag targets]\nclose \$logfile\n" | %s/xsdb -quiet' % vivado_path)
os.system('grep -i "Digilent" /tmp/hw_targets.tmp > /tmp/hw_targets')
os.system("rm /tmp/hw_targets.tmp")

# Kill all the stuff that just got spawned
os.killpg(os.getpgid(server.pid), signal.SIGTERM)

# Get whats currently recognized by vivado
actual_targets = []
for l in open('/tmp/hw_targets'):
    actual_targets.append(l.split()[3])

# Clean up the last temp file
os.system("rm /tmp/hw_targets")

# Get a list of current hw_server cable ID's
instances = None
try:
    instances = subprocess.check_output("ps aux | grep 'hw_server' | egrep -o 'filter [0-9A-F]+'", shell=True)
    instances = instances.decode("utf-8")

    # Make it into a newline delimited list
    instances = instances.strip().split("\n")
except subprocess.CalledProcessError:
    instances = []

serviced_targets = []
for instance in instances:
    serviced_targets.append(instance.split()[1])

# Iterate through the instances and prune unnecessary ones
for target in serviced_targets:
    if not target in actual_targets:
        # Kill it
        os.system("pkill -f 'filter %s'" % target)
        syslog.syslog("Terminated unnecessary hw_server for detached cable %s" % target)
        
# Iterate through the targets and spawn new ones
for target in actual_targets:
    if not target in serviced_targets:

        # Spawn one
        # First, check to see if its in the /etc/xilinx_hotplug.conf
        port = None
        name = None
        if target in cable_leases:

            # Fetch the lease
            lease = cable_leases[target]
            port = int(lease[0])
            name = lease[1]
        else:
            port = base_port + len(cable_leases)
            name = target
            
            # It was not known, so add it
            with open("/etc/xilinx_hotplug.conf", "a") as f:
                print("Derping")
                print("cable_lease %s %d \"%s\"" % (target, port, name), file=f)
                syslog.syslog("Added new JTAG cable %s at port %d" % (target, port))
                cable_leases[target] = [port, name]
                
        # And spawn
        os.system('%s/hw_server -q -d -s tcp:%s:%d -e "set jtag-port-filter %s"' % (vivado_path, address, port, target))

        # Log human readable to syslog
        syslog.syslog("JTAG device %s serviced by dedicated hw_server at %s:%s" % (name, address, port))
