"""
Home Assistant MQTT Discovery generator for IoT2MQTT
Optional component for HA integration
"""

import json
import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, asdict

logger = logging.getLogger(__name__)

@dataclass
class DeviceInfo:
    """Device information for HA discovery"""
    identifiers: List[str]
    name: str
    model: str = "Unknown"
    manufacturer: str = "Unknown"
    sw_version: str = None
    hw_version: str = None
    via_device: str = None
    suggested_area: str = None

@dataclass
class EntityConfig:
    """Entity configuration for HA discovery"""
    platform: str  # light, switch, sensor, etc.
    unique_id: str
    name: str
    device: DeviceInfo
    state_topic: str
    command_topic: str = None
    availability_topic: str = None
    json_attributes_topic: str = None
    value_template: str = None
    command_template: str = None
    payload_on: str = None
    payload_off: str = None
    state_on: str = None
    state_off: str = None
    optimistic: bool = False
    qos: int = 1
    retain: bool = False

class DiscoveryGenerator:
    """Generate Home Assistant MQTT Discovery messages"""
    
    # Device class mappings
    DEVICE_CLASSES = {
        # Lights
        'light.switch': 'light',
        'light.dimmable': 'light',
        'light.color_temp': 'light',
        'light.rgb': 'light',
        'light.rgbw': 'light',
        
        # Climate
        'climate.thermostat': 'climate',
        'climate.ac': 'climate',
        'climate.heater': 'climate',
        'climate.humidifier': 'humidifier',
        'climate.air_purifier': 'fan',
        
        # Sensors
        'sensor.temperature': 'sensor',
        'sensor.humidity': 'sensor',
        'sensor.motion': 'binary_sensor',
        'sensor.contact': 'binary_sensor',
        'sensor.energy': 'sensor',
        'sensor.air_quality': 'sensor',
        
        # Switches
        'switch.outlet': 'switch',
        'switch.relay': 'switch',
        'switch.wall': 'switch',
        
        # Security
        'security.lock': 'lock',
        'security.camera': 'camera',
        'security.alarm': 'alarm_control_panel',
        
        # Media
        'media.speaker': 'media_player',
        'media.tv': 'media_player',
        
        # Appliances
        'appliance.vacuum': 'vacuum',
        'appliance.washer': 'switch',
        'appliance.kettle': 'switch',
    }
    
    def __init__(self, base_topic: str = "IoT2mqtt", 
                 discovery_prefix: str = "homeassistant",
                 instance_id: str = None):
        """
        Initialize discovery generator
        
        Args:
            base_topic: IoT2MQTT base topic
            discovery_prefix: HA discovery prefix
            instance_id: Instance identifier
        """
        self.base_topic = base_topic
        self.discovery_prefix = discovery_prefix
        self.instance_id = instance_id
    
    def generate_device_discovery(self, device_id: str, device_config: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Generate discovery messages for a device
        
        Args:
            device_id: Device identifier
            device_config: Device configuration
            
        Returns:
            List of discovery configurations
        """
        discoveries = []
        
        # Get device class
        device_class = device_config.get('class', 'switch.outlet')
        ha_platform = self.DEVICE_CLASSES.get(device_class, 'switch')
        
        # Create device info
        global_id = f"{self.instance_id}_{device_id}" if self.instance_id else device_id
        
        device_info = DeviceInfo(
            identifiers=[global_id],
            name=device_config.get('friendly_name', device_id),
            model=device_config.get('model', 'Generic Device'),
            manufacturer=device_config.get('manufacturer', 'Unknown'),
            via_device=self.instance_id,
            suggested_area=device_config.get('area')
        )
        
        # Base topics
        state_topic = f"{self.base_topic}/v1/instances/{self.instance_id}/devices/{device_id}/state"
        command_topic = f"{self.base_topic}/v1/instances/{self.instance_id}/devices/{device_id}/cmd"
        availability_topic = f"{self.base_topic}/v1/instances/{self.instance_id}/devices/{device_id}/availability"
        
        # Generate entities based on capabilities
        capabilities = device_config.get('capabilities', {})
        
        if ha_platform == 'light':
            discoveries.append(self._generate_light_discovery(
                device_id, device_info, state_topic, command_topic, 
                availability_topic, capabilities
            ))
        elif ha_platform == 'switch':
            discoveries.append(self._generate_switch_discovery(
                device_id, device_info, state_topic, command_topic,
                availability_topic, capabilities
            ))
        elif ha_platform == 'sensor':
            discoveries.extend(self._generate_sensor_discoveries(
                device_id, device_info, state_topic, capabilities
            ))
        elif ha_platform == 'binary_sensor':
            discoveries.append(self._generate_binary_sensor_discovery(
                device_id, device_info, state_topic, availability_topic,
                device_class, capabilities
            ))
        elif ha_platform == 'climate':
            discoveries.append(self._generate_climate_discovery(
                device_id, device_info, state_topic, command_topic,
                availability_topic, capabilities
            ))
        elif ha_platform == 'fan':
            discoveries.append(self._generate_fan_discovery(
                device_id, device_info, state_topic, command_topic,
                availability_topic, capabilities
            ))
        elif ha_platform == 'camera':
            # For cameras, extract stream URLs from device_config
            stream_urls = device_config.get('stream_urls', {})
            discoveries.append(self._generate_camera_discovery(
                device_id, device_info, state_topic, stream_urls
            ))

        return discoveries
    
    def _generate_light_discovery(self, device_id: str, device_info: DeviceInfo,
                                 state_topic: str, command_topic: str,
                                 availability_topic: str, capabilities: Dict) -> Dict:
        """Generate light discovery configuration"""
        global_id = f"{self.instance_id}_{device_id}" if self.instance_id else device_id
        
        config = {
            "unique_id": f"{global_id}_light",
            "name": device_info.name,
            "device": self._device_info_to_dict(device_info),
            "state_topic": state_topic,
            "command_topic": command_topic,
            "availability_topic": availability_topic,
            "json_attributes_topic": state_topic,
            "schema": "json",
            "brightness": capabilities.get('brightness', {}).get('settable', False),
            "color_mode": True,
            "supported_color_modes": []
        }
        
        # Determine supported color modes
        if capabilities.get('brightness', {}).get('settable'):
            config["supported_color_modes"].append("brightness")
        if capabilities.get('color_temp', {}).get('settable'):
            config["supported_color_modes"].append("color_temp")
        if capabilities.get('color', {}).get('settable'):
            config["supported_color_modes"].append("rgb")
        
        if not config["supported_color_modes"]:
            config["supported_color_modes"] = ["onoff"]
        
        return {
            "topic": f"{self.discovery_prefix}/light/{global_id}/config",
            "payload": config,
            "retain": True
        }
    
    def _generate_switch_discovery(self, device_id: str, device_info: DeviceInfo,
                                  state_topic: str, command_topic: str,
                                  availability_topic: str, capabilities: Dict) -> Dict:
        """Generate switch discovery configuration"""
        global_id = f"{self.instance_id}_{device_id}" if self.instance_id else device_id
        
        config = {
            "unique_id": f"{global_id}_switch",
            "name": device_info.name,
            "device": self._device_info_to_dict(device_info),
            "state_topic": state_topic,
            "command_topic": command_topic,
            "availability_topic": availability_topic,
            "value_template": "{{ value_json.state.power }}",
            "payload_on": json.dumps({"values": {"power": True}}),
            "payload_off": json.dumps({"values": {"power": False}}),
            "state_on": "true",
            "state_off": "false"
        }
        
        return {
            "topic": f"{self.discovery_prefix}/switch/{global_id}/config",
            "payload": config,
            "retain": True
        }
    
    def _generate_sensor_discoveries(self, device_id: str, device_info: DeviceInfo,
                                    state_topic: str, capabilities: Dict) -> List[Dict]:
        """Generate sensor discovery configurations"""
        discoveries = []
        global_id = f"{self.instance_id}_{device_id}" if self.instance_id else device_id
        
        # Map capability names to sensor types
        sensor_mappings = {
            'temperature': ('temperature', '°C', 'temperature'),
            'humidity': ('humidity', '%', 'humidity'),
            'pressure': ('pressure', 'hPa', 'pressure'),
            'illuminance': ('illuminance', 'lx', 'illuminance'),
            'aqi': ('aqi', 'AQI', None),
            'pm25': ('pm25', 'µg/m³', 'pm25'),
            'co2': ('carbon_dioxide', 'ppm', 'carbon_dioxide'),
            'power': ('power', 'W', 'power'),
            'energy': ('energy', 'kWh', 'energy'),
            'voltage': ('voltage', 'V', 'voltage'),
            'current': ('current', 'A', 'current')
        }
        
        for capability, (device_class, unit, icon) in sensor_mappings.items():
            if capability in capabilities and not capabilities[capability].get('settable', False):
                config = {
                    "unique_id": f"{global_id}_{capability}",
                    "name": f"{device_info.name} {capability.capitalize()}",
                    "device": self._device_info_to_dict(device_info),
                    "state_topic": state_topic,
                    "value_template": f"{{{{ value_json.state.{capability} }}}}",
                    "unit_of_measurement": unit,
                    "device_class": device_class
                }
                
                if icon:
                    config["icon"] = f"mdi:{icon}"
                
                discoveries.append({
                    "topic": f"{self.discovery_prefix}/sensor/{global_id}_{capability}/config",
                    "payload": config,
                    "retain": True
                })
        
        return discoveries
    
    def _generate_binary_sensor_discovery(self, device_id: str, device_info: DeviceInfo,
                                         state_topic: str, availability_topic: str,
                                         device_class: str, capabilities: Dict) -> Dict:
        """Generate binary sensor discovery configuration"""
        global_id = f"{self.instance_id}_{device_id}" if self.instance_id else device_id
        
        # Determine the property name and device class
        if 'motion' in device_class:
            property_name = 'motion'
            ha_device_class = 'motion'
        elif 'contact' in device_class:
            property_name = 'contact'
            ha_device_class = 'door'
        else:
            property_name = 'state'
            ha_device_class = None
        
        config = {
            "unique_id": f"{global_id}_binary",
            "name": device_info.name,
            "device": self._device_info_to_dict(device_info),
            "state_topic": state_topic,
            "availability_topic": availability_topic,
            "value_template": f"{{{{ value_json.state.{property_name} }}}}",
            "payload_on": "true",
            "payload_off": "false"
        }
        
        if ha_device_class:
            config["device_class"] = ha_device_class
        
        return {
            "topic": f"{self.discovery_prefix}/binary_sensor/{global_id}/config",
            "payload": config,
            "retain": True
        }
    
    def _generate_climate_discovery(self, device_id: str, device_info: DeviceInfo,
                                  state_topic: str, command_topic: str,
                                  availability_topic: str, capabilities: Dict) -> Dict:
        """Generate climate discovery configuration"""
        global_id = f"{self.instance_id}_{device_id}" if self.instance_id else device_id
        
        config = {
            "unique_id": f"{global_id}_climate",
            "name": device_info.name,
            "device": self._device_info_to_dict(device_info),
            "current_temperature_topic": state_topic,
            "current_temperature_template": "{{ value_json.state.temperature }}",
            "mode_state_topic": state_topic,
            "mode_state_template": "{{ value_json.state.mode }}",
            "mode_command_topic": command_topic,
            "availability_topic": availability_topic,
            "modes": capabilities.get('mode', {}).get('options', ['auto', 'cool', 'heat', 'off']),
            "min_temp": capabilities.get('temperature', {}).get('min', 16),
            "max_temp": capabilities.get('temperature', {}).get('max', 30),
            "temp_step": capabilities.get('temperature', {}).get('step', 1)
        }
        
        if capabilities.get('target_temperature', {}).get('settable'):
            config["temperature_state_topic"] = state_topic
            config["temperature_state_template"] = "{{ value_json.state.target_temperature }}"
            config["temperature_command_topic"] = command_topic
        
        return {
            "topic": f"{self.discovery_prefix}/climate/{global_id}/config",
            "payload": config,
            "retain": True
        }
    
    def _generate_fan_discovery(self, device_id: str, device_info: DeviceInfo,
                               state_topic: str, command_topic: str,
                               availability_topic: str, capabilities: Dict) -> Dict:
        """Generate fan discovery configuration"""
        global_id = f"{self.instance_id}_{device_id}" if self.instance_id else device_id
        
        config = {
            "unique_id": f"{global_id}_fan",
            "name": device_info.name,
            "device": self._device_info_to_dict(device_info),
            "state_topic": state_topic,
            "command_topic": command_topic,
            "availability_topic": availability_topic,
            "state_value_template": "{{ value_json.state.power }}",
            "command_template": json.dumps({"values": {"power": "{{ value }}"}}),
            "payload_on": "true",
            "payload_off": "false"
        }
        
        if capabilities.get('speed', {}).get('settable'):
            config["percentage_state_topic"] = state_topic
            config["percentage_value_template"] = "{{ value_json.state.speed }}"
            config["percentage_command_topic"] = command_topic
            config["speed_range_min"] = capabilities['speed'].get('min', 1)
            config["speed_range_max"] = capabilities['speed'].get('max', 100)
        
        return {
            "topic": f"{self.discovery_prefix}/fan/{global_id}/config",
            "payload": config,
            "retain": True
        }

    def _generate_camera_discovery(self, device_id: str, device_info: DeviceInfo,
                                   state_topic: str, stream_urls: Dict[str, str]) -> Dict:
        """
        Generate camera discovery configuration

        Args:
            device_id: Camera device ID
            device_info: Device information
            state_topic: MQTT state topic
            stream_urls: Dict with stream URLs (must contain 'jpeg' and 'rtsp')

        Returns: Discovery message dict
        """
        global_id = f"{self.instance_id}_{device_id}" if self.instance_id else device_id

        config = {
            "unique_id": f"{global_id}_camera",
            "name": device_info.name,
            "device": self._device_info_to_dict(device_info),
            "topic": state_topic,
            "json_attributes_topic": state_topic,
        }

        # Add stream source (RTSP preferred for HA)
        if 'rtsp' in stream_urls:
            config["stream_source"] = stream_urls['rtsp']
        elif 'm3u8' in stream_urls:
            config["stream_source"] = stream_urls['m3u8']

        # Add still image URL (required for HA camera)
        if 'jpeg' in stream_urls:
            config["still_image_url"] = stream_urls['jpeg']

        return {
            "topic": f"{self.discovery_prefix}/camera/{global_id}/config",
            "payload": config,
            "retain": True
        }

    def _device_info_to_dict(self, device_info: DeviceInfo) -> Dict[str, Any]:
        """Convert DeviceInfo to dictionary, removing None values"""
        result = {}
        for key, value in asdict(device_info).items():
            if value is not None:
                result[key] = value
        return result
    
    def remove_discovery(self, device_id: str, device_class: str = None):
        """
        Generate messages to remove device from HA discovery
        
        Args:
            device_id: Device identifier
            device_class: Device class (optional)
            
        Returns:
            List of removal configurations
        """
        removals = []
        global_id = f"{self.instance_id}_{device_id}" if self.instance_id else device_id
        
        # If no device class specified, try common platforms
        if not device_class:
            platforms = ['light', 'switch', 'sensor', 'binary_sensor', 'climate', 'fan']
        else:
            ha_platform = self.DEVICE_CLASSES.get(device_class, 'switch')
            platforms = [ha_platform]
        
        for platform in platforms:
            topic = f"{self.discovery_prefix}/{platform}/{global_id}/config"
            removals.append({
                "topic": topic,
                "payload": "",  # Empty payload removes the device
                "retain": True
            })
        
        return removals