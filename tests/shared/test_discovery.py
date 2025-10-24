"""
Comprehensive tests for DiscoveryGenerator

Tests cover:
1. Device discovery message generation for all platforms
2. Light platform with color modes and capabilities
3. Switch platform discovery
4. Camera platform with stream URLs
5. Sensor platform (temperature, humidity, etc.)
6. Binary sensor platform (motion, contact)
7. Climate platform (thermostat, AC)
8. Fan platform with speed control
9. Device info generation with identifiers
10. Discovery topic format validation
11. Discovery message removal
"""

import pytest
import json
from unittest.mock import Mock, MagicMock, patch
from pathlib import Path

# Add shared to path for imports
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'shared'))

from discovery import DiscoveryGenerator, DeviceInfo, EntityConfig


# ============================================================================
# TIER 1 - CRITICAL TESTS: Discovery Generator Initialization
# ============================================================================

class TestDiscoveryGeneratorInitialization:
    """Test DiscoveryGenerator initialization"""

    def test_initialization_with_defaults(self):
        """Should initialize with default values"""
        generator = DiscoveryGenerator(
            base_topic="IoT2mqtt",
            instance_id="test_instance"
        )

        assert generator.base_topic == "IoT2mqtt"
        assert generator.discovery_prefix == "homeassistant"
        assert generator.instance_id == "test_instance"

    def test_initialization_with_custom_prefix(self):
        """Should use custom discovery prefix"""
        generator = DiscoveryGenerator(
            base_topic="IoT2mqtt",
            discovery_prefix="custom_ha",
            instance_id="test"
        )

        assert generator.discovery_prefix == "custom_ha"

    def test_device_class_mappings_exist(self):
        """Should have device class mappings defined"""
        generator = DiscoveryGenerator(base_topic="IoT2mqtt", instance_id="test")

        assert hasattr(generator, 'DEVICE_CLASSES')
        assert isinstance(generator.DEVICE_CLASSES, dict)
        assert 'light.dimmable' in generator.DEVICE_CLASSES
        assert 'switch.outlet' in generator.DEVICE_CLASSES
        assert 'security.camera' in generator.DEVICE_CLASSES


# ============================================================================
# TIER 1 - CRITICAL TESTS: Light Platform Discovery
# ============================================================================

