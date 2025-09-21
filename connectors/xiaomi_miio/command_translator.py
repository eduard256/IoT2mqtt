"""
Command Translator for Xiaomi MiIO Integration
Translates IoT2MQTT standard commands to device-specific MiIO commands
"""

from typing import Dict, Any, List, Tuple, Optional, Union
import logging

logger = logging.getLogger(__name__)


class CommandTranslator:
    """Translates between IoT2MQTT and MiIO command formats"""
    
    def translate_to_miio(self, mqtt_command: Dict[str, Any], model: str) -> List[Tuple[str, Any]]:
        """
        Translate MQTT command to MiIO device commands
        
        Args:
            mqtt_command: IoT2MQTT command dict
            model: Device model string
            
        Returns:
            List of (method_name, arguments) tuples
        """
        commands = []
        
        # Extract values from command
        values = mqtt_command.get('values', mqtt_command)
        
        # Process each command
        for key, value in values.items():
            # Power control
            if key == 'power':
                if value == 'toggle':
                    commands.append(('toggle', None))
                elif value:
                    commands.append(('on', None))
                else:
                    commands.append(('off', None))
            
            # Brightness/Speed control
            elif key == 'brightness':
                # For lights
                if 'light' in model or 'philips' in model:
                    brightness = self._parse_relative_value(value, 100)
                    commands.append(('set_brightness', brightness))
                # For purifiers/humidifiers (as fan speed)
                elif 'airpurifier' in model or 'humidifier' in model:
                    speed = self._parse_relative_value(value, 100)
                    commands.append(('set_speed', speed))
            
            elif key == 'speed':
                # For fans
                speed = self._parse_relative_value(value, 100)
                if 'fan' in model:
                    commands.append(('set_speed', speed))
                elif 'vacuum' in model:
                    commands.append(('set_fan_speed', speed))
            
            elif key == 'fan_speed':
                # Direct fan speed for vacuums
                if isinstance(value, str):
                    commands.append(('set_fan_speed_preset', value))
                else:
                    commands.append(('set_fan_speed', int(value)))
            
            # Color temperature
            elif key == 'color_temp':
                ct = self._parse_relative_value(value, 6500)
                ct = max(1700, min(6500, ct))  # Clamp to valid range
                commands.append(('set_color_temperature', ct))
            
            # Color control
            elif key == 'color':
                color_cmds = self._parse_color_commands(value)
                commands.extend(color_cmds)
            
            # Mode control
            elif key == 'mode':
                commands.append(('set_mode', value))
            
            # Scene control
            elif key == 'scene':
                if 'light' in model:
                    commands.append(('set_scene', self._translate_scene(value)))
                elif 'vacuum' in model and value == 'spot':
                    commands.append(('spot', None))
            
            # Effect control
            elif key == 'effect':
                if value == 'stop':
                    commands.append(('stop_effect', None))
                else:
                    commands.append(('set_effect', value))
            
            # Vacuum specific commands
            elif key == 'vacuum':
                if value == 'start':
                    commands.append(('resume_or_start', None))
                elif value == 'stop':
                    commands.append(('stop', None))
                elif value == 'pause':
                    commands.append(('pause', None))
                elif value == 'dock' or value == 'return':
                    commands.append(('home', None))
                elif value == 'spot':
                    commands.append(('spot', None))
                elif value == 'locate':
                    commands.append(('find', None))
            
            elif key == 'vacuum_mode':
                # Map vacuum modes to fan speeds
                mode_map = {
                    'quiet': 38,
                    'standard': 60,
                    'medium': 77,
                    'turbo': 90,
                    'max': 100
                }
                if value in mode_map:
                    commands.append(('set_fan_speed', mode_map[value]))
            
            # Clean zone/segment
            elif key == 'clean_zone':
                zone = value.get('zone', [])
                repeats = value.get('repeats', 1)
                if zone:
                    commands.append(('zoned_clean', {'zones': [zone + [repeats]]}))
            
            elif key == 'clean_segment':
                segments = value if isinstance(value, list) else [value]
                commands.append(('segment_clean', {'segments': segments}))
            
            elif key == 'goto':
                x = value.get('x', 0)
                y = value.get('y', 0)
                commands.append(('goto', {'x_coord': x, 'y_coord': y}))
            
            # Remote control
            elif key == 'remote_control':
                action = value.get('action')
                if action == 'start':
                    commands.append(('manual_start', None))
                elif action == 'stop':
                    commands.append(('manual_stop', None))
                elif action == 'move':
                    velocity = value.get('velocity', 0.3)
                    rotation = value.get('rotation', 0)
                    duration = value.get('duration', 1500)
                    commands.append(('manual_control', {
                        'velocity': velocity,
                        'rotation': rotation,
                        'duration': duration
                    }))
            
            # Humidifier specific
            elif key == 'target_humidity':
                humidity = int(value)
                humidity = max(30, min(80, humidity))
                commands.append(('set_target_humidity', humidity))
            
            elif key == 'dry' or key == 'dry_mode':
                if value:
                    commands.append(('set_dry', 'on'))
                else:
                    commands.append(('set_dry', 'off'))
            
            # Fan specific
            elif key == 'oscillation' or key == 'oscillate':
                if value:
                    commands.append(('set_oscillate', True))
                else:
                    commands.append(('set_oscillate', False))
            
            elif key == 'oscillation_angle' or key == 'angle':
                angle = int(value)
                commands.append(('set_angle', angle))
            
            elif key == 'natural_mode':
                if value:
                    commands.append(('set_natural_mode', True))
                else:
                    commands.append(('set_natural_mode', False))
            
            elif key == 'ionizer':
                if value:
                    commands.append(('set_ionizer', 'on'))
                else:
                    commands.append(('set_ionizer', 'off'))
            
            # Common device features
            elif key == 'child_lock':
                if value:
                    commands.append(('set_child_lock', 'on'))
                else:
                    commands.append(('set_child_lock', 'off'))
            
            elif key == 'buzzer':
                if value:
                    commands.append(('set_buzzer', True))
                else:
                    commands.append(('set_buzzer', False))
            
            elif key == 'led':
                if value:
                    commands.append(('set_led', True))
                else:
                    commands.append(('set_led', False))
            
            elif key == 'led_brightness':
                level = int(value)
                commands.append(('set_led_brightness', level))
            
            elif key == 'display':
                if value:
                    commands.append(('set_display', 'on'))
                else:
                    commands.append(('set_display', 'off'))
            
            # Timer/delay
            elif key == 'timer' or key == 'delay_off':
                seconds = int(value)
                commands.append(('set_delay_off', seconds))
            
            # Volume
            elif key == 'volume':
                vol = int(value)
                vol = max(0, min(100, vol))
                commands.append(('set_volume', vol))
            
            elif key == 'mute':
                if value == 'toggle':
                    commands.append(('toggle_mute', None))
                elif value:
                    commands.append(('mute', None))
                else:
                    commands.append(('unmute', None))
            
            # Filter reset
            elif key == 'reset_filter':
                commands.append(('reset_filter', None))
            
            # Favorite level
            elif key == 'favorite_level':
                level = int(value)
                commands.append(('set_favorite_level', level))
            
            elif key == 'favorite_rpm':
                rpm = int(value)
                commands.append(('set_favorite_rpm', rpm))
            
            # Raw command
            elif key == 'raw':
                protocol = value.get('protocol', 'miio')
                if protocol == 'miio':
                    cmd = value.get('command', value)
                    params = value.get('params', [])
                    commands.append(('raw_command', {'command': cmd, 'params': params}))
            
            # Exec command (for advanced users)
            elif key == 'exec':
                # This would be a raw MiIO command
                cmd_str = value
                if isinstance(value, dict):
                    cmd_str = value.get('command', '')
                    params = value.get('params', [])
                    commands.append(('raw_command', {'command': cmd_str, 'params': params}))
                else:
                    # Parse command string
                    parts = cmd_str.split(' ')
                    if parts:
                        commands.append(('raw_command', {'command': parts[0], 'params': parts[1:]}))
            
            # Query state
            elif key == 'query':
                properties = value if isinstance(value, list) else [value]
                for prop in properties:
                    if prop == 'status':
                        commands.append(('status', None))
                    elif prop == 'info':
                        commands.append(('info', None))
                    elif prop == 'consumables':
                        commands.append(('consumable_status', None))
                    elif prop == 'timers':
                        commands.append(('timer', None))
                    elif prop == 'dnd':
                        commands.append(('dnd_status', None))
            
            # Presets
            elif key == 'preset':
                preset_name = value
                commands.append(('set_preset', preset_name))
            
            elif key == 'save_preset':
                preset_name = value
                commands.append(('save_preset', preset_name))
            
            # Notifications
            elif key == 'notify':
                if value == 'beep':
                    commands.append(('set_buzzer', True))
                    commands.append(('set_buzzer', False))
                elif value == 'flash':
                    commands.append(('set_led', True))
                    commands.append(('set_led', False))
                    commands.append(('set_led', True))
            
            # Sequence commands
            elif key == 'sequence':
                for seq_cmd in value:
                    # Recursive call for each command in sequence
                    seq_commands = self.translate_to_miio({'values': seq_cmd}, model)
                    commands.extend(seq_commands)
        
        return commands
    
    def _parse_relative_value(self, value: Union[str, int, float], current: Optional[int] = None) -> int:
        """Parse relative or absolute value"""
        if isinstance(value, str):
            if value.startswith('+'):
                offset = int(value[1:])
                return (current or 50) + offset if current else offset
            elif value.startswith('-'):
                offset = int(value[1:])
                return (current or 50) - offset if current else -offset
            else:
                return int(value)
        return int(value)
    
    def _parse_color_commands(self, color_value: Any) -> List[Tuple[str, Any]]:
        """Parse color value and return appropriate commands"""
        commands = []
        
        if isinstance(color_value, str) and color_value.startswith('#'):
            # HEX color
            hex_color = color_value.lstrip('#')
            if len(hex_color) == 6:
                r = int(hex_color[0:2], 16)
                g = int(hex_color[2:4], 16)
                b = int(hex_color[4:6], 16)
                commands.append(('set_rgb', (r, g, b)))
        
        elif isinstance(color_value, dict):
            if 'r' in color_value and 'g' in color_value and 'b' in color_value:
                # RGB format
                r = max(0, min(255, int(color_value['r'])))
                g = max(0, min(255, int(color_value['g'])))
                b = max(0, min(255, int(color_value['b'])))
                commands.append(('set_rgb', (r, g, b)))
            
            elif 'h' in color_value and 's' in color_value:
                # HSV format
                h = max(0, min(359, int(color_value['h'])))
                s = max(0, min(100, int(color_value['s'])))
                v = max(0, min(100, int(color_value.get('v', 100))))
                
                # Some devices need brightness set separately
                if v != 100:
                    commands.append(('set_brightness', v))
                commands.append(('set_hsv', (h, s)))
        
        return commands
    
    def _translate_scene(self, scene_name: str) -> Any:
        """Translate scene name to device-specific scene data"""
        # Scene mappings for lights
        scene_map = {
            'sunrise': 1,
            'sunset': 2,
            'romance': 3,
            'party': 4,
            'candle': 5,
            'movie': 6,
            'night': 7,
            'reading': 8,
            'relax': 9
        }
        
        if scene_name in scene_map:
            return scene_map[scene_name]
        
        # Try as numeric scene ID
        try:
            return int(scene_name)
        except:
            return scene_name
    
    def translate_from_miio(self, miio_state: Dict[str, Any], model: str) -> Dict[str, Any]:
        """
        Translate MiIO device state to MQTT format
        
        Args:
            miio_state: Device state from MiIO
            model: Device model string
            
        Returns:
            MQTT formatted state dict
        """
        mqtt_state = {}
        
        # Direct mappings
        if 'is_on' in miio_state:
            mqtt_state['power'] = miio_state['is_on']
        elif 'power' in miio_state:
            mqtt_state['power'] = miio_state['power'] == 'on'
        
        if 'brightness' in miio_state:
            mqtt_state['brightness'] = miio_state['brightness']
        
        if 'speed' in miio_state:
            mqtt_state['speed'] = miio_state['speed']
        
        if 'fanspeed' in miio_state:
            mqtt_state['fan_speed'] = miio_state['fanspeed']
        
        if 'mode' in miio_state:
            mode = miio_state['mode']
            if hasattr(mode, 'value'):
                mqtt_state['mode'] = mode.value
            else:
                mqtt_state['mode'] = str(mode)
        
        if 'humidity' in miio_state:
            mqtt_state['humidity'] = miio_state['humidity']
        
        if 'target_humidity' in miio_state:
            mqtt_state['target_humidity'] = miio_state['target_humidity']
        
        if 'temperature' in miio_state:
            mqtt_state['temperature'] = miio_state['temperature']
        
        if 'aqi' in miio_state:
            mqtt_state['air_quality'] = miio_state['aqi']
        
        if 'battery' in miio_state:
            mqtt_state['battery'] = miio_state['battery']
        
        if 'color_temperature' in miio_state:
            mqtt_state['color_temp'] = miio_state['color_temperature']
        
        if 'rgb' in miio_state and miio_state['rgb']:
            rgb = miio_state['rgb']
            if isinstance(rgb, (list, tuple)) and len(rgb) >= 3:
                mqtt_state['color'] = {
                    'r': rgb[0],
                    'g': rgb[1],
                    'b': rgb[2]
                }
        
        # Boolean features
        for miio_key, mqtt_key in [
            ('child_lock', 'child_lock'),
            ('buzzer', 'buzzer'),
            ('led', 'led'),
            ('oscillate', 'oscillation'),
            ('natural_mode', 'natural_mode'),
            ('ionizer', 'ionizer'),
            ('dry', 'dry_mode'),
            ('display', 'display')
        ]:
            if miio_key in miio_state:
                mqtt_state[mqtt_key] = bool(miio_state[miio_key])
        
        # Numeric features
        for miio_key, mqtt_key in [
            ('angle', 'oscillation_angle'),
            ('led_brightness', 'led_brightness'),
            ('delay_off_countdown', 'timer'),
            ('volume', 'volume'),
            ('filter_life_remaining', 'filter_life'),
            ('filter_hours_used', 'filter_hours'),
            ('water_level', 'water_level'),
            ('load_power', 'power_load'),
            ('illumination', 'illumination')
        ]:
            if miio_key in miio_state:
                mqtt_state[mqtt_key] = miio_state[miio_key]
        
        # Vacuum specific
        if 'state' in miio_state:
            mqtt_state['activity'] = miio_state['state']
        
        if 'state_code' in miio_state:
            mqtt_state['state_code'] = miio_state['state_code']
        
        if 'error' in miio_state and miio_state['error']:
            mqtt_state['error'] = miio_state['error']
        
        if 'cleaning_time' in miio_state:
            mqtt_state['cleaning_time'] = miio_state['cleaning_time']
        
        if 'cleaned_area' in miio_state:
            mqtt_state['cleaned_area'] = miio_state['cleaned_area']
        
        return mqtt_state