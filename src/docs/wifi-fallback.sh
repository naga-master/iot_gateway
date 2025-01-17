#!/bin/bash

# ------------------------------------------------------------- #
# File path to place:  /usr/local/bin/wifi-fallback.sh
# sudo apt-get update
# sudo apt-get install -y hostapd dnsmasq wireless-tools wpasupplicant python3-wifi

# # Stop services initially
# sudo systemctl stop hostapd
# sudo systemctl stop dnsmasq

# # Install Python dependencies
# pip install wifi netifaces

# # Edit /etc/dhcpcd.conf to add static IP for AP mode
# sudo bash -c 'cat >> /etc/dhcpcd.conf << EOF

# interface wlan0
#     static ip_address=192.168.4.1/24
#     nohook wpa_supplicant
# EOF'

# # Make the fallback script executable
# sudo chmod +x /usr/local/bin/wifi-fallback.sh

# # Enable and start the fallback service
# sudo systemctl enable wifi-fallback.service
# sudo systemctl start wifi-fallback.service
# ------------------------------------------------------------- #


# Wait for network connection attempt
sleep 30

# Check if connected to WiFi
if ! iwgetid > /dev/null 2>&1; then
    # No WiFi connection, start AP mode
    python3 -c "
from iot_gateway.utils.wifi_manager import WiFiManager
manager = WiFiManager()
manager.start_ap_mode()
"
fi