class TestLightDiscovery:
    """Test light platform discovery generation"""

    def test_generate_light_discovery_basic(self):
        """Should generate basic light discovery without capabilities"""
        generator = DiscoveryGenerator(
            base_topic="IoT2mqtt",
            instance_id="test_instance"
        )

        device_config = {
            "device_id": "light1",
            "friendly_name": "Living Room Light",
            "class": "light.switch",
            "model": "Smart Bulb v1",
            "manufacturer": "TestBrand",
            "capabilities": {}
        }

        discoveries = generator.generate_device_discovery("light1", device_config)

        assert len(discoveries) == 1
        discovery = discoveries[0]

        assert discovery['topic'] == "homeassistant/light/test_instance_light1/config"
        assert discovery['retain'] is True
        assert 'payload' in discovery

        payload = discovery['payload']
        assert payload['unique_id'] == "test_instance_light1_light"
        assert payload['name'] == "Living Room Light"
        assert 'state_topic' in payload
        assert 'command_topic' in payload

    def test_generate_light_discovery_with_brightness(self):
        """Should include brightness support in discovery"""
        generator = DiscoveryGenerator(
            base_topic="IoT2mqtt",
            instance_id="test"
        )

        device_config = {
            "device_id": "light1",
            "friendly_name": "Dimmable Light",
            "class": "light.dimmable",
            "capabilities": {
                "brightness": {"settable": True, "min": 0, "max": 100}
            }
        }

        discoveries = generator.generate_device_discovery("light1", device_config)
        payload = discoveries[0]['payload']

        assert payload['brightness'] is True
        assert "brightness" in payload['supported_color_modes']

    def test_generate_light_discovery_with_color_temp(self):
        """Should include color temperature support"""
        generator = DiscoveryGenerator(
            base_topic="IoT2mqtt",
            instance_id="test"
        )

        device_config = {
            "device_id": "light1",
            "friendly_name": "Color Temp Light",
            "class": "light.color_temp",
            "capabilities": {
                "brightness": {"settable": True},
                "color_temp": {"settable": True, "min": 2700, "max": 6500}
            }
        }

        discoveries = generator.generate_device_discovery("light1", device_config)
        payload = discoveries[0]['payload']

        assert "color_temp" in payload['supported_color_modes']
        assert "brightness" in payload['supported_color_modes']

    def test_generate_light_discovery_with_rgb(self):
        """Should include RGB color support"""
        generator = DiscoveryGenerator(
            base_topic="IoT2mqtt",
            instance_id="test"
        )

        device_config = {
            "device_id": "light1",
            "friendly_name": "RGB Light",
            "class": "light.rgb",
            "capabilities": {
                "brightness": {"settable": True},
                "color": {"settable": True}
            }
        }

        discoveries = generator.generate_device_discovery("light1", device_config)
        payload = discoveries[0]['payload']

        assert "rgb" in payload['supported_color_modes']

    def test_light_discovery_topic_format(self):
        """Should use correct HA discovery topic format for light"""
        generator = DiscoveryGenerator(
            base_topic="IoT2mqtt",
            discovery_prefix="homeassistant",
            instance_id="my_instance"
        )

        device_config = {
            "device_id": "bulb_123",
            "class": "light.dimmable",
            "capabilities": {}
        }

        discoveries = generator.generate_device_discovery("bulb_123", device_config)

        # Format: homeassistant/light/{node_id}/config
        expected_topic = "homeassistant/light/my_instance_bulb_123/config"
        assert discoveries[0]['topic'] == expected_topic

    def test_light_discovery_includes_device_info(self):
        """Should include device info in light discovery"""
        generator = DiscoveryGenerator(
            base_topic="IoT2mqtt",
            instance_id="test"
        )

        device_config = {
            "device_id": "light1",
            "friendly_name": "Test Light",
            "class": "light.dimmable",
            "model": "BulbPro",
            "manufacturer": "SmartHome Inc",
            "capabilities": {}
        }

        discoveries = generator.generate_device_discovery("light1", device_config)
        payload = discoveries[0]['payload']

        assert 'device' in payload
        device_info = payload['device']
        assert device_info['name'] == "Test Light"
        assert device_info['model'] == "BulbPro"
        assert device_info['manufacturer'] == "SmartHome Inc"


# ============================================================================
# TIER 1 - CRITICAL TESTS: Switch Platform Discovery
# ============================================================================

class TestSwitchDiscovery:
    """Test switch platform discovery generation"""

    def test_generate_switch_discovery(self):
        """Should generate switch discovery config"""
        generator = DiscoveryGenerator(
            base_topic="IoT2mqtt",
            instance_id="test"
        )

        device_config = {
            "device_id": "switch1",
            "friendly_name": "Smart Outlet",
            "class": "switch.outlet",
            "capabilities": {}
        }

        discoveries = generator.generate_device_discovery("switch1", device_config)

        assert len(discoveries) == 1
        discovery = discoveries[0]

        assert discovery['topic'] == "homeassistant/switch/test_switch1/config"
        payload = discovery['payload']

        assert payload['unique_id'] == "test_switch1_switch"
        assert payload['name'] == "Smart Outlet"
        assert 'value_template' in payload
        assert payload['payload_on'] is not None
        assert payload['payload_off'] is not None

    def test_switch_discovery_payload_format(self):
        """Should use correct payload format for switch on/off"""
        generator = DiscoveryGenerator(
            base_topic="IoT2mqtt",
            instance_id="test"
        )

        device_config = {
            "device_id": "outlet1",
            "class": "switch.outlet",
            "capabilities": {}
        }

        discoveries = generator.generate_device_discovery("outlet1", device_config)
        payload = discoveries[0]['payload']

        # Payload should be JSON with values wrapper
        assert 'payload_on' in payload
        assert 'payload_off' in payload

        # Should be valid JSON
        on_payload = json.loads(payload['payload_on'])
        off_payload = json.loads(payload['payload_off'])

        assert on_payload == {"values": {"power": True}}
        assert off_payload == {"values": {"power": False}}

    def test_switch_value_template(self):
        """Should extract power state from MQTT payload"""
        generator = DiscoveryGenerator(
            base_topic="IoT2mqtt",
            instance_id="test"
        )

        device_config = {
            "device_id": "switch1",
            "class": "switch.relay",
            "capabilities": {}
        }

        discoveries = generator.generate_device_discovery("switch1", device_config)
        payload = discoveries[0]['payload']

        # Should use value_template to extract state.power
        assert payload['value_template'] == "{{ value_json.state.power }}"
        assert payload['state_on'] == "true"
        assert payload['state_off'] == "false"


