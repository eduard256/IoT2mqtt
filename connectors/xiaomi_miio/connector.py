"""
Xiaomi MiIO Connector Implementation
Complete integration for ALL Xiaomi MiIO devices
Replicates full functionality from Home Assistant xiaomi_miio integration
"""

import asyncio
import time
import logging
import socket
import threading
from typing import Dict, Any, List, Optional, Union
from datetime import datetime, timedelta
from functools import partial

# Import base connector from shared
import sys
from pathlib import Path
sys.path.insert(0, '/app/shared')
from base_connector import BaseConnector

# Import python-miio library
try:
    from miio import (
        Device as MiioDevice,
        DeviceException,
        AirFresh,
        AirFreshA1,
        AirFreshT2017,
        AirHumidifier,
        AirHumidifierMiot,
        AirHumidifierMjjsq,
        AirPurifier,
        AirPurifierMiot,
        Fan,
        Fan1C,
        FanMiot,
        FanP5,
        FanZA5,
        Ceil,
        PhilipsBulb,
        PhilipsEyecare,
        PhilipsMoonlight,
        ChuangmiPlug,
        PowerStrip,
        RoborockVacuum,
        Gateway,
        discovery
    )
    from miio.exceptions import DeviceException
    from miio.miot_device import MiotDevice
except ImportError:
    logger.error("python-miio library not installed. Please add 'python-miio' to requirements.txt")
    raise

# Import handlers
from .device_registry import DeviceRegistry, get_device_class
from .coordinators import VacuumCoordinator, DeviceCoordinator
from .command_translator import CommandTranslator
from .discovery import XiaomiDiscovery
from .cloud_client import MiCloudClient

logger = logging.getLogger(__name__)

# Constants from Home Assistant integration
POLLING_TIMEOUT_SEC = 10
UPDATE_INTERVAL = 15  # seconds
LAZY_DISCOVER_FOR_MODEL = {
    "zhimi.fan.za3": True,
    "zhimi.fan.za5": True,
    "zhimi.airpurifier.za1": True,
    "dmaker.fan.1c": True,
}

