#!/bin/bash
echo "restarting librespot"
systemctl --user reset-failed librespot
systemctl --user restart librespot
sleep 2
systemctl --user status librespot --no-pager
echo ""
echo "Done!"