# ============================================================================
# TIER 1 - CRITICAL TESTS: Camera Platform Discovery
# ============================================================================

class TestCameraDiscovery:
    """Test camera platform discovery generation"""

    def test_generate_camera_discovery_with_rtsp(self):
        """Should generate camera discovery with RTSP stream"""
        generator = DiscoveryGenerator(
            base_topic="IoT2mqtt",
            instance_id="cameras"
        )

        device_config = {
            "device_id": "cam1",
            "friendly_name": "Front Door Camera",
            "class": "security.camera",
            "model": "IP Cam Pro",
            "stream_urls": {
                "rtsp": "rtsp://192.168.1.10:554/stream",
                "jpeg": "http://192.168.1.10/snapshot.jpg"
            },
            "capabilities": {}
        }

        discoveries = generator.generate_device_discovery("cam1", device_config)

        assert len(discoveries) == 1
        discovery = discoveries[0]

        assert discovery['topic'] == "homeassistant/camera/cameras_cam1/config"
        payload = discovery['payload']

        assert payload['unique_id'] == "cameras_cam1_camera"
        assert payload['stream_source'] == "rtsp://192.168.1.10:554/stream"
        assert payload['still_image_url'] == "http://192.168.1.10/snapshot.jpg"

    def test_camera_discovery_with_m3u8_fallback(self):
        """Should use m3u8 stream if RTSP not available"""
        generator = DiscoveryGenerator(
            base_topic="IoT2mqtt",
            instance_id="cameras"
        )

        device_config = {
            "device_id": "cam2",
            "class": "security.camera",
            "stream_urls": {
                "m3u8": "http://192.168.1.11/stream.m3u8",
                "jpeg": "http://192.168.1.11/snapshot.jpg"
            },
            "capabilities": {}
        }

        discoveries = generator.generate_device_discovery("cam2", device_config)
        payload = discoveries[0]['payload']

        assert payload['stream_source'] == "http://192.168.1.11/stream.m3u8"

    def test_camera_discovery_requires_still_image(self):
        """Should include still image URL for camera"""
        generator = DiscoveryGenerator(
            base_topic="IoT2mqtt",
            instance_id="cameras"
        )

        device_config = {
            "device_id": "cam1",
            "class": "security.camera",
            "stream_urls": {
                "rtsp": "rtsp://192.168.1.10/stream",
                "jpeg": "http://192.168.1.10/snapshot.jpg"
            },
            "capabilities": {}
        }

        discoveries = generator.generate_device_discovery("cam1", device_config)
        payload = discoveries[0]['payload']

        assert 'still_image_url' in payload
        assert payload['still_image_url'] == "http://192.168.1.10/snapshot.jpg"


# ============================================================================
# TIER 1 - CRITICAL TESTS: Sensor Platform Discovery
# ============================================================================

