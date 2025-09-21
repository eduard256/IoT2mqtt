"""
Yeelight Connector Implementation
Direct connection to Yeelight bulbs without Home Assistant layers
"""

import time
import logging
import socket
from typing import Dict, Any, List, Optional
from datetime import datetime

# Import base connector from shared
import sys
from pathlib import Path
sys.path.insert(0, '/app/shared')
from base_connector import BaseConnector

# Import yeelight library
try:
    from yeelight import Bulb, BulbException, discover_bulbs
    from yeelight import Flow, RGBTransition, TemperatureTransition, SleepTransition
except ImportError:
    logger.error("yeelight library not installed. Please add 'yeelight' to requirements.txt")
    raise

logger = logging.getLogger(__name__)

class Connector(BaseConnector):
    """
    Yeelight connector implementation
    
    Provides direct connection to Yeelight WiFi bulbs
    Supports discovery, state management, and control
    """
    
    def __init__(self, config_path: str = None, instance_name: str = None):
        """Initialize connector"""
        super().__init__(config_path, instance_name)
        
        # Store device connections
        self.device_connections = {}
        
        # Discovery settings
        self.discovery_enabled = self.config.get('discovery_enabled', True)
        self.discovery_interval = self.config.get('discovery_interval', 300)  # 5 minutes
        self.last_discovery = 0
        
        # Effect settings
        self.default_effect = self.config.get('effect_type', 'smooth')
        self.default_duration = self.config.get('duration', 300)
        
        logger.info(f"Yeelight Connector initialized for {self.instance_id}")
    
    def initialize_connection(self):
        """
        Initialize connection to Yeelight devices
        """
        logger.info("Initializing connection to Yeelight devices...")
        
        # Initialize device connections
        for device_config in self.config.get('devices', []):
            device_id = device_config['device_id']
            
            if not device_config.get('enabled', True):
                logger.info(f"Device {device_id} is disabled, skipping")
                continue
            
            try:
                # Create Bulb connection
                ip = device_config.get('ip')
                if not ip:
                    logger.warning(f"No IP address for device {device_id}, skipping")
                    continue
                
                port = device_config.get('port', 55443)
                bulb = Bulb(
                    ip,
                    port=port,
                    effect=self.default_effect,
                    duration=self.default_duration,
                    auto_on=device_config.get('auto_on', True)
                )
                
                # Test connection by getting properties
                props = bulb.get_properties()
                if props:
                    self.device_connections[device_id] = {
                        "bulb": bulb,
                        "config": device_config,
                        "model": device_config.get('model', props.get('model', 'unknown')),
                        "capabilities": self._parse_capabilities(props),
                        "last_state": None
                    }
                    logger.info(f"Connected to Yeelight device: {device_id} at {ip}:{port}")
                    
                    # Set device name if configured
                    if 'name' in device_config:
                        try:
                            bulb.set_name(device_config['name'])
                        except:
                            pass
                else:
                    logger.warning(f"Could not get properties from {device_id} at {ip}")
                
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
        Clean up Yeelight connections when stopping
        """
        logger.info("Cleaning up Yeelight connections...")
        
        for device_id, connection in self.device_connections.items():
            try:
                bulb = connection.get('bulb')
                if bulb:
                    # Stop any running effects
                    try:
                        bulb.stop_flow()
                    except:
                        pass
                    # Stop music mode if active
                    try:
                        bulb.stop_music()
                    except:
                        pass
                    logger.info(f"Disconnected Yeelight device: {device_id}")
            except Exception as e:
                logger.error(f"Error disconnecting {device_id}: {e}")
        
        self.device_connections.clear()
    
    def get_device_state(self, device_id: str, device_config: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Get current state of a Yeelight device
        """
        if device_id not in self.device_connections:
            logger.warning(f"Device {device_id} not connected")
            return None
        
        connection = self.device_connections[device_id]
        bulb = connection['bulb']
        
        try:
            # Get all properties from device
            props = bulb.get_properties()
            
            if not props:
                return None
            
            # Parse state with safe type conversion
            def safe_int(value, default=0):
                """Safely convert value to int with default fallback"""
                if value is None:
                    return default
                try:
                    return int(value)
                except (ValueError, TypeError):
                    return default
            
            def safe_bool(value, default=False):
                """Safely convert value to bool with default fallback"""
                if value is None:
                    return default
                if isinstance(value, bool):
                    return value
                if isinstance(value, str):
                    return value.lower() in ('true', 'on', '1', 'yes')
                return bool(value) if value else default
            
            state = {
                'online': True,
                'power': props.get('power', 'off') == 'on',
                'brightness': safe_int(props.get('bright', 100), 100),
                'color_temp': safe_int(props.get('ct', 3500), 3500),
                'color_mode': safe_int(props.get('color_mode', 0), 0),
                'flowing': safe_int(props.get('flowing', 0), 0) == 1,
                'music_mode': safe_int(props.get('music_on', 0), 0) == 1,
                'name': props.get('name', device_config.get('name', device_id)),
                'model': connection['model'],
                'fw_ver': props.get('fw_ver', 'unknown'),
                'last_update': datetime.now().isoformat()
            }
            
            # Add RGB if available
            if 'rgb' in props and props['rgb'] is not None:
                rgb_val = safe_int(props['rgb'], 0)
                if rgb_val > 0:  # Only add RGB if valid value
                    state['rgb'] = {
                        'r': (rgb_val >> 16) & 0xFF,
                        'g': (rgb_val >> 8) & 0xFF,
                        'b': rgb_val & 0xFF
                    }
                    state['hex_color'] = f"#{rgb_val:06x}"
            
            # Add HSV if available
            if 'hue' in props and 'sat' in props:
                hue_val = safe_int(props.get('hue'), -1)
                sat_val = safe_int(props.get('sat'), -1)
                if hue_val >= 0 and sat_val >= 0:  # Only add if valid values
                    state['hsv'] = {
                        'h': hue_val,
                        's': sat_val,
                        'v': state['brightness']
                    }
            
            # Add nightlight if supported
            if 'nl_br' in props:
                nl_brightness = safe_int(props.get('nl_br'), 0)
                active_mode = safe_int(props.get('active_mode'), 0)
                state['nightlight'] = {
                    'brightness': nl_brightness,
                    'active': active_mode == 1
                }
            
            # Add background light for ceiling lights
            if 'bg_power' in props:
                state['background'] = {
                    'power': props.get('bg_power', 'off') == 'on',
                    'brightness': safe_int(props.get('bg_bright'), 0),
                    'color_temp': safe_int(props.get('bg_ct'), 0),
                    'flowing': safe_int(props.get('bg_flowing'), 0) == 1
                }
                
                if 'bg_rgb' in props and props['bg_rgb'] is not None:
                    bg_rgb_val = safe_int(props['bg_rgb'], 0)
                    if bg_rgb_val > 0:  # Only add if valid
                        state['background']['rgb'] = {
                            'r': (bg_rgb_val >> 16) & 0xFF,
                            'g': (bg_rgb_val >> 8) & 0xFF,
                            'b': bg_rgb_val & 0xFF
                        }
                        state['background']['hex_color'] = f"#{bg_rgb_val:06x}"
                
                if 'bg_hue' in props and 'bg_sat' in props:
                    bg_hue_val = safe_int(props.get('bg_hue'), -1)
                    bg_sat_val = safe_int(props.get('bg_sat'), -1)
                    if bg_hue_val >= 0 and bg_sat_val >= 0:  # Only add if valid
                        state['background']['hsv'] = {
                            'h': bg_hue_val,
                            's': bg_sat_val
                    }
            
            # Store last state
            connection['last_state'] = state
            
            return state
            
        except BulbException as e:
            logger.error(f"Bulb error getting state for {device_id}: {e}")
            return {'online': False, 'last_update': datetime.now().isoformat()}
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
        Set Yeelight device state
        """
        logger.info(f"Setting state for {device_id}: {state}")
        
        if device_id not in self.device_connections:
            logger.warning(f"Device {device_id} not connected")
            return False
        
        connection = self.device_connections[device_id]
        bulb = connection['bulb']
        
        try:
            # Extract transition if present (applies to all changes)
            transition = state.pop('transition', self.default_duration) if 'transition' in state else self.default_duration
            
            # Process commands
            for key, value in state.items():
                if key == 'power':
                    if value == 'toggle':
                        bulb.toggle()
                        logger.info(f"Toggled {device_id} power")
                    elif value:
                        bulb.turn_on(duration=transition)
                        logger.info(f"Set {device_id} power: on")
                    else:
                        bulb.turn_off(duration=transition)
                        logger.info(f"Set {device_id} power: off")
                
                elif key == 'brightness':
                    # Handle relative changes
                    if isinstance(value, str) and (value.startswith('+') or value.startswith('-')):
                        current = self._get_current_brightness(device_id)
                        brightness = current + int(value)
                    else:
                        brightness = int(value) if isinstance(value, str) else value
                    
                    brightness = max(1, min(100, brightness))
                    bulb.set_brightness(brightness, duration=transition)
                    logger.info(f"Set {device_id} brightness: {brightness}")
                
                elif key == 'brightness_step':
                    # Alternative relative brightness
                    current = self._get_current_brightness(device_id)
                    brightness = max(1, min(100, current + int(value)))
                    bulb.set_brightness(brightness, duration=transition)
                    logger.info(f"Adjusted {device_id} brightness by {value} to {brightness}")
                
                elif key == 'color_temp':
                    # Handle relative changes
                    if isinstance(value, str) and (value.startswith('+') or value.startswith('-')):
                        current = self._get_current_color_temp(device_id)
                        ct = current + int(value)
                    else:
                        ct = int(value) if isinstance(value, str) else value
                    
                    # Yeelight expects kelvin (1700-6500)
                    ct = max(1700, min(6500, ct))
                    bulb.set_color_temp(ct, duration=transition)
                    logger.info(f"Set {device_id} color_temp: {ct}K")
                
                elif key == 'color':
                    # New unified color handling
                    color_data = self._parse_color_value(value)
                    if color_data:
                        if color_data[0] == 'rgb':
                            r, g, b = color_data[1], color_data[2], color_data[3]
                            bulb.set_rgb(r, g, b, duration=transition)
                            logger.info(f"Set {device_id} RGB: ({r}, {g}, {b})")
                        elif color_data[0] == 'hsv':
                            h, s, v = color_data[1], color_data[2], color_data[3]
                            # Note: Yeelight set_hsv doesn't use v, it uses current brightness
                            if v != 100:
                                bulb.set_brightness(v, duration=transition)
                            bulb.set_hsv(h, s, duration=transition)
                            logger.info(f"Set {device_id} HSV: ({h}, {s}, {v})")
                    else:
                        logger.warning(f"Invalid color format for {device_id}: {value}")
                
                elif key == 'rgb':
                    # Keep backward compatibility
                    if isinstance(value, dict):
                        r, g, b = value['r'], value['g'], value['b']
                    else:
                        r, g, b = value
                    bulb.set_rgb(r, g, b, duration=transition)
                    logger.info(f"Set {device_id} RGB: ({r}, {g}, {b})")
                
                elif key == 'hsv':
                    # Keep backward compatibility
                    h = max(0, min(359, int(value['h'])))
                    s = max(0, min(100, int(value['s'])))
                    v = value.get('v', 100)
                    if v != 100:
                        bulb.set_brightness(v, duration=transition)
                    bulb.set_hsv(h, s, duration=transition)
                    logger.info(f"Set {device_id} HSV: ({h}, {s}, {v})")
                
                elif key == 'scene':
                    self._apply_scene(bulb, value, transition)
                    logger.info(f"Applied scene '{value}' to {device_id}")
                
                elif key == 'effect':
                    self._apply_effect(bulb, value, transition)
                    logger.info(f"Applied effect '{value}' to {device_id}")
                
                elif key == 'toggle':
                    bulb.toggle(duration=transition)
                    logger.info(f"Toggled {device_id}")
                
                elif key == 'music_mode':
                    if value:
                        bulb.start_music()
                    else:
                        bulb.stop_music()
                    logger.info(f"Set {device_id} music_mode: {value}")
                
                elif key == 'background':
                    # Handle background light commands for ceiling lights
                    self._set_background_state(bulb, value)
                    logger.info(f"Set {device_id} background state")
                
                else:
                    logger.warning(f"Unknown command '{key}' for device {device_id}")
            
            # After successful update, get and publish new state
            time.sleep(0.5)  # Give device time to update
            new_state = self.get_device_state(device_id, device_config)
            if new_state:
                self.mqtt.publish_state(device_id, new_state)
            
            return True
            
        except BulbException as e:
            logger.error(f"Bulb error setting state for {device_id}: {e}")
            self.mqtt.publish_error(
                device_id,
                "COMMAND_ERROR",
                f"Bulb error: {e}",
                severity="error"
            )
            return False
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
        Discover Yeelight devices on the network
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
            logger.info("Starting Yeelight device discovery...")
            bulbs = discover_bulbs(timeout=5)
            
            for bulb_info in bulbs:
                ip = bulb_info['ip']
                capabilities = bulb_info.get('capabilities', {})
                bulb_id = capabilities.get('id', ip.replace('.', '_'))
                
                # Check if device is already configured
                already_configured = False
                for device in self.config.get('devices', []):
                    if device.get('ip') == ip:
                        already_configured = True
                        break
                
                if not already_configured:
                    device_info = {
                        "device_id": f"yeelight_{bulb_id}",
                        "ip": ip,
                        "port": bulb_info.get('port', 55443),
                        "model": capabilities.get('model', 'unknown'),
                        "name": capabilities.get('name', f"Yeelight {bulb_id}"),
                        "fw_ver": capabilities.get('fw_ver'),
                        "support": capabilities.get('support', []),
                        "power": capabilities.get('power', 'off') == 'on',
                        "bright": capabilities.get('bright', 0),
                        "color_mode": capabilities.get('color_mode', 0),
                        "ct": capabilities.get('ct', 0),
                        "rgb": capabilities.get('rgb', 0),
                        "hue": capabilities.get('hue', 0),
                        "sat": capabilities.get('sat', 0)
                    }
                    discovered.append(device_info)
                    logger.info(f"Discovered new Yeelight device: {device_info['name']} at {ip}")
            
        except Exception as e:
            logger.error(f"Error during device discovery: {e}")
        
        # Publish discovered devices if any
        if discovered:
            self.mqtt.publish_discovered(discovered)
            logger.info(f"Discovered {len(discovered)} new Yeelight devices")
        
        return discovered
    
    # === Custom Yeelight methods ===
    
    def _parse_capabilities(self, props: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parse device capabilities from properties
        """
        capabilities = {}
        
        # Basic capabilities
        if 'power' in props:
            capabilities['power'] = {'settable': True, 'type': 'boolean'}
        if 'bright' in props:
            capabilities['brightness'] = {'settable': True, 'type': 'integer', 'min': 1, 'max': 100}
        if 'ct' in props:
            capabilities['color_temp'] = {'settable': True, 'type': 'integer', 'min': 1700, 'max': 6500}
        if 'rgb' in props:
            capabilities['rgb'] = {'settable': True, 'type': 'object'}
        if 'hue' in props and 'sat' in props:
            capabilities['hsv'] = {'settable': True, 'type': 'object'}
        
        # Nightlight
        if 'nl_br' in props:
            capabilities['nightlight'] = {'settable': False, 'type': 'object'}
        
        # Background light (ceiling)
        if 'bg_power' in props:
            capabilities['background'] = {'settable': True, 'type': 'object'}
        
        return capabilities
    
    def _parse_color_value(self, color_value):
        """
        Parse color from different formats (RGB dict, HEX string, HSV dict)
        Returns tuple: (format, val1, val2, val3) or None
        """
        if isinstance(color_value, str) and color_value.startswith('#'):
            # HEX to RGB
            hex_color = color_value.lstrip('#')
            if len(hex_color) == 6:
                try:
                    r = int(hex_color[0:2], 16)
                    g = int(hex_color[2:4], 16)
                    b = int(hex_color[4:6], 16)
                    return ('rgb', r, g, b)
                except ValueError:
                    return None
        elif isinstance(color_value, dict):
            if 'r' in color_value and 'g' in color_value and 'b' in color_value:
                # RGB format
                return ('rgb', 
                        max(0, min(255, int(color_value['r']))),
                        max(0, min(255, int(color_value['g']))),
                        max(0, min(255, int(color_value['b']))))
            elif 'h' in color_value and 's' in color_value:
                # HSV format
                return ('hsv',
                        max(0, min(359, int(color_value['h']))),
                        max(0, min(100, int(color_value['s']))),
                        max(0, min(100, int(color_value.get('v', 100)))))
        return None
    
    def _get_current_brightness(self, device_id: str) -> int:
        """
        Get current brightness from cached state or device
        """
        if device_id in self.device_connections:
            last_state = self.device_connections[device_id].get('last_state')
            if last_state:
                return last_state.get('brightness', 50)
        return 50  # default
    
    def _get_current_color_temp(self, device_id: str) -> int:
        """
        Get current color temperature from cached state or device
        """
        if device_id in self.device_connections:
            last_state = self.device_connections[device_id].get('last_state')
            if last_state:
                return last_state.get('color_temp', 4000)
        return 4000  # default
    
    def _apply_scene(self, bulb: Bulb, scene: str, transition: int = 300):
        """
        Apply a predefined scene to the bulb
        """
        scenes = {
            'sunrise': ('cf', 3, 1, '50,1,16731392,1,360000,2,1700,10,540000,2,2700,100'),
            'sunset': ('cf', 3, 2, '50,2,2700,10,180000,2,1700,5,420000,1,16731136,1'),
            'romance': ('cf', 0, 0, '500,1,16711936,100,500,1,16711936,1'),
            'party': ('cf', 0, 0, '300,1,16711680,100,300,1,65280,100,300,1,255,100'),
            'candle': ('cf', 0, 0, '800,1,14438425,50,800,1,14448670,30'),
            'movie': ('ct', 2700, 50),
            'night': ('ct', 1700, 1),
            'reading': ('ct', 4000, 100),
            'relax': ('ct', 3000, 30)
        }
        
        if scene in scenes:
            scene_data = scenes[scene]
            if scene_data[0] == 'ct':
                bulb.set_scene('ct', scene_data[1], scene_data[2])
            else:
                bulb.set_scene(*scene_data)
        else:
            logger.warning(f"Unknown scene: {scene}")
    
    def _apply_effect(self, bulb: Bulb, effect: str, transition: int = 300):
        """
        Apply a flow effect to the bulb
        """
        if effect == 'stop':
            bulb.stop_flow()
        elif effect == 'disco':
            flow = Flow(
                count=0,
                transitions=[
                    RGBTransition(255, 0, 0, duration=300),
                    RGBTransition(0, 255, 0, duration=300),
                    RGBTransition(0, 0, 255, duration=300),
                    RGBTransition(255, 255, 0, duration=300),
                    RGBTransition(255, 0, 255, duration=300),
                    RGBTransition(0, 255, 255, duration=300)
                ]
            )
            bulb.start_flow(flow)
        elif effect == 'pulse':
            flow = Flow(
                count=0,
                transitions=[
                    TemperatureTransition(3000, brightness=100, duration=500),
                    TemperatureTransition(3000, brightness=10, duration=500)
                ]
            )
            bulb.start_flow(flow)
        elif effect == 'strobe':
            flow = Flow(
                count=0,
                transitions=[
                    RGBTransition(255, 255, 255, duration=50),
                    SleepTransition(duration=50)
                ]
            )
            bulb.start_flow(flow)
        elif effect == 'rainbow':
            flow = Flow(
                count=0,
                transitions=[
                    RGBTransition(255, 0, 0, duration=1000),
                    RGBTransition(255, 127, 0, duration=1000),
                    RGBTransition(255, 255, 0, duration=1000),
                    RGBTransition(0, 255, 0, duration=1000),
                    RGBTransition(0, 0, 255, duration=1000),
                    RGBTransition(75, 0, 130, duration=1000),
                    RGBTransition(148, 0, 211, duration=1000)
                ]
            )
            bulb.start_flow(flow)
        else:
            logger.warning(f"Unknown effect: {effect}")
    
    def _set_background_state(self, bulb: Bulb, bg_state: Dict[str, Any]):
        """
        Set background light state for ceiling lights
        """
        if 'power' in bg_state:
            if bg_state['power']:
                bulb.bg_turn_on()
            else:
                bulb.bg_turn_off()
        
        if 'brightness' in bg_state:
            bulb.bg_set_brightness(bg_state['brightness'])
        
        if 'color_temp' in bg_state:
            bulb.bg_set_color_temp(bg_state['color_temp'])
        
        if 'rgb' in bg_state:
            rgb = bg_state['rgb']
            if isinstance(rgb, dict):
                bulb.bg_set_rgb(rgb['r'], rgb['g'], rgb['b'])
            else:
                bulb.bg_set_rgb(rgb[0], rgb[1], rgb[2])
        
        if 'hsv' in bg_state:
            hsv = bg_state['hsv']
            bulb.bg_set_hsv(hsv['h'], hsv['s'])