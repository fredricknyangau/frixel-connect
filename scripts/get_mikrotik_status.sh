#!/bin/bash
setsid env SSH_ASKPASS="$(dirname "$0")/askpass.sh" SSH_ASKPASS_REQUIRE=force DISPLAY=:0 ssh -o StrictHostKeyChecking=no admin@192.168.56.100 "/ip hotspot print; /ip dhcp-server print; /ip pool print"