class TestSensorDiscovery:
    """Test sensor platform discovery generation"""

    def test_generate_sensor_discoveries_multiple(self):
        """Should generate multiple sensor entities for different capabilities"""
        generator = DiscoveryGenerator(
            base_topic="IoT2mqtt",
            instance_id="test"
        )

        device_config = {
            "device_id": "sensor1",
            "friendly_name": "Climate Sensor",
            "class": "sensor.temperature",
            "capabilities": {
                "temperature": {"settable": False, "unit": "°C"},
                "humidity": {"settable": False, "unit": "%"},
                "pressure": {"settable": False, "unit": "hPa"}
            }
        }

        discoveries = generator.generate_device_discovery("sensor1", device_config)

        # Should generate 3 sensor entities
        assert len(discoveries) == 3

        # Check topics
        topics = [d['topic'] for d in discoveries]
        assert "homeassistant/sensor/test_sensor1_temperature/config" in topics
        assert "homeassistant/sensor/test_sensor1_humidity/config" in topics
        assert "homeassistant/sensor/test_sensor1_pressure/config" in topics

    def test_sensor_value_template(self):
        """Should use value_template to extract sensor value"""
        generator = DiscoveryGenerator(
            base_topic="IoT2mqtt",
            instance_id="test"
        )

        device_config = {
            "device_id": "sensor1",
            "class": "sensor.temperature",
            "capabilities": {
                "temperature": {"settable": False}
            }
        }

        discoveries = generator.generate_device_discovery("sensor1", device_config)
        payload = discoveries[0]['payload']

        assert payload['value_template'] == "{{ value_json.state.temperature }}"

    def test_sensor_device_class_and_unit(self):
        """Should include device_class and unit_of_measurement"""
        generator = DiscoveryGenerator(
            base_topic="IoT2mqtt",
            instance_id="test"
        )

        device_config = {
            "device_id": "sensor1",
            "class": "sensor.temperature",
            "capabilities": {
                "temperature": {"settable": False}
            }
        }

        discoveries = generator.generate_device_discovery("sensor1", device_config)
        payload = discoveries[0]['payload']

        assert payload['device_class'] == "temperature"
        assert payload['unit_of_measurement'] == "°C"

    def test_sensor_energy_monitoring(self):
        """Should support power and energy sensors"""
        generator = DiscoveryGenerator(
            base_topic="IoT2mqtt",
            instance_id="test"
        )

        device_config = {
            "device_id": "meter1",
            "class": "sensor.energy",
            "capabilities": {
                "power": {"settable": False},
                "energy": {"settable": False},
                "voltage": {"settable": False},
                "current": {"settable": False}
            }
        }

        discoveries = generator.generate_device_discovery("meter1", device_config)

        # Should generate 4 sensor entities
        assert len(discoveries) == 4

        # Check units
        power_sensor = next(d for d in discoveries if 'power' in d['topic'])
        energy_sensor = next(d for d in discoveries if 'energy' in d['topic'])

        assert power_sensor['payload']['unit_of_measurement'] == "W"
        assert energy_sensor['payload']['unit_of_measurement'] == "kWh"


# ============================================================================
# TIER 1 - CRITICAL TESTS: Binary Sensor Platform Discovery
# ============================================================================

class TestBinarySensorDiscovery:
    """Test binary sensor platform discovery generation"""

    def test_generate_motion_sensor_discovery(self):
        """Should generate motion sensor binary_sensor"""
        generator = DiscoveryGenerator(
            base_topic="IoT2mqtt",
            instance_id="test"
        )

        device_config = {
            "device_id": "motion1",
            "friendly_name": "Hallway Motion",
            "class": "sensor.motion",
            "capabilities": {}
        }

        discoveries = generator.generate_device_discovery("motion1", device_config)

        assert len(discoveries) == 1
        discovery = discoveries[0]

        assert discovery['topic'] == "homeassistant/binary_sensor/test_motion1/config"
        payload = discovery['payload']

        assert payload['device_class'] == "motion"
        assert payload['value_template'] == "{{ value_json.state.motion }}"

    def test_generate_contact_sensor_discovery(self):
        """Should generate contact/door sensor"""
        generator = DiscoveryGenerator(
            base_topic="IoT2mqtt",
            instance_id="test"
        )

        device_config = {
            "device_id": "door1",
            "class": "sensor.contact",
            "capabilities": {}
        }

        discoveries = generator.generate_device_discovery("door1", device_config)
        payload = discoveries[0]['payload']

        assert payload['device_class'] == "door"
        assert payload['value_template'] == "{{ value_json.state.contact }}"

    def test_binary_sensor_payload_on_off(self):
        """Should use true/false payloads for binary sensor"""
        generator = DiscoveryGenerator(
            base_topic="IoT2mqtt",
            instance_id="test"
        )

        device_config = {
            "device_id": "motion1",
            "class": "sensor.motion",
            "capabilities": {}
        }

        discoveries = generator.generate_device_discovery("motion1", device_config)
        payload = discoveries[0]['payload']

        assert payload['payload_on'] == "true"
        assert payload['payload_off'] == "false"


