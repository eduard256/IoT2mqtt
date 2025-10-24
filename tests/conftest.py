"""
Shared pytest fixtures for IoT2MQTT tests
"""

import os
import json
import tempfile
import pytest
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime


@pytest.fixture
def temp_dir():
    """Create a temporary directory for tests"""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def temp_config_file(temp_dir):
    """Create a temporary config file with sample configuration"""
    config = {
        "instance_id": "test_instance",
        "connector_type": "test",
        "mqtt": {
            "qos": 1,
            "retain_state": True
        },
        "ha_discovery_enabled": True,
        "ha_discovery_prefix": "homeassistant",
        "update_interval": 10,
        "devices": [
            {
                "device_id": "test_device_1",
                "friendly_name": "Test Device 1",
                "enabled": True,
                "model": "Test Model",
                "class": "light.dimmable",
                "ip": "192.168.1.100",
                "capabilities": {
                    "brightness": {"settable": True, "min": 0, "max": 100},
                    "power": {"settable": True}
                }
            },
            {
                "device_id": "test_device_2",
                "friendly_name": "Test Device 2",
                "enabled": False,
                "model": "Test Model",
                "class": "switch.outlet"
            }
        ],
        "groups": [
            {
                "group_id": "test_group",
                "devices": ["test_device_1", "test_device_2"]
            }
        ]
    }

    # Create instances directory
    instances_dir = temp_dir / "instances"
    instances_dir.mkdir(exist_ok=True)

    config_file = instances_dir / "test_instance.json"
    with open(config_file, 'w') as f:
        json.dump(config, f, indent=2)

    return config_file


@pytest.fixture
def parasite_config_file(temp_dir):
    """Create a config file with parasitic mode enabled"""
    config = {
        "instance_id": "motion_detector",
        "connector_type": "cameras-motion",
        "mqtt": {
            "qos": 1,
            "retain_state": True
        },
        "update_interval": 5,
        "config": {
            "parasite_targets": [
                {
                    "mqtt_path": "IoT2mqtt/v1/instances/cameras/devices/camera_1",
                    "device_id": "camera_1",
                    "instance_id": "cameras",
                    "extracted_data": {
                        "ip": "192.168.1.10",
                        "rtsp_url": "rtsp://192.168.1.10/stream"
                    }
                },
                {
                    "mqtt_path": "IoT2mqtt/v1/instances/cameras/devices/camera_2/state",
                    "device_id": "camera_2",
                    "instance_id": "cameras"
                }
            ]
        },
        "devices": [
            {
                "device_id": "camera_1",
                "enabled": True,
                "friendly_name": "Camera 1 Motion"
            }
        ]
    }

    instances_dir = temp_dir / "instances"
    instances_dir.mkdir(exist_ok=True)

    config_file = instances_dir / "motion_detector.json"
    with open(config_file, 'w') as f:
        json.dump(config, f, indent=2)

    return config_file


@pytest.fixture
def invalid_json_config_file(temp_dir):
    """Create an invalid JSON config file"""
    instances_dir = temp_dir / "instances"
    instances_dir.mkdir(exist_ok=True)

    config_file = instances_dir / "invalid.json"
    with open(config_file, 'w') as f:
        f.write("{ invalid json content")

    return config_file


@pytest.fixture
def mock_mqtt_client():
    """Create a mock MQTT client"""
    mock_client = MagicMock()
    mock_client.connected = True
    mock_client.base_topic = "IoT2mqtt"
    mock_client.instance_id = "test_instance"
    mock_client.connect.return_value = True
    mock_client.disconnect.return_value = None
    mock_client.publish_state.return_value = None
    mock_client.publish_error.return_value = None
    mock_client.subscribe.return_value = None
    mock_client.subscribe_external_topic.return_value = None
    mock_client.publish.return_value = None
    mock_client.publish_to_external_topic.return_value = None
    mock_client.publish_ha_discovery.return_value = None

    return mock_client


@pytest.fixture
def mock_discovery_generator():
    """Create a mock DiscoveryGenerator"""
    mock_generator = MagicMock()
    mock_generator.generate_device_discovery.return_value = [
        {
            "topic": "homeassistant/light/test_instance_test_device_1/config",
            "payload": {
                "unique_id": "test_instance_test_device_1_light",
                "name": "Test Device 1",
                "state_topic": "IoT2mqtt/v1/instances/test_instance/devices/test_device_1/state"
            },
            "retain": True
        }
    ]

    return mock_generator


@pytest.fixture
def mock_env_vars(monkeypatch, temp_dir):
    """Set up environment variables for testing"""
    monkeypatch.setenv("INSTANCE_NAME", "test_instance")
    monkeypatch.setenv("CONNECTOR_TYPE", "test")
    monkeypatch.setenv("MQTT_HOST", "localhost")
    monkeypatch.setenv("MQTT_PORT", "1883")
    monkeypatch.setenv("MQTT_USERNAME", "test_user")
    monkeypatch.setenv("MQTT_PASSWORD", "test_pass")
    monkeypatch.setenv("MQTT_BASE_TOPIC", "IoT2mqtt")
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")

    # Change to temp directory for config file resolution
    original_cwd = os.getcwd()
    os.chdir(temp_dir)

    yield

    # Restore original directory
    os.chdir(original_cwd)


@pytest.fixture
def sample_device_state():
    """Sample device state for testing"""
    return {
        "online": True,
        "power": True,
        "brightness": 80,
        "color_temp": 4000,
        "timestamp": datetime.now().isoformat()
    }


@pytest.fixture
def sample_command_payload():
    """Sample command payload for testing"""
    return {
        "id": "test-cmd-123",
        "timestamp": datetime.now().isoformat(),
        "values": {
            "power": True,
            "brightness": 90
        },
        "timeout": 5000
    }


@pytest.fixture
def sample_parent_state():
    """Sample parent device state for parasitic testing"""
    return {
        "timestamp": datetime.now().isoformat(),
        "device_id": "camera_1",
        "state": {
            "online": True,
            "stream_urls": {
                "rtsp": "rtsp://192.168.1.10:554/stream",
                "jpeg": "http://192.168.1.10/snapshot.jpg"
            },
            "ip": "192.168.1.10",
            "recording": True
        }
    }
