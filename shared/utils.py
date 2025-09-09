"""
Utility functions for IoT2MQTT
"""

import os
import json
import hashlib
import base64
from typing import Any, Dict, List, Optional
from datetime import datetime, timedelta
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

def load_env_file(env_path: str = ".env") -> Dict[str, str]:
    """
    Load environment variables from .env file
    
    Args:
        env_path: Path to .env file
        
    Returns:
        Dictionary of environment variables
    """
    env_vars = {}
    
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    if '=' in line:
                        key, value = line.split('=', 1)
                        env_vars[key.strip()] = value.strip()
    
    return env_vars

def encrypt_password(password: str, key: str = None) -> str:
    """
    Simple password encryption (for basic protection)
    In production, use proper encryption like Fernet
    
    Args:
        password: Password to encrypt
        key: Encryption key (uses default if not provided)
        
    Returns:
        Encrypted password as base64 string
    """
    if not key:
        key = os.getenv('ENCRYPTION_KEY', 'default_key_change_me')
    
    # Simple XOR encryption (NOT secure, just obfuscation)
    # In production, use cryptography.fernet or similar
    encrypted = []
    for i, char in enumerate(password):
        key_char = key[i % len(key)]
        encrypted.append(chr(ord(char) ^ ord(key_char)))
    
    return base64.b64encode(''.join(encrypted).encode()).decode()

def decrypt_password(encrypted: str, key: str = None) -> str:
    """
    Decrypt password
    
    Args:
        encrypted: Encrypted password as base64 string
        key: Decryption key
        
    Returns:
        Decrypted password
    """
    if not key:
        key = os.getenv('ENCRYPTION_KEY', 'default_key_change_me')
    
    decoded = base64.b64decode(encrypted.encode()).decode()
    
    decrypted = []
    for i, char in enumerate(decoded):
        key_char = key[i % len(key)]
        decrypted.append(chr(ord(char) ^ ord(key_char)))
    
    return ''.join(decrypted)

def validate_instance_name(name: str) -> bool:
    """
    Validate instance name
    
    Args:
        name: Instance name to validate
        
    Returns:
        True if valid, False otherwise
    """
    if not name:
        return False
    
    # Must be alphanumeric with underscores, no spaces
    if not name.replace('_', '').replace('-', '').isalnum():
        return False
    
    # Must not start with number
    if name[0].isdigit():
        return False
    
    # Reasonable length
    if len(name) < 3 or len(name) > 50:
        return False
    
    return True

def validate_mqtt_topic(topic: str) -> bool:
    """
    Validate MQTT topic
    
    Args:
        topic: MQTT topic to validate
        
    Returns:
        True if valid, False otherwise
    """
    if not topic:
        return False
    
    # Check for invalid characters
    invalid_chars = ['#', '+', '\0']
    for char in invalid_chars:
        if char in topic:
            # # and + are valid as wildcards but not in normal topics
            if char in ['#', '+']:
                # Check if used correctly as wildcards
                parts = topic.split('/')
                for part in parts:
                    if char in part and part != char:
                        return False
            else:
                return False
    
    # Must not start or end with /
    if topic.startswith('/') or topic.endswith('/'):
        return False
    
    # No double slashes
    if '//' in topic:
        return False
    
    return True

def parse_device_class(device_model: str) -> str:
    """
    Try to determine device class from model name
    
    Args:
        device_model: Device model string
        
    Returns:
        Guessed device class
    """
    model_lower = device_model.lower()
    
    # Lights
    if any(word in model_lower for word in ['bulb', 'light', 'lamp', 'ceiling']):
        if 'color' in model_lower or 'rgb' in model_lower:
            return 'light.rgb'
        elif 'warm' in model_lower or 'temp' in model_lower:
            return 'light.color_temp'
        elif 'dim' in model_lower:
            return 'light.dimmable'
        else:
            return 'light.switch'
    
    # Climate
    elif any(word in model_lower for word in ['thermostat', 'heating', 'cooling']):
        return 'climate.thermostat'
    elif 'air' in model_lower and 'condition' in model_lower:
        return 'climate.ac'
    elif 'heater' in model_lower:
        return 'climate.heater'
    elif 'humidifier' in model_lower:
        return 'climate.humidifier'
    elif 'purifier' in model_lower:
        return 'climate.air_purifier'
    
    # Sensors
    elif 'motion' in model_lower:
        return 'sensor.motion'
    elif 'door' in model_lower or 'window' in model_lower or 'contact' in model_lower:
        return 'sensor.contact'
    elif 'temp' in model_lower:
        return 'sensor.temperature'
    elif 'humid' in model_lower:
        return 'sensor.humidity'
    elif 'energy' in model_lower or 'power' in model_lower:
        return 'sensor.energy'
    
    # Switches
    elif 'plug' in model_lower or 'outlet' in model_lower or 'socket' in model_lower:
        return 'switch.outlet'
    elif 'switch' in model_lower or 'relay' in model_lower:
        return 'switch.relay'
    
    # Security
    elif 'lock' in model_lower:
        return 'security.lock'
    elif 'camera' in model_lower:
        return 'security.camera'
    elif 'alarm' in model_lower:
        return 'security.alarm'
    
    # Media
    elif 'speaker' in model_lower or 'sound' in model_lower:
        return 'media.speaker'
    elif 'tv' in model_lower or 'television' in model_lower:
        return 'media.tv'
    
    # Appliances
    elif 'vacuum' in model_lower or 'robot' in model_lower:
        return 'appliance.vacuum'
    elif 'washer' in model_lower or 'washing' in model_lower:
        return 'appliance.washer'
    elif 'kettle' in model_lower:
        return 'appliance.kettle'
    
    # Default
    else:
        return 'switch.outlet'