# ============================================================================
# TIER 1 - CRITICAL TESTS: Climate Platform Discovery
# ============================================================================

class TestClimateDiscovery:
    """Test climate platform discovery generation"""

    def test_generate_thermostat_discovery(self):
        """Should generate climate entity for thermostat"""
        generator = DiscoveryGenerator(
            base_topic="IoT2mqtt",
            instance_id="test"
        )

        device_config = {
            "device_id": "thermo1",
            "friendly_name": "Living Room Thermostat",
            "class": "climate.thermostat",
            "capabilities": {
                "mode": {"settable": True, "options": ["auto", "cool", "heat", "off"]},
                "temperature": {"settable": True, "min": 16, "max": 30, "step": 0.5},
                "target_temperature": {"settable": True}
            }
        }

        discoveries = generator.generate_device_discovery("thermo1", device_config)

        assert len(discoveries) == 1
        discovery = discoveries[0]

        assert discovery['topic'] == "homeassistant/climate/test_thermo1/config"
        payload = discovery['payload']

        assert payload['unique_id'] == "test_thermo1_climate"
        assert payload['modes'] == ["auto", "cool", "heat", "off"]
        assert payload['min_temp'] == 16
        assert payload['max_temp'] == 30
        assert payload['temp_step'] == 0.5

    def test_climate_temperature_topics(self):
        """Should include temperature state and command topics"""
        generator = DiscoveryGenerator(
            base_topic="IoT2mqtt",
            instance_id="test"
        )

        device_config = {
            "device_id": "ac1",
            "class": "climate.ac",
            "capabilities": {
                "mode": {"settable": True, "options": ["auto", "cool", "off"]},
                "target_temperature": {"settable": True}
            }
        }

        discoveries = generator.generate_device_discovery("ac1", device_config)
        payload = discoveries[0]['payload']

        assert 'temperature_state_topic' in payload
        assert 'temperature_command_topic' in payload
        assert payload['temperature_state_template'] == "{{ value_json.state.target_temperature }}"


# ============================================================================
# TIER 1 - CRITICAL TESTS: Fan Platform Discovery
# ============================================================================

class TestFanDiscovery:
    """Test fan platform discovery generation"""

    def test_generate_fan_discovery(self):
        """Should generate fan entity discovery"""
        generator = DiscoveryGenerator(
            base_topic="IoT2mqtt",
            instance_id="test"
        )

        device_config = {
            "device_id": "fan1",
            "friendly_name": "Ceiling Fan",
            "class": "climate.air_purifier",  # Maps to fan platform
            "capabilities": {
                "speed": {"settable": True, "min": 1, "max": 100}
            }
        }

        discoveries = generator.generate_device_discovery("fan1", device_config)

        assert len(discoveries) == 1
        discovery = discoveries[0]

        assert discovery['topic'] == "homeassistant/fan/test_fan1/config"
        payload = discovery['payload']

        assert payload['unique_id'] == "test_fan1_fan"

    def test_fan_with_speed_control(self):
        """Should include percentage control for fan speed"""
        generator = DiscoveryGenerator(
            base_topic="IoT2mqtt",
            instance_id="test"
        )

        device_config = {
            "device_id": "fan1",
            "class": "climate.air_purifier",
            "capabilities": {
                "speed": {"settable": True, "min": 1, "max": 100}
            }
        }

        discoveries = generator.generate_device_discovery("fan1", device_config)
        payload = discoveries[0]['payload']

        assert 'percentage_state_topic' in payload
        assert 'percentage_command_topic' in payload
        assert payload['speed_range_min'] == 1
        assert payload['speed_range_max'] == 100


