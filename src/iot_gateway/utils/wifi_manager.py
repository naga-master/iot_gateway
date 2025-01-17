from typing import List, Dict
import wifi
from ..utils.logging import get_logger

import subprocess
import time
import logging
import netifaces
import wifi

logger = get_logger(__name__)

# WiFi management class
class WiFiManager:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.ap_ssid = "IoTGateway"
        self.ap_password = "iotgateway123"
        self.wpa_supplicant_path = "/etc/wpa_supplicant/wpa_supplicant.conf"
        self.hostapd_path = "/etc/hostapd/hostapd.conf"
        self.dnsmasq_path = "/etc/dnsmasq.conf"

    def scan_networks(self) -> List[Dict[str, str]]:
        """Scan for available WiFi networks"""
        try:
            
            networks = []

            # TODO this needs to be uncommented on raspberry deploy
            # wifi.Cell.all('wlan0')
            # cells = wifi.Cell.all('wlan0')
            
            # for cell in cells:
            #     networks.append({
            #         'ssid': cell.ssid,
            #         'signal_strength': cell.signal,
            #         'encrypted': cell.encrypted,
            #         'encryption_type': cell.encryption_type if cell.encrypted else None
            #     })


            networks.append({
                    'ssid': "Testing",
                    'signal_strength': "2.5 Ghz",
                    'encrypted': "WPA",
                    'encryption_type': None
                })
            return networks
        except Exception as e:
            self.logger.error(f"Error scanning networks: {e}")
            return []

    def connect_to_network(self, ssid: str, password: str) -> bool:
        """Connect to a WiFi network"""
        try:
            # Generate WPA supplicant configuration
            wpa_config = (
                'ctrl_interface=DIR=/var/run/wpa_supplicant GROUP=netdev\n'
                'update_config=1\n'
                'country=US\n\n'
                'network={\n'
                f'    ssid="{ssid}"\n'
                f'    psk="{password}"\n'
                '    key_mgmt=WPA-PSK\n'
                '}\n'
            )
            
            # Write configuration
            with open(self.wpa_supplicant_path, 'w') as f:
                f.write(wpa_config)
            
            # Restart networking services
            subprocess.run(['sudo', 'systemctl', 'restart', 'wpa_supplicant'])
            subprocess.run(['sudo', 'systemctl', 'restart', 'dhcpcd'])
            
            # Wait for connection
            time.sleep(10)
            
            # Check if connected
            return self.check_connection()
        except Exception as e:
            self.logger.error(f"Error connecting to network: {e}")
            return False

    def check_connection(self) -> bool:
        """Check if connected to a WiFi network"""
        try:
            output = subprocess.check_output(['iwgetid']).decode()
            return len(output) > 0
        except:
            return False

    def start_ap_mode(self) -> bool:
        """Start Access Point mode"""
        try:
            # Configure hostapd
            hostapd_config = (
                f'interface=wlan0\n'
                f'driver=nl80211\n'
                f'ssid={self.ap_ssid}\n'
                f'hw_mode=g\n'
                f'channel=7\n'
                f'wmm_enabled=0\n'
                f'macaddr_acl=0\n'
                f'auth_algs=1\n'
                f'ignore_broadcast_ssid=0\n'
                f'wpa=2\n'
                f'wpa_passphrase={self.ap_password}\n'
                f'wpa_key_mgmt=WPA-PSK\n'
                f'wpa_pairwise=TKIP\n'
                f'rsn_pairwise=CCMP\n'
            )
            
            with open(self.hostapd_path, 'w') as f:
                f.write(hostapd_config)

            # Configure dnsmasq
            dnsmasq_config = (
                'interface=wlan0\n'
                'dhcp-range=192.168.4.2,192.168.4.20,255.255.255.0,24h\n'
            )
            
            with open(self.dnsmasq_path, 'w') as f:
                f.write(dnsmasq_config)

            # Configure static IP
            subprocess.run(['sudo', 'ifconfig', 'wlan0', '192.168.4.1', 'netmask', '255.255.255.0'])
            
            # Start services
            subprocess.run(['sudo', 'systemctl', 'start', 'hostapd'])
            subprocess.run(['sudo', 'systemctl', 'start', 'dnsmasq'])
            
            return True
        except Exception as e:
            self.logger.error(f"Error starting AP mode: {e}")
            return False

    def get_current_wifi_info(self) -> Dict[str, str]:
        """Get current WiFi connection information"""
        try:
            ssid = subprocess.check_output(['iwgetid', '-r']).decode().strip()
            strength = subprocess.check_output(['iwconfig', 'wlan0']).decode()
            signal_strength = strength.split('Signal level=')[1].split(' ')[0]
            
            return {
                'ssid': ssid,
                'signal_strength': signal_strength,
                'ip_address': netifaces.ifaddresses('wlan0')[netifaces.AF_INET][0]['addr']
            }
        except:
            return {
                'ssid': None,
                'signal_strength': None,
                'ip_address': None
            }