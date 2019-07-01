# Xilinx `hw_server` Manager
Keeps track of JTAG cables and spawns dedicated hw_server instances on consistent ports to service them.
Remembers newly added boards and assigns new ports to them.
Also kills unnecessary hw_servers upon disconnect.

Uses udev and python-3.
Written as a Debian/Devuan ASCII package.

## Installation
After cloning the repository, `cd` to the repository and run

```bash
$ dpkg-deb --build xilinx-hwserver-manager-1.0-1
$ sudo dpkg -i xilinx-hwserver-manager-1.0-1.deb
```

Boards are recognized and added upon install.
To customize human-readable names for the boards, just edit `/etc/xilinx_hotplug.conf`.

## Reloading configuration
You can reload configuration (e.g. the server bind address, port assignments for particular cables) at any time by running

```bash
$ sudo udevadm trigger --action=add --subsystem-match=usb --attr-match=idVendor='0403'
```

Note that this will kill all currently running `hw_server`s.