# ============================================================================
# TIER 1 - CRITICAL TESTS: Device Info Generation
# ============================================================================

class TestDeviceInfo:
    """Test device info generation"""

    def test_device_info_with_identifiers(self):
        """Should generate device info with unique identifiers"""
        generator = DiscoveryGenerator(
            base_topic="IoT2mqtt",
            instance_id="test_instance"
        )

        device_config = {
            "device_id": "device123",
            "friendly_name": "Test Device",
            "class": "switch.outlet",
            "model": "Switch Pro",
            "manufacturer": "SmartCo",
            "capabilities": {}
        }

        discoveries = generator.generate_device_discovery("device123", device_config)
        payload = discoveries[0]['payload']

        device_info = payload['device']
        assert device_info['identifiers'] == ["test_instance_device123"]
        assert device_info['name'] == "Test Device"
        assert device_info['model'] == "Switch Pro"
        assert device_info['manufacturer'] == "SmartCo"

    def test_device_info_via_device_for_parasitic(self):
        """Should include via_device for parasitic connectors"""
        generator = DiscoveryGenerator(
            base_topic="IoT2mqtt",
            instance_id="test_instance"
        )

        device_config = {
            "device_id": "device1",
            "class": "switch.outlet",
            "capabilities": {}
        }

        discoveries = generator.generate_device_discovery("device1", device_config)
        payload = discoveries[0]['payload']

        device_info = payload['device']
        # via_device should be the instance_id
        assert device_info['via_device'] == "test_instance"

    def test_device_info_suggested_area(self):
        """Should include suggested_area if provided"""
        generator = DiscoveryGenerator(
            base_topic="IoT2mqtt",
            instance_id="test"
        )

        device_config = {
            "device_id": "light1",
            "class": "light.dimmable",
            "area": "Living Room",
            "capabilities": {}
        }

        discoveries = generator.generate_device_discovery("light1", device_config)
        payload = discoveries[0]['payload']

        device_info = payload['device']
        assert device_info['suggested_area'] == "Living Room"

    def test_device_info_filters_none_values(self):
        """Should not include None values in device info"""
        generator = DiscoveryGenerator(
            base_topic="IoT2mqtt",
            instance_id="test"
        )

        device_config = {
            "device_id": "device1",
            "class": "switch.outlet",
            # No sw_version, hw_version provided
            "capabilities": {}
        }

        discoveries = generator.generate_device_discovery("device1", device_config)
        payload = discoveries[0]['payload']

        device_info = payload['device']
        assert 'sw_version' not in device_info
        assert 'hw_version' not in device_info


# ============================================================================
# TIER 1 - CRITICAL TESTS: Discovery Topic Format
# ============================================================================

class TestDiscoveryTopicFormat:
    """Test HA discovery topic format validation"""

    def test_discovery_topic_format_standard(self):
        """Should use standard HA discovery topic format"""
        generator = DiscoveryGenerator(
            base_topic="IoT2mqtt",
            discovery_prefix="homeassistant",
            instance_id="my_instance"
        )

        device_config = {
            "device_id": "dev123",
            "class": "light.dimmable",
            "capabilities": {}
        }

        discoveries = generator.generate_device_discovery("dev123", device_config)

        # Format: {discovery_prefix}/{platform}/{node_id}/config
        expected = "homeassistant/light/my_instance_dev123/config"
        assert discoveries[0]['topic'] == expected

    def test_discovery_topic_with_custom_prefix(self):
        """Should use custom discovery prefix in topic"""
        generator = DiscoveryGenerator(
            base_topic="IoT2mqtt",
            discovery_prefix="custom_discovery",
            instance_id="test"
        )

        device_config = {
            "device_id": "switch1",
            "class": "switch.outlet",
            "capabilities": {}
        }

        discoveries = generator.generate_device_discovery("switch1", device_config)

        assert discoveries[0]['topic'].startswith("custom_discovery/")

    def test_state_topic_format(self):
        """Should generate correct state topic in discovery payload"""
        generator = DiscoveryGenerator(
            base_topic="IoT2mqtt",
            instance_id="test_instance"
        )

        device_config = {
            "device_id": "device1",
            "class": "switch.outlet",
            "capabilities": {}
        }

        discoveries = generator.generate_device_discovery("device1", device_config)
        payload = discoveries[0]['payload']

        expected_state = "IoT2mqtt/v1/instances/test_instance/devices/device1/state"
        assert payload['state_topic'] == expected_state

    def test_command_topic_format(self):
        """Should generate correct command topic in discovery payload"""
        generator = DiscoveryGenerator(
            base_topic="IoT2mqtt",
            instance_id="test_instance"
        )

        device_config = {
            "device_id": "device1",
            "class": "light.dimmable",
            "capabilities": {}
        }

        discoveries = generator.generate_device_discovery("device1", device_config)
        payload = discoveries[0]['payload']

        expected_cmd = "IoT2mqtt/v1/instances/test_instance/devices/device1/cmd"
        assert payload['command_topic'] == expected_cmd


