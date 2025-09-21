"""
Discovery System for Xiaomi MiIO Integration
Handles device discovery via mDNS/Zeroconf and network scanning
"""

import socket
import logging
import struct
import time
from typing import List, Dict, Any, Optional
from zeroconf import ServiceBrowser, Zeroconf, ServiceInfo
import threading

logger = logging.getLogger(__name__)


class XiaomiDiscovery:
    """Handles Xiaomi device discovery"""
    
    def __init__(self):
        """Initialize discovery handler"""
        self.discovered_devices = {}
        self.zeroconf = None
        self.browser = None
        self._lock = threading.Lock()
    
    def start_mdns_discovery(self, callback=None):
        """Start mDNS/Zeroconf discovery"""
        try:
            self.zeroconf = Zeroconf()
            self.browser = ServiceBrowser(
                self.zeroconf,
                ["_miio._udp.local."],
                self,
                handlers=[self._mdns_handler]
            )
            logger.info("Started mDNS discovery for Xiaomi devices")
        except Exception as e:
            logger.error(f"Failed to start mDNS discovery: {e}")
    
    def stop_mdns_discovery(self):
        """Stop mDNS discovery"""
        if self.browser:
            self.browser.cancel()
        if self.zeroconf:
            self.zeroconf.close()
        logger.info("Stopped mDNS discovery")
    
    def _mdns_handler(self, zeroconf: Zeroconf, service_type: str, name: str, state_change):
        """Handle mDNS service events"""
        if state_change == "added":
            info = zeroconf.get_service_info(service_type, name)
            if info:
                self._process_mdns_device(info)
    
    def _process_mdns_device(self, info: ServiceInfo):
        """Process discovered mDNS device"""
        try:
            # Extract device information
            ip = socket.inet_ntoa(info.addresses[0]) if info.addresses else None
            if not ip:
                return
            
            properties = info.properties
            device_info = {
                'ip': ip,
                'port': info.port or 54321,
                'name': info.name,
                'mac': None,
                'model': None,
                'token': None
            }
            
            # Extract MAC address
            if b'mac' in properties:
                device_info['mac'] = properties[b'mac'].decode('utf-8')
            
            # Extract model
            if b'model' in properties:
                device_info['model'] = properties[b'model'].decode('utf-8')
            
            # Try to extract from poch field (some devices)
            if b'poch' in properties:
                poch = properties[b'poch'].decode('utf-8')
                if 'mac=' in poch:
                    mac_part = poch.split('mac=')[1].split('&')[0]
                    device_info['mac'] = mac_part
            
            # Store discovered device
            with self._lock:
                self.discovered_devices[ip] = device_info
            
            logger.info(f"Discovered Xiaomi device via mDNS: {device_info}")
            
        except Exception as e:
            logger.error(f"Error processing mDNS device: {e}")
    
    def scan_network(self, ip_range: str = None, timeout: int = 5) -> List[Dict[str, Any]]:
        """
        Scan network for Xiaomi devices using MiIO protocol
        
        Args:
            ip_range: IP range to scan (e.g., "192.168.1.0/24")
            timeout: Scan timeout in seconds
            
        Returns:
            List of discovered devices
        """
        discovered = []
        
        if not ip_range:
            # Try to detect local network
            ip_range = self._get_local_network()
        
        if not ip_range:
            logger.warning("Could not determine network range for scanning")
            return discovered
        
        logger.info(f"Scanning network {ip_range} for Xiaomi devices...")
        
        # Parse IP range
        ips = self._parse_ip_range(ip_range)
        
        # Scan each IP
        for ip in ips:
            device = self._probe_device(ip, timeout)
            if device:
                discovered.append(device)
        
        return discovered
    
    def _probe_device(self, ip: str, timeout: int = 2) -> Optional[Dict[str, Any]]:
        """
        Probe a single IP for Xiaomi device
        
        Args:
            ip: IP address to probe
            timeout: Probe timeout
            
        Returns:
            Device info if found, None otherwise
        """
        try:
            # Create UDP socket
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.settimeout(timeout)
            
            # MiIO hello packet (21 31 00 20 + 16 bytes of 0xFF + checksum)
            hello = bytes.fromhex('21310020') + b'\xFF' * 16
            
            # Calculate MD5 checksum
            import hashlib
            checksum = hashlib.md5(hello).digest()
            packet = hello + checksum
            
            # Send hello packet
            sock.sendto(packet, (ip, 54321))
            
            # Wait for response
            try:
                data, addr = sock.recvfrom(1024)
                
                if data and len(data) >= 32:
                    # Parse response header
                    magic = struct.unpack('>H', data[0:2])[0]
                    length = struct.unpack('>H', data[2:4])[0]
                    
                    if magic == 0x2131:  # Valid MiIO response
                        # Extract device ID and timestamp
                        device_id = data[8:12].hex()
                        timestamp = struct.unpack('>I', data[12:16])[0]
                        
                        device_info = {
                            'ip': ip,
                            'port': 54321,
                            'device_id': device_id,
                            'timestamp': timestamp,
                            'responsive': True
                        }
                        
                        logger.info(f"Found Xiaomi device at {ip}")
                        return device_info
                        
            except socket.timeout:
                pass
            finally:
                sock.close()
                
        except Exception as e:
            logger.debug(f"Error probing {ip}: {e}")
        
        return None
    
    def _get_local_network(self) -> Optional[str]:
        """Get local network range"""
        try:
            # Get local IP
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.connect(("8.8.8.8", 80))
            local_ip = sock.getsockname()[0]
            sock.close()
            
            # Assume /24 network
            parts = local_ip.split('.')
            network = f"{parts[0]}.{parts[1]}.{parts[2]}.0/24"
            
            return network
            
        except Exception as e:
            logger.error(f"Failed to get local network: {e}")
            return None
    
    def _parse_ip_range(self, ip_range: str) -> List[str]:
        """Parse IP range into list of IPs"""
        ips = []
        
        try:
            if '/' in ip_range:
                # CIDR notation
                import ipaddress
                network = ipaddress.ip_network(ip_range, strict=False)
                for ip in network.hosts():
                    ips.append(str(ip))
            elif '-' in ip_range:
                # Range notation (e.g., 192.168.1.1-254)
                base, end_part = ip_range.rsplit('.', 1)
                if '-' in end_part:
                    start, end = end_part.split('-')
                    for i in range(int(start), int(end) + 1):
                        ips.append(f"{base}.{i}")
            else:
                # Single IP
                ips.append(ip_range)
                
        except Exception as e:
            logger.error(f"Failed to parse IP range {ip_range}: {e}")
        
        return ips
    
    def discover_by_model(self, model_filter: str = None) -> List[Dict[str, Any]]:
        """
        Discover devices filtered by model
        
        Args:
            model_filter: Model substring to filter by
            
        Returns:
            List of matching devices
        """
        devices = []
        
        with self._lock:
            for device in self.discovered_devices.values():
                if model_filter:
                    if device.get('model') and model_filter in device['model']:
                        devices.append(device)
                else:
                    devices.append(device)
        
        return devices
    
    def get_discovered_devices(self) -> Dict[str, Dict[str, Any]]:
        """Get all discovered devices"""
        with self._lock:
            return self.discovered_devices.copy()