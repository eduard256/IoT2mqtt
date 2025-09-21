"""
Xiaomi Cloud Client for MiIO Integration
Handles authentication and device discovery through Xiaomi cloud
"""

import logging
import hashlib
import json
from typing import Dict, Any, List, Optional

try:
    from micloud import MiCloud
    from micloud.micloudexception import MiCloudAccessDenied
    HAS_MICLOUD = True
except ImportError:
    HAS_MICLOUD = False
    logger.warning("micloud library not installed. Cloud features will be disabled.")

logger = logging.getLogger(__name__)

# Server country codes from Home Assistant
SERVER_COUNTRY_CODES = ["cn", "de", "i2", "ru", "sg", "us"]
DEFAULT_CLOUD_COUNTRY = "cn"


class MiCloudClient:
    """Client for Xiaomi Cloud services"""
    
    def __init__(self, username: str, password: str, country: str = DEFAULT_CLOUD_COUNTRY):
        """
        Initialize cloud client
        
        Args:
            username: Xiaomi account username
            password: Xiaomi account password
            country: Country server code
        """
        if not HAS_MICLOUD:
            raise ImportError("micloud library is required for cloud features")
        
        self.username = username
        self.password = password
        self.country = country if country in SERVER_COUNTRY_CODES else DEFAULT_CLOUD_COUNTRY
        
        self.cloud = None
        self.logged_in = False
        self.devices_cache = {}
        
        logger.info(f"Initialized MiCloud client for {username} on {self.country} server")
    
    def login(self) -> bool:
        """
        Login to Xiaomi cloud
        
        Returns:
            True if login successful
        """
        try:
            self.cloud = MiCloud(self.username, self.password)
            
            if self.cloud.login():
                self.logged_in = True
                logger.info("Successfully logged in to Xiaomi cloud")
                return True
            else:
                logger.error("Failed to login to Xiaomi cloud")
                return False
                
        except MiCloudAccessDenied as e:
            logger.error(f"Access denied to Xiaomi cloud: {e}")
            raise
        except Exception as e:
            logger.error(f"Error logging in to Xiaomi cloud: {e}")
            return False
    
    def get_devices(self, force_refresh: bool = False) -> List[Dict[str, Any]]:
        """
        Get devices from Xiaomi cloud
        
        Args:
            force_refresh: Force refresh from cloud instead of using cache
            
        Returns:
            List of device information dicts
        """
        if not self.logged_in and not self.login():
            logger.error("Not logged in to Xiaomi cloud")
            return []
        
        if not force_refresh and self.devices_cache:
            return list(self.devices_cache.values())
        
        try:
            # Get devices from cloud
            devices_raw = self.cloud.get_devices(self.country)
            
            # Process devices
            devices = []
            for device_data in devices_raw:
                device_info = self._process_cloud_device(device_data)
                if device_info:
                    devices.append(device_info)
                    # Cache by DID
                    self.devices_cache[device_info['did']] = device_info
            
            logger.info(f"Retrieved {len(devices)} devices from Xiaomi cloud")
            return devices
            
        except Exception as e:
            logger.error(f"Error getting devices from cloud: {e}")
            return []
    
    def get_device_by_id(self, device_id: str) -> Optional[Dict[str, Any]]:
        """
        Get specific device by ID
        
        Args:
            device_id: Device ID (DID)
            
        Returns:
            Device info dict or None
        """
        if device_id in self.devices_cache:
            return self.devices_cache[device_id]
        
        # Try to refresh from cloud
        devices = self.get_devices(force_refresh=True)
        
        for device in devices:
            if device.get('did') == device_id:
                return device
        
        return None
    
    def get_device_by_ip(self, ip: str) -> Optional[Dict[str, Any]]:
        """
        Get device by IP address
        
        Args:
            ip: Device IP address
            
        Returns:
            Device info dict or None
        """
        devices = self.get_devices()
        
        for device in devices:
            if device.get('localip') == ip:
                return device
        
        return None
    
    def get_device_token(self, device_id: str = None, ip: str = None) -> Optional[str]:
        """
        Get device token
        
        Args:
            device_id: Device ID
            ip: Device IP address
            
        Returns:
            Device token or None
        """
        device = None
        
        if device_id:
            device = self.get_device_by_id(device_id)
        elif ip:
            device = self.get_device_by_ip(ip)
        
        if device:
            return device.get('token')
        
        return None
    
    def _process_cloud_device(self, device_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Process raw cloud device data
        
        Args:
            device_data: Raw device data from cloud
            
        Returns:
            Processed device info dict
        """
        try:
            # Extract relevant fields
            device_info = {
                'did': device_data.get('did'),
                'name': device_data.get('name', 'Unknown Device'),
                'model': device_data.get('model'),
                'localip': device_data.get('localip'),
                'token': device_data.get('token'),
                'mac': device_data.get('mac'),
                'ssid': device_data.get('ssid'),
                'bssid': device_data.get('bssid'),
                'parent_id': device_data.get('parent_id'),
                'parent_model': device_data.get('parent_model'),
                'fw_version': device_data.get('fw_ver'),
                'hw_version': device_data.get('hw_ver'),
                'rssi': device_data.get('rssi'),
                'isOnline': device_data.get('isOnline', False),
                'desc': device_data.get('desc', ''),
                'extra': device_data.get('extra', {})
            }
            
            # Validate required fields
            if not device_info['did'] or not device_info['model']:
                logger.warning(f"Skipping device with missing DID or model: {device_data}")
                return None
            
            # Format MAC address if present
            if device_info['mac']:
                device_info['mac'] = self._format_mac(device_info['mac'])
            
            return device_info
            
        except Exception as e:
            logger.error(f"Error processing cloud device: {e}")
            return None
    
    def _format_mac(self, mac: str) -> str:
        """Format MAC address to standard format"""
        # Remove any separators
        mac = mac.replace(':', '').replace('-', '').upper()
        
        # Add colons
        if len(mac) == 12:
            return ':'.join(mac[i:i+2] for i in range(0, 12, 2))
        
        return mac
    
    def get_gateway_subdevices(self, gateway_id: str) -> List[Dict[str, Any]]:
        """
        Get sub-devices for a gateway
        
        Args:
            gateway_id: Gateway device ID
            
        Returns:
            List of sub-device info dicts
        """
        devices = self.get_devices()
        subdevices = []
        
        for device in devices:
            if device.get('parent_id') == gateway_id:
                subdevices.append(device)
        
        logger.info(f"Found {len(subdevices)} sub-devices for gateway {gateway_id}")
        return subdevices
    
    def refresh_device_info(self, device_id: str) -> Optional[Dict[str, Any]]:
        """
        Refresh device info from cloud
        
        Args:
            device_id: Device ID
            
        Returns:
            Updated device info or None
        """
        # Force refresh all devices
        devices = self.get_devices(force_refresh=True)
        
        # Find the specific device
        for device in devices:
            if device.get('did') == device_id:
                return device
        
        return None