def format_mac_address(mac: str) -> str:
    """
    Format MAC address to standard format
    
    Args:
        mac: MAC address in any format
        
    Returns:
        Formatted MAC address (XX:XX:XX:XX:XX:XX)
    """
    # Remove all separators
    mac_clean = mac.replace(':', '').replace('-', '').replace('.', '').upper()
    
    # Validate length
    if len(mac_clean) != 12:
        raise ValueError(f"Invalid MAC address length: {mac}")
    
    # Validate hex
    try:
        int(mac_clean, 16)
    except ValueError:
        raise ValueError(f"Invalid MAC address format: {mac}")
    
    # Format with colons
    return ':'.join(mac_clean[i:i+2] for i in range(0, 12, 2))

def parse_ip_address(ip: str) -> Optional[str]:
    """
    Validate and parse IP address
    
    Args:
        ip: IP address string
        
    Returns:
        Valid IP address or None
    """
    import socket
    
    try:
        # Try IPv4
        socket.inet_pton(socket.AF_INET, ip)
        return ip
    except socket.error:
        try:
            # Try IPv6
            socket.inet_pton(socket.AF_INET6, ip)
            return ip
        except socket.error:
            return None

def exponential_backoff(attempt: int, base_delay: float = 1.0, 
                        max_delay: float = 60.0) -> float:
    """
    Calculate exponential backoff delay
    
    Args:
        attempt: Attempt number (starting from 0)
        base_delay: Base delay in seconds
        max_delay: Maximum delay in seconds
        
    Returns:
        Delay in seconds
    """
    delay = base_delay * (2 ** attempt)
    return min(delay, max_delay)

def rate_limit(func=None, *, calls: int = 10, period: timedelta = timedelta(seconds=60)):
    """
    Rate limiting decorator
    
    Args:
        calls: Number of allowed calls
        period: Time period for the limit
    """
    def decorator(f):
        call_times = []
        
        def wrapper(*args, **kwargs):
            now = datetime.now()
            
            # Remove old calls outside the period
            nonlocal call_times
            call_times = [t for t in call_times if now - t < period]
            
            # Check rate limit
            if len(call_times) >= calls:
                oldest = call_times[0]
                wait_time = (oldest + period - now).total_seconds()
                raise Exception(f"Rate limit exceeded. Wait {wait_time:.1f} seconds")
            
            # Record this call
            call_times.append(now)
            
            # Execute function
            return f(*args, **kwargs)
        
        return wrapper
    
    if func is None:
        return decorator
    else:
        return decorator(func)

def chunk_list(lst: List[Any], chunk_size: int) -> List[List[Any]]:
    """
    Split list into chunks
    
    Args:
        lst: List to split
        chunk_size: Size of each chunk
        
    Returns:
        List of chunks
    """
    return [lst[i:i + chunk_size] for i in range(0, len(lst), chunk_size)]

def merge_dicts(dict1: Dict, dict2: Dict) -> Dict:
    """
    Deep merge two dictionaries
    
    Args:
        dict1: First dictionary
        dict2: Second dictionary (takes precedence)
        
    Returns:
        Merged dictionary
    """
    result = dict1.copy()
    
    for key, value in dict2.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = merge_dicts(result[key], value)
        else:
            result[key] = value
    
    return result

def sanitize_filename(filename: str) -> str:
    """
    Sanitize filename for safe filesystem usage
    
    Args:
        filename: Original filename
        
    Returns:
        Sanitized filename
    """
    # Remove invalid characters
    invalid_chars = '<>:"/\\|?*'
    for char in invalid_chars:
        filename = filename.replace(char, '_')
    
    # Remove control characters
    filename = ''.join(char for char in filename if ord(char) >= 32)
    
    # Limit length
    max_length = 255
    if len(filename) > max_length:
        name, ext = os.path.splitext(filename)
        filename = name[:max_length - len(ext)] + ext
    
    return filename

def get_timestamp() -> str:
    """
    Get current ISO format timestamp
    
    Returns:
        ISO format timestamp string
    """
    return datetime.now().isoformat()

def parse_timestamp(timestamp: str) -> Optional[datetime]:
    """
    Parse ISO format timestamp
    
    Args:
        timestamp: ISO format timestamp string
        
    Returns:
        datetime object or None if invalid
    """
    try:
        return datetime.fromisoformat(timestamp)
    except (ValueError, AttributeError):
        return None

def is_timestamp_outdated(timestamp: str, max_age_seconds: float = 30) -> bool:
    """
    Check if timestamp is outdated
    
    Args:
        timestamp: ISO format timestamp string
        max_age_seconds: Maximum age in seconds
        
    Returns:
        True if outdated, False otherwise
    """
    ts = parse_timestamp(timestamp)
    if not ts:
        return True
    
    age = (datetime.now() - ts).total_seconds()
    return age > max_age_seconds

class CircularBuffer:
    """Simple circular buffer for storing recent values"""
    
    def __init__(self, size: int):
        self.size = size
        self.buffer = []
        self.index = 0
    
    def add(self, value: Any):
        """Add value to buffer"""
        if len(self.buffer) < self.size:
            self.buffer.append(value)
        else:
            self.buffer[self.index] = value
            self.index = (self.index + 1) % self.size
    
    def get_all(self) -> List[Any]:
        """Get all values in order"""
        if len(self.buffer) < self.size:
            return self.buffer.copy()
        else:
            return self.buffer[self.index:] + self.buffer[:self.index]
    
    def get_latest(self, n: int = 1) -> List[Any]:
        """Get n latest values"""
        all_values = self.get_all()
        return all_values[-n:] if n <= len(all_values) else all_values
    
    def clear(self):
        """Clear buffer"""
        self.buffer = []
        self.index = 0