# ============================================================================
# TIER 1 - CRITICAL TESTS: Discovery Removal
# ============================================================================

class TestDiscoveryRemoval:
    """Test discovery message removal"""

    def test_remove_discovery_for_device(self):
        """Should generate removal messages for device"""
        generator = DiscoveryGenerator(
            base_topic="IoT2mqtt",
            discovery_prefix="homeassistant",
            instance_id="test"
        )

        removals = generator.remove_discovery("device1", device_class="switch.outlet")

        assert len(removals) == 1
        removal = removals[0]

        assert removal['topic'] == "homeassistant/switch/test_device1/config"
        assert removal['payload'] == ""  # Empty payload removes device
        assert removal['retain'] is True

    def test_remove_discovery_all_platforms(self):
        """Should generate removal for all common platforms if class not specified"""
        generator = DiscoveryGenerator(
            base_topic="IoT2mqtt",
            discovery_prefix="homeassistant",
            instance_id="test"
        )

        removals = generator.remove_discovery("device1")

        # Should try common platforms: light, switch, sensor, binary_sensor, climate, fan
        assert len(removals) == 6

        platforms = [r['topic'].split('/')[1] for r in removals]
        assert 'light' in platforms
        assert 'switch' in platforms
        assert 'sensor' in platforms


# ============================================================================
# Additional Edge Cases
# ============================================================================

class TestEdgeCases:
    """Test edge cases and error handling"""

    def test_unknown_device_class_defaults_to_switch(self):
        """Should default to switch platform for unknown device class"""
        generator = DiscoveryGenerator(
            base_topic="IoT2mqtt",
            instance_id="test"
        )

        device_config = {
            "device_id": "unknown1",
            "class": "unknown.device.type",
            "capabilities": {}
        }

        discoveries = generator.generate_device_discovery("unknown1", device_config)

        # Should default to switch
        assert len(discoveries) == 1
        assert 'switch' in discoveries[0]['topic']

    def test_device_with_no_capabilities(self):
        """Should handle devices with empty capabilities"""
        generator = DiscoveryGenerator(
            base_topic="IoT2mqtt",
            instance_id="test"
        )

        device_config = {
            "device_id": "simple1",
            "class": "light.switch",
            "capabilities": {}
        }

        discoveries = generator.generate_device_discovery("simple1", device_config)

        # Should still generate discovery
        assert len(discoveries) == 1
        payload = discoveries[0]['payload']

        # Should have onoff as default color mode
        assert "onoff" in payload['supported_color_modes']

    def test_sensor_with_only_settable_capabilities_ignored(self):
        """Should only create sensor entities for non-settable capabilities"""
        generator = DiscoveryGenerator(
            base_topic="IoT2mqtt",
            instance_id="test"
        )

        device_config = {
            "device_id": "sensor1",
            "class": "sensor.temperature",
            "capabilities": {
                "temperature": {"settable": True},  # Settable, not a sensor
                "humidity": {"settable": False}     # Non-settable, is a sensor
            }
        }

        discoveries = generator.generate_device_discovery("sensor1", device_config)

        # Should only generate for humidity
        assert len(discoveries) == 1
        assert 'humidity' in discoveries[0]['topic']


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