class Connector(BaseConnector):
    """
    Xiaomi MiIO connector implementation
    
    Provides complete support for ALL Xiaomi MiIO devices:
    - Vacuums (Roborock, Rockrobo)
    - Air Purifiers (Zhimi)
    - Fans (Dmaker, Zhimi)
    - Humidifiers (Zhimi, Deerma)
    - Lights (Philips)
    - Switches (Chuangmi)
    - Gateways (Lumi)
    """
    
    def __init__(self, config_path: str = None, instance_name: str = None):
        """Initialize connector"""
        super().__init__(config_path, instance_name)
        
        # Store device connections
        self.device_connections = {}
        self.device_coordinators = {}
        
        # Device registry
        self.registry = DeviceRegistry()
        
        # Command translator
        self.translator = CommandTranslator()
        
        # Discovery
        self.discovery_enabled = self.config.get('discovery_enabled', True)
        self.discovery_interval = self.config.get('discovery_interval', 300)
        self.last_discovery = 0
        self.discovery_handler = XiaomiDiscovery()
        
        # Cloud client
        self.cloud_client = None
        cloud_config = self.config.get('cloud_credentials', {})
        if cloud_config.get('username') and cloud_config.get('password'):
            self.cloud_client = MiCloudClient(
                cloud_config['username'],
                cloud_config['password'],
                cloud_config.get('country', 'cn')
            )
        
        # Update interval override
        self.update_interval = self.config.get('update_interval', UPDATE_INTERVAL)
        
        logger.info(f"Xiaomi MiIO Connector initialized for {self.instance_id}")
    
    def initialize_connection(self):
        """
        Initialize connection to Xiaomi MiIO devices
        """
        logger.info("Initializing connection to Xiaomi MiIO devices...")
        
        # Initialize device connections
        for device_config in self.config.get('devices', []):
            device_id = device_config['device_id']
            
            if not device_config.get('enabled', True):
                logger.info(f"Device {device_id} is disabled, skipping")
                continue
            
            try:
                # Get device parameters
                host = device_config.get('host')
                token = device_config.get('token')
                model = device_config.get('model')
                
                if not host or not token:
                    logger.warning(f"Missing host or token for device {device_id}, skipping")
                    continue
                
                # Check if lazy discover is needed
                lazy_discover = LAZY_DISCOVER_FOR_MODEL.get(model, False)
                
                # Create device instance based on model
                device = self._create_device_instance(host, token, model, lazy_discover)
                
                if device:
                    # Test connection
                    try:
                        info = device.info()
                        logger.info(f"Connected to {model} at {host}: {info.model} v{info.firmware_version}")
                        
                        # Store connection
                        self.device_connections[device_id] = {
                            "device": device,
                            "config": device_config,
                            "model": model,
                            "info": info,
                            "last_state": None,
                            "error_count": 0
                        }
                        
                        # Create coordinator based on device type
                        coordinator = self._create_coordinator(device, model)
                        if coordinator:
                            self.device_coordinators[device_id] = coordinator
                            coordinator.start()
                        
                        # Publish device info
                        self._publish_device_info(device_id, info, model)
                        
                    except DeviceException as e:
                        if getattr(e, "code", None) == -9999:
                            # Retry once for network issues
                            logger.warning(f"Network issue with {device_id}, retrying...")
                            time.sleep(1)
                            try:
                                info = device.info()
                                self.device_connections[device_id] = {
                                    "device": device,
                                    "config": device_config,
                                    "model": model,
                                    "info": info,
                                    "last_state": None,
                                    "error_count": 0
                                }
                            except Exception as retry_error:
                                logger.error(f"Failed to connect to {device_id} after retry: {retry_error}")
                        else:
                            raise
                
            except Exception as e:
                logger.error(f"Failed to initialize device {device_id}: {e}")
                self.mqtt.publish_error(
                    device_id,
                    "INIT_ERROR",
                    str(e),
                    severity="error"
                )
    
    def cleanup_connection(self):
        """
        Clean up Xiaomi MiIO connections when stopping
        """
        logger.info("Cleaning up Xiaomi MiIO connections...")
        
        # Stop coordinators
        for coordinator in self.device_coordinators.values():
            coordinator.stop()
        
        # Close device connections
        for device_id, connection in self.device_connections.items():
            try:
                device = connection.get('device')
                if device:
                    # For vacuums, try to stop any ongoing operations
                    if isinstance(device, RoborockVacuum):
                        try:
                            device.stop()
                        except:
                            pass
                    logger.info(f"Disconnected Xiaomi device: {device_id}")
            except Exception as e:
                logger.error(f"Error disconnecting {device_id}: {e}")
        
        self.device_connections.clear()
        self.device_coordinators.clear()
    
    def get_device_state(self, device_id: str, device_config: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Get current state of a Xiaomi MiIO device
        """
        if device_id not in self.device_connections:
            logger.warning(f"Device {device_id} not connected")
            return None
        
        connection = self.device_connections[device_id]
        device = connection['device']
        model = connection['model']
        
        # Use coordinator if available
        if device_id in self.device_coordinators:
            coordinator = self.device_coordinators[device_id]
            state = coordinator.get_state()
            if state:
                return self._format_state_for_mqtt(state, model)
        
        try:
            # Get state based on device type
            state = self._get_device_state_by_type(device, model)
            
            if state:
                # Reset error count on success
                connection['error_count'] = 0
                connection['last_state'] = state
                return self._format_state_for_mqtt(state, model)
            
        except DeviceException as e:
            connection['error_count'] += 1
            
            # Handle -9999 error with retry
            if getattr(e, "code", None) == -9999 and connection['error_count'] < 2:
                logger.warning(f"Network issue getting state for {device_id}, retrying...")
                time.sleep(1)
                try:
                    state = self._get_device_state_by_type(device, model)
                    if state:
                        connection['error_count'] = 0
                        connection['last_state'] = state
                        return self._format_state_for_mqtt(state, model)
                except:
                    pass
            
            logger.error(f"Device error getting state for {device_id}: {e}")
            return {'online': False, 'error': str(e), 'last_update': datetime.now().isoformat()}
            
        except Exception as e:
            logger.error(f"Error getting state for {device_id}: {e}")
            self.mqtt.publish_error(
                device_id,
                "STATE_ERROR",
                str(e),
                severity="warning"
            )
            return None
    
    def set_device_state(self, device_id: str, device_config: Dict[str, Any], 
                        state: Dict[str, Any]) -> bool:
        """
        Set Xiaomi MiIO device state
        """
        logger.info(f"Setting state for {device_id}: {state}")
        
        if device_id not in self.device_connections:
            logger.warning(f"Device {device_id} not connected")
            return False
        
        connection = self.device_connections[device_id]
        device = connection['device']
        model = connection['model']
        
        try:
            # Translate MQTT commands to MiIO commands
            commands = self.translator.translate_to_miio(state, model)
            
            # Execute commands
            for cmd_name, cmd_args in commands:
                try:
                    # Get method from device
                    if hasattr(device, cmd_name):
                        method = getattr(device, cmd_name)
                        
                        # Call with or without arguments
                        if cmd_args is not None:
                            if isinstance(cmd_args, dict):
                                result = method(**cmd_args)
                            elif isinstance(cmd_args, (list, tuple)):
                                result = method(*cmd_args)
                            else:
                                result = method(cmd_args)
                        else:
                            result = method()
                        
                        logger.info(f"Executed {cmd_name} on {device_id}: {result}")
                    else:
                        # Try raw command
                        if cmd_name == "raw_command":
                            result = device.raw_command(cmd_args['command'], cmd_args.get('params'))
                            logger.info(f"Executed raw command on {device_id}: {result}")
                        else:
                            logger.warning(f"Method {cmd_name} not found on {model}")
                            
                except DeviceException as e:
                    if getattr(e, "code", None) == -9999:
                        # Retry once for network issues
                        logger.warning(f"Network issue executing {cmd_name}, retrying...")
                        time.sleep(1)
                        try:
                            if hasattr(device, cmd_name):
                                method = getattr(device, cmd_name)
                                if cmd_args is not None:
                                    if isinstance(cmd_args, dict):
                                        result = method(**cmd_args)
                                    else:
                                        result = method(cmd_args)
                                else:
                                    result = method()
                        except:
                            raise
                    else:
                        raise
            
            # Get and publish updated state
            time.sleep(0.5)
            new_state = self.get_device_state(device_id, device_config)
            if new_state:
                self.mqtt.publish_state(device_id, new_state)
            
            return True
            
        except Exception as e:
            logger.error(f"Error setting state for {device_id}: {e}")
            self.mqtt.publish_error(
                device_id,
                "COMMAND_ERROR",
                str(e),
                severity="error"
            )
            return False
    
    def discover_devices(self) -> List[Dict[str, Any]]:
        """
        Discover Xiaomi MiIO devices on the network
        """
        if not self.discovery_enabled:
            return []
        
        # Check discovery interval
        current_time = time.time()
        if current_time - self.last_discovery < self.discovery_interval:
            return []
        
        self.last_discovery = current_time
        discovered = []
        
        try:
            logger.info("Starting Xiaomi MiIO device discovery...")
            
            # Use python-miio discovery
            devices = discovery.scan(timeout=5)
            
            for info in devices:
                # Check if device is already configured
                already_configured = False
                for device in self.config.get('devices', []):
                    if device.get('host') == info.ip:
                        already_configured = True
                        break
                
                if not already_configured and info.token:
                    device_info = {
                        "device_id": f"xiaomi_{info.ip.replace('.', '_')}",
                        "host": info.ip,
                        "token": info.token,
                        "model": info.model or "unknown",
                        "name": f"Xiaomi {info.model or 'Device'}",
                        "ssid": info.ssid,
                        "mac": info.mac_address
                    }
                    discovered.append(device_info)
                    logger.info(f"Discovered Xiaomi device: {device_info['name']} at {info.ip}")
            
            # Try cloud discovery if available
            if self.cloud_client:
                try:
                    cloud_devices = self.cloud_client.get_devices()
                    for cloud_device in cloud_devices:
                        if cloud_device['localip'] and cloud_device['token']:
                            # Check if already discovered locally
                            already_found = False
                            for d in discovered:
                                if d['host'] == cloud_device['localip']:
                                    already_found = True
                                    break
                            
                            if not already_found:
                                device_info = {
                                    "device_id": f"xiaomi_{cloud_device['did']}",
                                    "host": cloud_device['localip'],
                                    "token": cloud_device['token'],
                                    "model": cloud_device['model'],
                                    "name": cloud_device['name'],
                                    "mac": cloud_device.get('mac')
                                }
                                discovered.append(device_info)
                                logger.info(f"Discovered via cloud: {device_info['name']}")
                except Exception as e:
                    logger.warning(f"Cloud discovery failed: {e}")
            
        except Exception as e:
            logger.error(f"Error during device discovery: {e}")
        
        # Publish discovered devices if any
        if discovered:
            self.mqtt.publish_discovered(discovered)
            logger.info(f"Discovered {len(discovered)} new Xiaomi MiIO devices")
        
        return discovered
    
    # === Device Creation Methods ===
    
    def _create_device_instance(self, host: str, token: str, model: str, lazy_discover: bool = False) -> Optional[MiioDevice]:
        """
        Create appropriate device instance based on model
        Exact implementation from Home Assistant
        """
        try:
            # Get device class from registry
            device_class = get_device_class(model)
            
            if device_class:
                # Special handling for specific device types
                if device_class == RoborockVacuum:
                    # Vacuums don't support lazy_discover yet
                    return device_class(host, token)
                elif device_class in [AirHumidifierMiot, AirHumidifierMjjsq]:
                    return device_class(host, token, lazy_discover=lazy_discover, model=model)
                elif device_class == Gateway:
                    return device_class(host, token)
                else:
                    # Most devices support lazy_discover
                    return device_class(host, token, lazy_discover=lazy_discover)
            else:
                # Unknown model, use generic device
                logger.warning(f"Unknown model {model}, using generic MiioDevice")
                return MiioDevice(host, token, lazy_discover=lazy_discover)
                
        except Exception as e:
            logger.error(f"Failed to create device instance for {model}: {e}")
            return None
    
    def _create_coordinator(self, device: MiioDevice, model: str) -> Optional[DeviceCoordinator]:
        """
        Create appropriate coordinator based on device type
        """
        try:
            if isinstance(device, RoborockVacuum):
                return VacuumCoordinator(device, self.update_interval)
            else:
                return DeviceCoordinator(device, self.update_interval)
        except Exception as e:
            logger.error(f"Failed to create coordinator for {model}: {e}")
            return None
    
    def _get_device_state_by_type(self, device: MiioDevice, model: str) -> Optional[Dict[str, Any]]:
        """
        Get device state based on device type
        """
        state = {}
        
        # Get status based on device type
        if isinstance(device, RoborockVacuum):
            # Vacuum specific state
            status = device.status()
            state = {
                'state': status.state,
                'state_code': status.state_code,
                'battery': status.battery,
                'fan_speed': status.fanspeed,
                'error': status.error if status.got_error else None,
                'cleaning_time': status.clean_time,
                'cleaned_area': status.clean_area,
                'dnd_enabled': status.dnd,
                'map_present': status.map_present,
                'in_cleaning': status.is_on,
                'is_charging': status.is_charging,
                'is_paused': status.is_paused
            }
            
            # Add consumables
            try:
                consumables = device.consumable_status()
                state['consumables'] = {
                    'main_brush': consumables.main_brush,
                    'main_brush_left': consumables.main_brush_left,
                    'side_brush': consumables.side_brush,
                    'side_brush_left': consumables.side_brush_left,
                    'filter': consumables.filter,
                    'filter_left': consumables.filter_left,
                    'sensor_dirty': consumables.sensor_dirty,
                    'sensor_dirty_left': consumables.sensor_dirty_left
                }
            except:
                pass
                
        elif isinstance(device, (AirPurifier, AirPurifierMiot)):
            # Air purifier state
            status = device.status()
            state = {
                'power': status.is_on,
                'aqi': status.aqi,
                'mode': status.mode.value if hasattr(status.mode, 'value') else str(status.mode),
                'humidity': status.humidity,
                'temperature': status.temperature,
                'fan_speed': status.fan_speed,
                'filter_life_remaining': status.filter_life_remaining,
                'filter_hours_used': status.filter_hours_used,
                'buzzer': status.buzzer,
                'child_lock': status.child_lock,
                'led': status.led,
                'led_brightness': getattr(status, 'led_brightness', None),
                'favorite_level': getattr(status, 'favorite_level', None),
                'motor_speed': getattr(status, 'motor_speed', None)
            }
            
        elif isinstance(device, (AirHumidifier, AirHumidifierMiot, AirHumidifierMjjsq)):
            # Humidifier state
            status = device.status()
            state = {
                'power': status.is_on,
                'mode': status.mode.value if hasattr(status.mode, 'value') else str(status.mode),
                'humidity': status.humidity,
                'target_humidity': status.target_humidity,
                'temperature': status.temperature,
                'water_level': getattr(status, 'water_level', None),
                'buzzer': status.buzzer,
                'child_lock': getattr(status, 'child_lock', None),
                'led': getattr(status, 'led', None),
                'led_brightness': getattr(status, 'led_brightness', None),
                'dry': getattr(status, 'dry', None),
                'use_time': getattr(status, 'use_time', None)
            }
            
        elif isinstance(device, (Fan, Fan1C, FanMiot, FanP5, FanZA5)):
            # Fan state
            status = device.status()
            state = {
                'power': status.is_on,
                'speed': status.speed,
                'angle': status.angle,
                'oscillate': status.oscillate,
                'natural_mode': getattr(status, 'natural_speed', 0) > 0,
                'buzzer': status.buzzer,
                'child_lock': status.child_lock,
                'led': getattr(status, 'led', None),
                'led_brightness': getattr(status, 'led_brightness', None),
                'delay_off_countdown': status.delay_off_countdown,
                'battery': getattr(status, 'battery', None),
                'battery_charge': getattr(status, 'battery_charge', None),
                'battery_state': getattr(status, 'battery_state', None),
                'ionizer': getattr(status, 'ionizer', None)
            }
            
        elif isinstance(device, (Ceil, PhilipsBulb, PhilipsEyecare, PhilipsMoonlight)):
            # Light state
            status = device.status()
            state = {
                'power': status.is_on,
                'brightness': status.brightness,
                'color_temperature': status.color_temperature,
                'scene': getattr(status, 'scene', None),
                'delay_off_countdown': getattr(status, 'delay_off_countdown', None)
            }
            
            # Add RGB for color bulbs
            if hasattr(status, 'rgb'):
                rgb = status.rgb
                if rgb:
                    state['rgb'] = {'r': rgb[0], 'g': rgb[1], 'b': rgb[2]}
                    state['hex_color'] = f"#{rgb[0]:02x}{rgb[1]:02x}{rgb[2]:02x}"
                    
        elif isinstance(device, (ChuangmiPlug, PowerStrip)):
            # Switch/plug state
            status = device.status()
            state = {
                'power': status.is_on,
                'temperature': status.temperature,
                'load_power': getattr(status, 'load_power', None),
                'wifi_led': getattr(status, 'wifi_led', None),
                'power_mode': getattr(status, 'mode', None)
            }
            
            # PowerStrip has multiple channels
            if isinstance(device, PowerStrip):
                state['channels'] = {
                    'usb': status.usb_power,
                    'socket': status.is_on
                }
                
        elif isinstance(device, Gateway):
            # Gateway state
            status = device.status()
            state = {
                'illumination': status.illumination,
                'rgb': status.rgb,
                'devices': []
            }
            
            # Add sub-devices
            for sub_device in device.devices.values():
                state['devices'].append({
                    'sid': sub_device.sid,
                    'model': sub_device.model,
                    'name': sub_device.name,
                    'status': sub_device.status
                })
        else:
            # Generic device - try to get basic status
            try:
                status = device.status()
                # Convert status attributes to dict
                if hasattr(status, '__dict__'):
                    state = {k: v for k, v in status.__dict__.items() if not k.startswith('_')}
                else:
                    state = {'status': str(status)}
            except:
                state = {'online': True}
        
        # Add common fields
        state['online'] = True
        state['model'] = model
        state['last_update'] = datetime.now().isoformat()
        
        return state
    
    def _format_state_for_mqtt(self, state: Dict[str, Any], model: str) -> Dict[str, Any]:
        """
        Format device state for MQTT according to IoT2MQTT standards
        """
        formatted = {
            'online': state.get('online', True),
            'last_update': state.get('last_update', datetime.now().isoformat())
        }
        
        # Map device-specific states to standard IoT2MQTT format
        if 'power' in state:
            formatted['power'] = state['power']
        if 'brightness' in state:
            formatted['brightness'] = state['brightness']
        if 'color_temperature' in state:
            formatted['color_temp'] = state['color_temperature']
        if 'rgb' in state:
            formatted['color'] = state['rgb']
        if 'hex_color' in state:
            formatted['hex_color'] = state['hex_color']
        if 'mode' in state:
            formatted['mode'] = state['mode']
        if 'speed' in state:
            formatted['speed'] = state['speed']
        if 'fan_speed' in state:
            formatted['fan_speed'] = state['fan_speed']
        if 'humidity' in state:
            formatted['humidity'] = state['humidity']
        if 'target_humidity' in state:
            formatted['target_humidity'] = state['target_humidity']
        if 'temperature' in state:
            formatted['temperature'] = state['temperature']
        if 'aqi' in state:
            formatted['air_quality'] = state['aqi']
        if 'battery' in state:
            formatted['battery'] = state['battery']
        if 'state' in state:
            formatted['activity'] = state['state']
        if 'error' in state:
            formatted['error'] = state['error']
        if 'oscillate' in state:
            formatted['oscillation'] = state['oscillate']
        if 'angle' in state:
            formatted['oscillation_angle'] = state['angle']
        if 'child_lock' in state:
            formatted['child_lock'] = state['child_lock']
        if 'buzzer' in state:
            formatted['buzzer'] = state['buzzer']
        if 'led' in state:
            formatted['led'] = state['led']
        if 'led_brightness' in state:
            formatted['led_brightness'] = state['led_brightness']
        
        # Add device-specific attributes
        formatted['attributes'] = {}
        
        # Vacuum specific
        if 'consumables' in state:
            formatted['attributes']['consumables'] = state['consumables']
        if 'cleaning_time' in state:
            formatted['attributes']['cleaning_time'] = state['cleaning_time']
        if 'cleaned_area' in state:
            formatted['attributes']['cleaned_area'] = state['cleaned_area']
        if 'dnd_enabled' in state:
            formatted['attributes']['dnd_enabled'] = state['dnd_enabled']
        if 'map_present' in state:
            formatted['attributes']['map_present'] = state['map_present']
        
        # Air quality
        if 'filter_life_remaining' in state:
            formatted['attributes']['filter_life'] = state['filter_life_remaining']
        if 'filter_hours_used' in state:
            formatted['attributes']['filter_hours'] = state['filter_hours_used']
        
        # Fan
        if 'natural_mode' in state:
            formatted['attributes']['natural_mode'] = state['natural_mode']
        if 'delay_off_countdown' in state:
            formatted['attributes']['timer'] = state['delay_off_countdown']
        if 'ionizer' in state:
            formatted['attributes']['ionizer'] = state['ionizer']
        
        # Water level for humidifiers
        if 'water_level' in state:
            formatted['attributes']['water_level'] = state['water_level']
        if 'dry' in state:
            formatted['attributes']['dry_mode'] = state['dry']
        
        # Power monitoring
        if 'load_power' in state:
            formatted['attributes']['power_load'] = state['load_power']
        if 'power_mode' in state:
            formatted['attributes']['power_mode'] = state['power_mode']
        
        # Gateway
        if 'illumination' in state:
            formatted['attributes']['illumination'] = state['illumination']
        if 'devices' in state:
            formatted['attributes']['sub_devices'] = state['devices']
        
        # Model info
        formatted['model'] = model
        
        return formatted
    
    def _publish_device_info(self, device_id: str, info: Any, model: str):
        """
        Publish device information to MQTT
        """
        device_info = {
            'model': model,
            'firmware_version': info.firmware_version,
            'hardware_version': info.hardware_version,
            'mac_address': info.mac_address if hasattr(info, 'mac_address') else None,
            'capabilities': self.registry.get_capabilities(model)
        }
        
        self.mqtt.publish_meta(device_id, 'info', device_info)