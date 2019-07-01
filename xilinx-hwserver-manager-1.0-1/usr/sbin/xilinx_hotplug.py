#!/usr/bin/python3

import os
import sys
import subprocess
import signal
import syslog
import fcntl

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

# syslog.syslog(syslog.LOG_DEBUG, "hotplug called!")

# Load and lock on /etc/xilinx_hotplug.conf
with open("/etc/xilinx_hotplug.conf", "a+") as f:
    
    # Sweet flock() is blocking
    # syslog.syslog("Waiting on POSIX configuration file lock")
    try:
        fcntl.flock(f, fcntl.LOCK_EX)
    except Exception as e:
        syslog.syslog("POSIX lock on the configuration file failed: %s" % e)
        exit(0)

    # syslog.syslog("POSIX lock on configuration file acquired")
    
    # We parse the file after the lock is yielded, so if other cables have been
    # recorded for the first time, we know
            
    # Append mode puts you at the end
    f.seek(0)

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
        clearLock(lock)
        exit(1)

    # Syslog debug output
    # syslog.syslog(syslog.LOG_DEBUG, "Known leases: %s" % cable_leases)

    # Get a list of current hw_server cable ID's
    serviced_targets = []
    try:
        instances = subprocess.check_output("pgrep -a 'hw_server' | egrep -o 'filter [0-9A-F]+'", shell=True)
        instances = instances.decode("utf-8")
        
        # Make it into a newline delimited list
        instances = instances.strip().split("\n")

        # Remove the filter part
        serviced_targets = [instance.split()[1] for instance in instances]
    
        # Log to syslog
        # syslog.syslog(syslog.LOG_DEBUG, "Current cables seviced: %s" % serviced_targets)
    
    except subprocess.CalledProcessError as e:
        pass
        #syslog.syslog(syslog.LOG_DEBUG, "No cables serviced" % e.output)

    # Define the target directly from udev
    target = os.environ['ID_SERIAL_SHORT']

    if sys.argv[1] == "--remove":
        # Iterate through the instances and prune unnecessary ones
        if target in serviced_targets:
            os.system("pkill -f 'filter %s'" % target)
            syslog.syslog("Terminated unnecessary hw_server for detached cable %s" % cable_leases[target][1])
    
    if sys.argv[1] == "--add":   
        if not target in serviced_targets:
            # Spawn one
            # First, check to see if its in the /etc/xilinx_hotplug.conf
            port = None
            name = None
            if target in cable_leases:
                
                syslog.syslog("Found a lease for %s at port %d" % (cable_leases[target][1], int(cable_leases[target][0])))
        
                # Fetch the lease
                lease = cable_leases[target]
                port = int(lease[0])
                name = lease[1]
            else:

                # Here, we need to be careful
                port = base_port + len(cable_leases)
                name = target
                
                print("cable_lease %s %d \"%s\"" % (target, port, name), file=f)
                syslog.syslog("Added new JTAG cable %s at port %d" % (target, port))
                cable_leases[target] = [port, name]

            # And spawn
            os.system('%s/hw_server -q -d -s tcp:%s:%d -e "set jtag-port-filter %s"' % (vivado_path, address, port, target))
            
            # Log human readable to syslog
            syslog.syslog("Spawned hw_server for JTAG device %s, listening at %s:%s" % (name, address, port))

# Debug
# syslog.syslog("Released POSIX configuration file lock")

