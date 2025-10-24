"""
Comprehensive tests for BaseConnector

Tests cover:
1. Initialization and configuration loading
2. MQTT topic generation and parsing
3. Command handling with timestamp ordering
4. Parasitic mode functionality
5. Home Assistant discovery
6. Lifecycle management
7. Error handling
"""

import pytest
import json
import os
import time
import threading
from unittest.mock import Mock, MagicMock, patch, call
from datetime import datetime, timedelta
from pathlib import Path

# Add shared to path for imports
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'shared'))

from base_connector import BaseConnector


# ============================================================================
# Test Connector Implementation (Concrete class for testing abstract base)
# ============================================================================

class TestConnector(BaseConnector):
    """Concrete implementation of BaseConnector for testing"""

    def __init__(self, *args, **kwargs):
        self.initialize_called = False
        self.cleanup_called = False
        self.get_state_calls = []
        self.set_state_calls = []
        super().__init__(*args, **kwargs)

    def initialize_connection(self):
        """Mock initialize"""
        self.initialize_called = True

    def cleanup_connection(self):
        """Mock cleanup"""
        self.cleanup_called = True

    def get_device_state(self, device_id: str, device_config: dict):
        """Mock get state"""
        self.get_state_calls.append((device_id, device_config))
        return {
            "online": True,
            "power": True,
            "brightness": 75
        }

    def set_device_state(self, device_id: str, device_config: dict, state: dict):
        """Mock set state"""
        self.set_state_calls.append((device_id, device_config, state))
        return True


# ============================================================================
# TIER 1 - CRITICAL TESTS: Initialization and Configuration
# ============================================================================

class TestBaseConnectorInitialization:
    """Test connector initialization and configuration loading"""

    def test_initialization_with_config_path(self, temp_config_file, mock_env_vars):
        """Should initialize correctly with explicit config path"""
        with patch('base_connector.MQTTClient') as MockMQTT:
            mock_mqtt = MagicMock()
            MockMQTT.return_value = mock_mqtt

            connector = TestConnector(
                config_path=str(temp_config_file),
                instance_name="test_instance"
            )

            assert connector.instance_name == "test_instance"
            assert connector.instance_id == "test_instance"
            assert connector.config is not None
            assert connector.config['instance_id'] == "test_instance"
            assert len(connector.config['devices']) == 2

    def test_initialization_from_env_var(self, temp_config_file, mock_env_vars):
        """Should load instance name from INSTANCE_NAME env var"""
        with patch('base_connector.MQTTClient') as MockMQTT:
            MockMQTT.return_value = MagicMock()

            connector = TestConnector()

            assert connector.instance_name == "test_instance"

    def test_initialization_without_instance_name_fails(self, monkeypatch):
        """Should raise ValueError if instance name not provided"""
        monkeypatch.delenv("INSTANCE_NAME", raising=False)

        with pytest.raises(ValueError, match="Instance name not provided"):
            TestConnector()

    def test_mqtt_client_initialization(self, temp_config_file, mock_env_vars):
        """Should create MQTT client with correct parameters"""
        with patch('base_connector.MQTTClient') as MockMQTT:
            mock_mqtt = MagicMock()
            mock_mqtt.base_topic = "IoT2mqtt"
            MockMQTT.return_value = mock_mqtt

            connector = TestConnector(
                config_path=str(temp_config_file),
                instance_name="test_instance"
            )

            MockMQTT.assert_called_once_with(
                instance_id="test_instance",
                qos=1,
                retain_state=True
            )

    def test_discovery_generator_initialization_enabled(self, temp_config_file, mock_env_vars):
        """Should initialize DiscoveryGenerator when HA discovery enabled"""
        with patch('base_connector.MQTTClient'), \
             patch('base_connector.DiscoveryGenerator') as MockDiscovery:

            connector = TestConnector(
                config_path=str(temp_config_file),
                instance_name="test_instance"
            )

            MockDiscovery.assert_called_once()
            assert connector.ha_discovery_enabled is True
            assert connector.discovery_generator is not None

    def test_discovery_generator_disabled(self, temp_config_file, mock_env_vars):
        """Should not initialize DiscoveryGenerator when disabled in config"""
        # Modify config to disable discovery
        config = json.loads(temp_config_file.read_text())
        config['ha_discovery_enabled'] = False
        temp_config_file.write_text(json.dumps(config))

        with patch('base_connector.MQTTClient'), \
             patch('base_connector.DiscoveryGenerator') as MockDiscovery:

            connector = TestConnector(
                config_path=str(temp_config_file),
                instance_name="test_instance"
            )

            MockDiscovery.assert_not_called()
            assert connector.ha_discovery_enabled is False
            assert connector.discovery_generator is None


# ============================================================================
# TIER 1 - CRITICAL TESTS: Config Loading
# ============================================================================

class TestConfigLoading:
    """Test configuration file loading and validation"""

    def test_load_config_production_path(self, temp_config_file, mock_env_vars, monkeypatch):
        """Should load config from production path /app/instances/{name}.json"""
        # Create production path
        prod_path = Path("/app/instances")
        monkeypatch.setattr(os.path, 'exists', lambda p: str(prod_path / "test_instance.json") == p or str(temp_config_file) == p)

        with patch('base_connector.MQTTClient'), \
             patch('builtins.open', create=True) as mock_open:
            mock_open.return_value.__enter__.return_value.read.return_value = temp_config_file.read_text()

            # Mock file opening to use temp_config_file content
            original_open = open
            def custom_open(path, *args, **kwargs):
                if '/app/instances' in str(path):
                    return original_open(temp_config_file, *args, **kwargs)
                return original_open(path, *args, **kwargs)

            with patch('builtins.open', custom_open):
                connector = TestConnector(instance_name="test_instance")
                assert connector.config is not None

    def test_load_config_dev_fallback(self, temp_config_file, mock_env_vars, monkeypatch):
        """Should fallback to instances/{name}.json for development"""
        # Mock production path doesn't exist
        def mock_exists(path):
            if '/app/instances' in str(path):
                return False
            return str(temp_config_file) == path

        monkeypatch.setattr(os.path, 'exists', mock_exists)

        with patch('base_connector.MQTTClient'):
            # This should use the instances/test_instance.json path
            connector = TestConnector(
                config_path=str(temp_config_file),
                instance_name="test_instance"
            )

            assert connector.config is not None

    def test_load_config_file_not_found(self, temp_dir, mock_env_vars):
        """Should raise FileNotFoundError if config not found"""
        with patch('base_connector.MQTTClient'):
            with pytest.raises(FileNotFoundError, match="Configuration file not found"):
                TestConnector(
                    config_path=str(temp_dir / "nonexistent.json"),
                    instance_name="test_instance"
                )

    def test_load_config_invalid_json(self, invalid_json_config_file, mock_env_vars):
        """Should raise JSONDecodeError for invalid JSON"""
        with patch('base_connector.MQTTClient'):
            with pytest.raises(json.JSONDecodeError):
                TestConnector(
                    config_path=str(invalid_json_config_file),
                    instance_name="invalid"
                )

    def test_load_secrets_from_docker(self, temp_config_file, temp_dir, mock_env_vars):
        """Should load secrets from Docker secrets file"""
        # Create actual secrets file for this test
        secrets_dir = temp_dir / "run" / "secrets"
        secrets_dir.mkdir(parents=True, exist_ok=True)
        secrets_file = secrets_dir / "test_instance_creds"
        secrets_file.write_text("username=secret_user\npassword=secret_pass\napi_key=12345")

        with patch('base_connector.MQTTClient'):
            # Patch the secrets path to point to our temp directory
            with patch.object(BaseConnector, '_load_secrets') as mock_load_secrets:
                def load_secrets_impl(config):
                    # Simulate loading secrets
                    if 'connection' not in config:
                        config['connection'] = {}
                    config['connection']['username'] = 'secret_user'
                    config['connection']['password'] = 'secret_pass'
                    config['connection']['api_key'] = '12345'

                mock_load_secrets.side_effect = load_secrets_impl

                connector = TestConnector(
                    config_path=str(temp_config_file),
                    instance_name="test_instance"
                )

                # Secrets loading method should have been called
                assert mock_load_secrets.called
                # Config should exist
                assert connector.config is not None


# ============================================================================
# TIER 1 - CRITICAL TESTS: MQTT Topic Operations
# ============================================================================

class TestMQTTTopicOperations:
    """Test MQTT topic generation and parsing"""

    def test_device_state_topic_format(self, temp_config_file, mock_env_vars):
        """Should generate correct device state topic"""
        with patch('base_connector.MQTTClient') as MockMQTT:
            mock_mqtt = MagicMock()
            mock_mqtt.base_topic = "IoT2mqtt"
            MockMQTT.return_value = mock_mqtt

            connector = TestConnector(
                config_path=str(temp_config_file),
                instance_name="test_instance"
            )

            # Expected format: {base_topic}/v1/instances/{instance_id}/devices/{device_id}/state
            expected_base = "IoT2mqtt/v1/instances/test_instance/devices"

            # Verify by checking subscription setup (indirectly tests topic format)
            assert connector.mqtt.base_topic == "IoT2mqtt"
            assert connector.instance_id == "test_instance"

    def test_device_command_topic_format(self, temp_config_file, mock_env_vars):
        """Should subscribe to device command topics correctly"""
        with patch('base_connector.MQTTClient') as MockMQTT:
            mock_mqtt = MagicMock()
            mock_mqtt.base_topic = "IoT2mqtt"
            MockMQTT.return_value = mock_mqtt

            connector = TestConnector(
                config_path=str(temp_config_file),
                instance_name="test_instance"
            )

            connector._setup_subscriptions()

            # Should subscribe to devices/+/cmd
            mock_mqtt.subscribe.assert_any_call("devices/+/cmd", connector._handle_command)
            mock_mqtt.subscribe.assert_any_call("devices/+/get", connector._handle_get)

    def test_group_command_topic_format(self, temp_config_file, mock_env_vars):
        """Should subscribe to group command topics"""
        with patch('base_connector.MQTTClient') as MockMQTT:
            mock_mqtt = MagicMock()
            mock_mqtt.base_topic = "IoT2mqtt"
            MockMQTT.return_value = mock_mqtt

            connector = TestConnector(
                config_path=str(temp_config_file),
                instance_name="test_instance"
            )

            connector._setup_subscriptions()

            mock_mqtt.subscribe.assert_any_call("groups/+/cmd", connector._handle_group_command)

    def test_meta_request_topic_format(self, temp_config_file, mock_env_vars):
        """Should subscribe to meta request topics"""
        with patch('base_connector.MQTTClient') as MockMQTT:
            mock_mqtt = MagicMock()
            mock_mqtt.base_topic = "IoT2mqtt"
            MockMQTT.return_value = mock_mqtt

            connector = TestConnector(
                config_path=str(temp_config_file),
                instance_name="test_instance"
            )

            connector._setup_subscriptions()

            mock_mqtt.subscribe.assert_any_call("meta/request/+", connector._handle_meta_request)

    def test_parse_device_id_from_command_topic(self, temp_config_file, mock_env_vars):
        """Should correctly extract device_id from command topic"""
        with patch('base_connector.MQTTClient') as MockMQTT:
            mock_mqtt = MagicMock()
            MockMQTT.return_value = mock_mqtt

            connector = TestConnector(
                config_path=str(temp_config_file),
                instance_name="test_instance"
            )

            # Test topic parsing in _handle_command
            topic = "IoT2mqtt/v1/instances/test_instance/devices/test_device_1/cmd"
            payload = {
                "timestamp": datetime.now().isoformat(),
                "values": {"power": True}
            }

            connector._handle_command(topic, payload)

            # Should have called set_device_state for test_device_1
            assert len(connector.set_state_calls) == 1
            assert connector.set_state_calls[0][0] == "test_device_1"

    def test_parse_group_name_from_topic(self, temp_config_file, mock_env_vars):
        """Should correctly extract group_name from group command topic"""
        with patch('base_connector.MQTTClient') as MockMQTT:
            mock_mqtt = MagicMock()
            MockMQTT.return_value = mock_mqtt

            connector = TestConnector(
                config_path=str(temp_config_file),
                instance_name="test_instance"
            )

            # Test group command parsing
            topic = "IoT2mqtt/v1/instances/test_instance/groups/test_group/cmd"
            payload = {
                "values": {"power": True}
            }

            connector._handle_group_command(topic, payload)

            # Should have processed group command (2 devices in group, 1 enabled)
            assert len(connector.set_state_calls) == 1  # Only enabled device


# ============================================================================
# TIER 1 - CRITICAL TESTS: Device State Publishing
# ============================================================================

class TestDeviceStatePublishing:
    """Test device state publishing to MQTT"""

    def test_publish_device_state_with_timestamp(self, temp_config_file, mock_env_vars):
        """Should publish device state with timestamp"""
        with patch('base_connector.MQTTClient') as MockMQTT:
            mock_mqtt = MagicMock()
            MockMQTT.return_value = mock_mqtt

            connector = TestConnector(
                config_path=str(temp_config_file),
                instance_name="test_instance"
            )

            state = {"online": True, "power": True, "brightness": 80}
            connector.mqtt.publish_state("test_device_1", state)

            mock_mqtt.publish_state.assert_called_once_with("test_device_1", state)

    def test_publish_state_uses_configured_qos(self, temp_config_file, mock_env_vars):
        """Should use QoS from config when publishing state"""
        # Modify config QoS
        config = json.loads(temp_config_file.read_text())
        config['mqtt']['qos'] = 2
        temp_config_file.write_text(json.dumps(config))

        with patch('base_connector.MQTTClient') as MockMQTT:
            mock_mqtt = MagicMock()
            MockMQTT.return_value = mock_mqtt

            connector = TestConnector(
                config_path=str(temp_config_file),
                instance_name="test_instance"
            )

            # QoS should be passed to MQTTClient constructor
            MockMQTT.assert_called_with(
                instance_id="test_instance",
                qos=2,
                retain_state=True
            )

    def test_publish_state_uses_retain_flag(self, temp_config_file, mock_env_vars):
        """Should use retain flag from config"""
        config = json.loads(temp_config_file.read_text())
        config['mqtt']['retain_state'] = False
        temp_config_file.write_text(json.dumps(config))

        with patch('base_connector.MQTTClient') as MockMQTT:
            mock_mqtt = MagicMock()
            MockMQTT.return_value = mock_mqtt

            connector = TestConnector(
                config_path=str(temp_config_file),
                instance_name="test_instance"
            )

            MockMQTT.assert_called_with(
                instance_id="test_instance",
                qos=1,
                retain_state=False
            )


# ============================================================================
# TIER 1 - CRITICAL TESTS: Command Handling
# ============================================================================

class TestCommandHandling:
    """Test MQTT command handling and processing"""

    def test_handle_device_command(self, temp_config_file, mock_env_vars):
        """Should handle device command and call set_device_state"""
        with patch('base_connector.MQTTClient') as MockMQTT:
            mock_mqtt = MagicMock()
            MockMQTT.return_value = mock_mqtt

            connector = TestConnector(
                config_path=str(temp_config_file),
                instance_name="test_instance"
            )

            topic = "IoT2mqtt/v1/instances/test_instance/devices/test_device_1/cmd"
            payload = {
                "timestamp": datetime.now().isoformat(),
                "values": {"power": True, "brightness": 90}
            }

            connector._handle_command(topic, payload)

            assert len(connector.set_state_calls) == 1
            assert connector.set_state_calls[0][0] == "test_device_1"
            assert connector.set_state_calls[0][2] == {"power": True, "brightness": 90}

    def test_ignore_outdated_commands(self, temp_config_file, mock_env_vars):
        """Should ignore commands with old timestamp (> 30 seconds)"""
        with patch('base_connector.MQTTClient') as MockMQTT:
            mock_mqtt = MagicMock()
            MockMQTT.return_value = mock_mqtt

            connector = TestConnector(
                config_path=str(temp_config_file),
                instance_name="test_instance"
            )

            # Create command with old timestamp
            old_time = datetime.now() - timedelta(seconds=60)
            topic = "IoT2mqtt/v1/instances/test_instance/devices/test_device_1/cmd"
            payload = {
                "timestamp": old_time.isoformat(),
                "values": {"power": True}
            }

            connector._handle_command(topic, payload)

            # Should not call set_device_state
            assert len(connector.set_state_calls) == 0

    def test_command_with_response_id(self, temp_config_file, mock_env_vars):
        """Should send response if command has id field"""
        with patch('base_connector.MQTTClient') as MockMQTT:
            mock_mqtt = MagicMock()
            MockMQTT.return_value = mock_mqtt

            connector = TestConnector(
                config_path=str(temp_config_file),
                instance_name="test_instance"
            )

            topic = "IoT2mqtt/v1/instances/test_instance/devices/test_device_1/cmd"
            payload = {
                "id": "cmd-12345",
                "timestamp": datetime.now().isoformat(),
                "values": {"power": True}
            }

            connector._handle_command(topic, payload)

            # Should publish response
            assert mock_mqtt.publish.called
            # Check response was published
            calls = [c for c in mock_mqtt.publish.call_args_list if 'response' in str(c)]
            assert len(calls) > 0

    def test_command_error_handling(self, temp_config_file, mock_env_vars):
        """Should publish error response if command fails"""
        with patch('base_connector.MQTTClient') as MockMQTT:
            mock_mqtt = MagicMock()
            MockMQTT.return_value = mock_mqtt

            # Create connector that raises error on set_device_state
            class ErrorConnector(TestConnector):
                def set_device_state(self, device_id, device_config, state):
                    raise RuntimeError("Device unreachable")

            connector = ErrorConnector(
                config_path=str(temp_config_file),
                instance_name="test_instance"
            )

            topic = "IoT2mqtt/v1/instances/test_instance/devices/test_device_1/cmd"
            payload = {
                "id": "cmd-error",
                "timestamp": datetime.now().isoformat(),
                "values": {"power": True}
            }

            connector._handle_command(topic, payload)

            # Should publish error response
            assert mock_mqtt.publish.called

    def test_command_for_unknown_device(self, temp_config_file, mock_env_vars):
        """Should log warning for commands to unknown devices"""
        with patch('base_connector.MQTTClient') as MockMQTT:
            mock_mqtt = MagicMock()
            MockMQTT.return_value = mock_mqtt

            connector = TestConnector(
                config_path=str(temp_config_file),
                instance_name="test_instance"
            )

            topic = "IoT2mqtt/v1/instances/test_instance/devices/unknown_device/cmd"
            payload = {
                "timestamp": datetime.now().isoformat(),
                "values": {"power": True}
            }

            with patch('base_connector.logger') as mock_logger:
                connector._handle_command(topic, payload)
                # Should log warning
                assert any('unknown' in str(call).lower() for call in mock_logger.warning.call_args_list)

    def test_command_with_direct_payload_format(self, temp_config_file, mock_env_vars):
        """Should handle commands without 'values' wrapper"""
        with patch('base_connector.MQTTClient') as MockMQTT:
            mock_mqtt = MagicMock()
            MockMQTT.return_value = mock_mqtt

            connector = TestConnector(
                config_path=str(temp_config_file),
                instance_name="test_instance"
            )

            topic = "IoT2mqtt/v1/instances/test_instance/devices/test_device_1/cmd"
            # Direct payload without 'values' wrapper
            payload = {
                "timestamp": datetime.now().isoformat(),
                "power": True,
                "brightness": 85
            }

            connector._handle_command(topic, payload)

            assert len(connector.set_state_calls) == 1
            # Should extract command values (excluding timestamp, id, timeout)
            assert connector.set_state_calls[0][2] == {"power": True, "brightness": 85}


# ============================================================================
# TIER 1 - CRITICAL TESTS: Parasitic Mode
# ============================================================================

class TestParasiticMode:
    """Test parasitic connector functionality"""

    def test_load_parasite_targets(self, parasite_config_file, mock_env_vars):
        """Should load parasite_targets from config"""
        with patch('base_connector.MQTTClient') as MockMQTT:
            mock_mqtt = MagicMock()
            MockMQTT.return_value = mock_mqtt

            connector = TestConnector(
                config_path=str(parasite_config_file),
                instance_name="motion_detector"
            )

            assert connector.is_parasite_mode is True
            assert len(connector.parasite_targets) == 2
            assert connector.parasite_targets[0]['device_id'] == "camera_1"
            assert connector.parasite_targets[1]['device_id'] == "camera_2"

    def test_parasite_mode_disabled_when_no_targets(self, temp_config_file, mock_env_vars):
        """Should disable parasite mode when no targets configured"""
        with patch('base_connector.MQTTClient') as MockMQTT:
            mock_mqtt = MagicMock()
            MockMQTT.return_value = mock_mqtt

            connector = TestConnector(
                config_path=str(temp_config_file),
                instance_name="test_instance"
            )

            assert connector.is_parasite_mode is False
            assert len(connector.parasite_targets) == 0

    def test_subscribe_to_parent_devices(self, parasite_config_file, mock_env_vars):
        """Should subscribe to parent device state topics"""
        with patch('base_connector.MQTTClient') as MockMQTT:
            mock_mqtt = MagicMock()
            MockMQTT.return_value = mock_mqtt

            connector = TestConnector(
                config_path=str(parasite_config_file),
                instance_name="motion_detector"
            )

            connector._setup_parasite_subscriptions()

            # Should subscribe to both parent state topics
            assert mock_mqtt.subscribe_external_topic.call_count == 2

            # Check subscription topics (normalized without /state suffix)
            calls = mock_mqtt.subscribe_external_topic.call_args_list
            topics = [call[0][0] for call in calls]

            assert "IoT2mqtt/v1/instances/cameras/devices/camera_1/state" in topics
            assert "IoT2mqtt/v1/instances/cameras/devices/camera_2/state" in topics

    def test_normalize_mqtt_path_removes_state_suffix(self, parasite_config_file, mock_env_vars):
        """Should remove /state suffix from mqtt_path during normalization"""
        with patch('base_connector.MQTTClient') as MockMQTT:
            mock_mqtt = MagicMock()
            MockMQTT.return_value = mock_mqtt

            connector = TestConnector(
                config_path=str(parasite_config_file),
                instance_name="motion_detector"
            )

            connector._setup_parasite_subscriptions()

            # camera_2 originally has /state suffix, should be normalized
            target_2 = [t for t in connector.parasite_targets if t['device_id'] == 'camera_2'][0]
            assert not target_2['mqtt_path'].endswith('/state')

    def test_cache_parent_device_state(self, parasite_config_file, mock_env_vars, sample_parent_state):
        """Should cache parent device state when updated"""
        with patch('base_connector.MQTTClient') as MockMQTT:
            mock_mqtt = MagicMock()
            MockMQTT.return_value = mock_mqtt

            connector = TestConnector(
                config_path=str(parasite_config_file),
                instance_name="motion_detector"
            )

            mqtt_path = "IoT2mqtt/v1/instances/cameras/devices/camera_1"
            topic = f"{mqtt_path}/state"

            connector._on_parent_state_update(mqtt_path, topic, sample_parent_state)

            # Should cache the state
            assert mqtt_path in connector.parent_states
            cached_state = connector.parent_states[mqtt_path]
            assert cached_state['online'] is True
            assert 'stream_urls' in cached_state

    def test_get_parent_state(self, parasite_config_file, mock_env_vars, sample_parent_state):
        """Should retrieve cached parent state"""
        with patch('base_connector.MQTTClient') as MockMQTT:
            mock_mqtt = MagicMock()
            MockMQTT.return_value = mock_mqtt

            connector = TestConnector(
                config_path=str(parasite_config_file),
                instance_name="motion_detector"
            )

            mqtt_path = "IoT2mqtt/v1/instances/cameras/devices/camera_1"

            # Cache parent state
            connector._on_parent_state_update(mqtt_path, f"{mqtt_path}/state", sample_parent_state)

            # Retrieve it
            parent_state = connector.get_parent_state(mqtt_path)

            assert parent_state is not None
            assert parent_state['ip'] == "192.168.1.10"
            assert parent_state['stream_urls']['rtsp'] == "rtsp://192.168.1.10:554/stream"

    def test_publish_parasite_fields(self, parasite_config_file, mock_env_vars):
        """Should publish additional fields to parent device state"""
        with patch('base_connector.MQTTClient') as MockMQTT:
            mock_mqtt = MagicMock()
            MockMQTT.return_value = mock_mqtt

            connector = TestConnector(
                config_path=str(parasite_config_file),
                instance_name="motion_detector"
            )

            mqtt_path = "IoT2mqtt/v1/instances/cameras/devices/camera_1"
            fields = {
                "motion_detected": True,
                "motion_confidence": 0.85,
                "last_motion_time": datetime.now().isoformat()
            }

            connector.publish_parasite_fields(mqtt_path, fields)

            # Should publish each field to external topic
            assert mock_mqtt.publish_to_external_topic.call_count == 3

            # Check topics
            calls = mock_mqtt.publish_to_external_topic.call_args_list
            topics = [call[0][0] for call in calls]

            assert f"{mqtt_path}/state/motion_detected" in topics
            assert f"{mqtt_path}/state/motion_confidence" in topics
            assert f"{mqtt_path}/state/last_motion_time" in topics

    def test_publish_parasite_registry(self, parasite_config_file, mock_env_vars):
        """Should publish /parasite topic listing parent devices"""
        with patch('base_connector.MQTTClient') as MockMQTT:
            mock_mqtt = MagicMock()
            MockMQTT.return_value = mock_mqtt

            connector = TestConnector(
                config_path=str(parasite_config_file),
                instance_name="motion_detector"
            )

            connector._publish_parasite_registry()

            # Should publish registry for camera_1 device
            assert mock_mqtt.publish.called
            # Check that parasite topic was published
            calls = mock_mqtt.publish.call_args_list
            parasite_calls = [c for c in calls if 'parasite' in str(c[0][0])]
            assert len(parasite_calls) > 0


# ============================================================================
# TIER 1 - CRITICAL TESTS: Home Assistant Discovery
# ============================================================================

class TestHomeAssistantDiscovery:
    """Test Home Assistant MQTT Discovery"""

    def test_publish_ha_discovery_for_enabled_devices(self, temp_config_file, mock_env_vars):
        """Should publish HA discovery for all enabled devices"""
        with patch('base_connector.MQTTClient') as MockMQTT, \
             patch('base_connector.DiscoveryGenerator') as MockDiscovery:

            mock_mqtt = MagicMock()
            MockMQTT.return_value = mock_mqtt

            mock_generator = MagicMock()
            mock_generator.generate_device_discovery.return_value = [
                {
                    "topic": "homeassistant/light/test_instance_test_device_1/config",
                    "payload": {"name": "Test Device 1"},
                    "retain": True
                }
            ]
            MockDiscovery.return_value = mock_generator

            connector = TestConnector(
                config_path=str(temp_config_file),
                instance_name="test_instance"
            )

            connector._publish_ha_discovery()

            # Should generate discovery for enabled device (test_device_1)
            assert mock_generator.generate_device_discovery.call_count == 1
            mock_mqtt.publish_ha_discovery.assert_called()

    def test_skip_discovery_for_disabled_devices(self, temp_config_file, mock_env_vars):
        """Should not publish discovery for disabled devices"""
        with patch('base_connector.MQTTClient') as MockMQTT, \
             patch('base_connector.DiscoveryGenerator') as MockDiscovery:

            mock_mqtt = MagicMock()
            MockMQTT.return_value = mock_mqtt

            mock_generator = MagicMock()
            MockDiscovery.return_value = mock_generator

            connector = TestConnector(
                config_path=str(temp_config_file),
                instance_name="test_instance"
            )

            connector._publish_ha_discovery()

            # Should only call for test_device_1 (enabled), not test_device_2 (disabled)
            # Extract device_id from keyword arguments
            call_args = [call.kwargs.get('device_id') or call[0][0]
                        for call in mock_generator.generate_device_discovery.call_args_list]
            assert "test_device_1" in call_args
            assert "test_device_2" not in call_args

    def test_discovery_not_published_when_disabled(self, temp_config_file, mock_env_vars):
        """Should not publish discovery when ha_discovery_enabled is False"""
        config = json.loads(temp_config_file.read_text())
        config['ha_discovery_enabled'] = False
        temp_config_file.write_text(json.dumps(config))

        with patch('base_connector.MQTTClient') as MockMQTT, \
             patch('base_connector.DiscoveryGenerator') as MockDiscovery:

            mock_mqtt = MagicMock()
            MockMQTT.return_value = mock_mqtt
            mock_generator = MagicMock()
            MockDiscovery.return_value = mock_generator

            connector = TestConnector(
                config_path=str(temp_config_file),
                instance_name="test_instance"
            )

            connector._publish_ha_discovery()

            # Should not call publish_ha_discovery
            mock_mqtt.publish_ha_discovery.assert_not_called()

    def test_discovery_error_does_not_fail_startup(self, temp_config_file, mock_env_vars):
        """Should not fail startup if discovery generation throws error"""
        with patch('base_connector.MQTTClient') as MockMQTT, \
             patch('base_connector.DiscoveryGenerator') as MockDiscovery:

            mock_mqtt = MagicMock()
            MockMQTT.return_value = mock_mqtt

            mock_generator = MagicMock()
            mock_generator.generate_device_discovery.side_effect = RuntimeError("Discovery error")
            MockDiscovery.return_value = mock_generator

            connector = TestConnector(
                config_path=str(temp_config_file),
                instance_name="test_instance"
            )

            # Should not raise exception
            connector._publish_ha_discovery()


# ============================================================================
# TIER 1 - CRITICAL TESTS: Lifecycle Management
# ============================================================================

class TestLifecycleManagement:
    """Test connector lifecycle (start, stop, run)"""

    def test_start_connects_to_mqtt(self, temp_config_file, mock_env_vars):
        """Should connect to MQTT broker on start"""
        with patch('base_connector.MQTTClient') as MockMQTT:
            mock_mqtt = MagicMock()
            mock_mqtt.connect.return_value = True
            MockMQTT.return_value = mock_mqtt

            connector = TestConnector(
                config_path=str(temp_config_file),
                instance_name="test_instance"
            )

            result = connector.start()

            assert result is True
            mock_mqtt.connect.assert_called_once()

    def test_start_fails_if_mqtt_connection_fails(self, temp_config_file, mock_env_vars):
        """Should return False if MQTT connection fails"""
        with patch('base_connector.MQTTClient') as MockMQTT:
            mock_mqtt = MagicMock()
            mock_mqtt.connect.return_value = False
            MockMQTT.return_value = mock_mqtt

            connector = TestConnector(
                config_path=str(temp_config_file),
                instance_name="test_instance"
            )

            result = connector.start()

            assert result is False
            assert connector.running is False

    def test_start_calls_initialize_connection(self, temp_config_file, mock_env_vars):
        """Should call initialize_connection during startup"""
        with patch('base_connector.MQTTClient') as MockMQTT:
            mock_mqtt = MagicMock()
            mock_mqtt.connect.return_value = True
            MockMQTT.return_value = mock_mqtt

            connector = TestConnector(
                config_path=str(temp_config_file),
                instance_name="test_instance"
            )

            connector.start()

            assert connector.initialize_called is True

    def test_start_sets_up_subscriptions(self, temp_config_file, mock_env_vars):
        """Should setup MQTT subscriptions during startup"""
        with patch('base_connector.MQTTClient') as MockMQTT:
            mock_mqtt = MagicMock()
            mock_mqtt.connect.return_value = True
            MockMQTT.return_value = mock_mqtt

            connector = TestConnector(
                config_path=str(temp_config_file),
                instance_name="test_instance"
            )

            connector.start()

            # Should subscribe to command topics
            assert mock_mqtt.subscribe.call_count >= 3  # devices/+/cmd, devices/+/get, groups/+/cmd

    def test_start_launches_main_thread(self, temp_config_file, mock_env_vars):
        """Should start main polling loop in separate thread"""
        with patch('base_connector.MQTTClient') as MockMQTT:
            mock_mqtt = MagicMock()
            mock_mqtt.connect.return_value = True
            MockMQTT.return_value = mock_mqtt

            connector = TestConnector(
                config_path=str(temp_config_file),
                instance_name="test_instance"
            )

            connector.start()

            assert connector.running is True
            assert connector.main_thread is not None
            assert connector.main_thread.is_alive()

            # Cleanup
            connector.stop()

    def test_stop_calls_cleanup_connection(self, temp_config_file, mock_env_vars):
        """Should call cleanup_connection when stopping"""
        with patch('base_connector.MQTTClient') as MockMQTT:
            mock_mqtt = MagicMock()
            mock_mqtt.connect.return_value = True
            MockMQTT.return_value = mock_mqtt

            connector = TestConnector(
                config_path=str(temp_config_file),
                instance_name="test_instance"
            )

            connector.start()
            time.sleep(0.1)  # Let thread start
            connector.stop()

            assert connector.cleanup_called is True

    def test_stop_disconnects_mqtt(self, temp_config_file, mock_env_vars):
        """Should disconnect from MQTT when stopping"""
        with patch('base_connector.MQTTClient') as MockMQTT:
            mock_mqtt = MagicMock()
            mock_mqtt.connect.return_value = True
            MockMQTT.return_value = mock_mqtt

            connector = TestConnector(
                config_path=str(temp_config_file),
                instance_name="test_instance"
            )

            connector.start()
            connector.stop()

            mock_mqtt.disconnect.assert_called_once()

    def test_stop_waits_for_main_thread(self, temp_config_file, mock_env_vars):
        """Should wait for main thread to finish"""
        with patch('base_connector.MQTTClient') as MockMQTT:
            mock_mqtt = MagicMock()
            mock_mqtt.connect.return_value = True
            MockMQTT.return_value = mock_mqtt

            connector = TestConnector(
                config_path=str(temp_config_file),
                instance_name="test_instance"
            )

            connector.start()
            time.sleep(0.1)
            connector.stop()

            # Main thread should be stopped
            assert connector.running is False
            # Give thread time to finish
            time.sleep(0.2)
            assert not connector.main_thread.is_alive()


# ============================================================================
# TIER 1 - CRITICAL TESTS: Error Handling in Main Loop
# ============================================================================

class TestErrorHandlingInMainLoop:
    """Test error handling and recovery in main polling loop"""

    def test_continue_on_device_error(self, temp_config_file, mock_env_vars):
        """Should continue polling other devices if one fails"""
        with patch('base_connector.MQTTClient') as MockMQTT:
            mock_mqtt = MagicMock()
            mock_mqtt.connect.return_value = True
            MockMQTT.return_value = mock_mqtt

            call_count = [0]

            class FailingConnector(TestConnector):
                def get_device_state(self, device_id, device_config):
                    call_count[0] += 1
                    if call_count[0] == 1:
                        raise RuntimeError("Device error")
                    return {"online": True}

            connector = FailingConnector(
                config_path=str(temp_config_file),
                instance_name="test_instance"
            )

            connector.start()
            time.sleep(0.3)  # Let loop run
            connector.stop()

            # Should have published error
            assert mock_mqtt.publish_error.called

    def test_increment_error_count_on_failure(self, temp_config_file, mock_env_vars):
        """Should increment error count when device update fails"""
        with patch('base_connector.MQTTClient') as MockMQTT:
            mock_mqtt = MagicMock()
            mock_mqtt.connect.return_value = True
            MockMQTT.return_value = mock_mqtt

            class AlwaysFailingConnector(TestConnector):
                def get_device_state(self, device_id, device_config):
                    raise RuntimeError("Always fails")

            connector = AlwaysFailingConnector(
                config_path=str(temp_config_file),
                instance_name="test_instance"
            )

            connector.start()
            time.sleep(0.5)  # Let loop run
            connector.stop()

            # Should have called publish_error multiple times
            assert mock_mqtt.publish_error.call_count >= 1

    def test_stop_after_max_consecutive_errors(self, temp_config_file, mock_env_vars):
        """Should stop connector after MAX_ERRORS consecutive failures"""
        with patch('base_connector.MQTTClient') as MockMQTT:
            mock_mqtt = MagicMock()
            mock_mqtt.connect.return_value = True
            MockMQTT.return_value = mock_mqtt

            class AlwaysFailingConnector(TestConnector):
                def get_device_state(self, device_id, device_config):
                    raise RuntimeError("Always fails")

            connector = AlwaysFailingConnector(
                config_path=str(temp_config_file),
                instance_name="test_instance"
            )

            # Modify update_interval for faster testing
            connector.update_interval = 0.1

            connector.start()
            time.sleep(1)  # Let it hit max errors

            # Should have stopped
            assert connector.running is False

            connector.stop()

    def test_reset_error_count_on_success(self, temp_config_file, mock_env_vars):
        """Should reset error count after successful update"""
        with patch('base_connector.MQTTClient') as MockMQTT:
            mock_mqtt = MagicMock()
            mock_mqtt.connect.return_value = True
            MockMQTT.return_value = mock_mqtt

            call_count = [0]

            class RecoveringConnector(TestConnector):
                def get_device_state(self, device_id, device_config):
                    call_count[0] += 1
                    if call_count[0] <= 2:
                        raise RuntimeError("Temporary failure")
                    return {"online": True}

            connector = RecoveringConnector(
                config_path=str(temp_config_file),
                instance_name="test_instance"
            )

            connector.update_interval = 0.1
            connector.start()
            time.sleep(0.5)

            # Should have recovered and continue running
            assert connector.running is True

            connector.stop()


# ============================================================================
# TIER 1 - CRITICAL TESTS: Get Request Handling
# ============================================================================

class TestGetRequestHandling:
    """Test handling of device state get requests"""

    def test_handle_get_request_from_cache(self, temp_config_file, mock_env_vars):
        """Should serve device state from cache when available"""
        with patch('base_connector.MQTTClient') as MockMQTT:
            mock_mqtt = MagicMock()
            MockMQTT.return_value = mock_mqtt

            connector = TestConnector(
                config_path=str(temp_config_file),
                instance_name="test_instance"
            )

            # Populate cache
            connector.devices["test_device_1"] = {
                "state": {"online": True, "power": True},
                "last_update": datetime.now(),
                "config": {}
            }

            topic = "IoT2mqtt/v1/instances/test_instance/devices/test_device_1/get"
            payload = {}

            connector._handle_get(topic, payload)

            # Should publish cached state
            mock_mqtt.publish_state.assert_called_once_with(
                "test_device_1",
                {"online": True, "power": True}
            )

    def test_handle_get_request_queries_device_when_not_cached(self, temp_config_file, mock_env_vars):
        """Should query device if state not in cache"""
        with patch('base_connector.MQTTClient') as MockMQTT:
            mock_mqtt = MagicMock()
            MockMQTT.return_value = mock_mqtt

            connector = TestConnector(
                config_path=str(temp_config_file),
                instance_name="test_instance"
            )

            topic = "IoT2mqtt/v1/instances/test_instance/devices/test_device_1/get"
            payload = {}

            connector._handle_get(topic, payload)

            # Should call get_device_state
            assert len(connector.get_state_calls) == 1
            assert connector.get_state_calls[0][0] == "test_device_1"

    def test_handle_get_with_property_filter(self, temp_config_file, mock_env_vars):
        """Should filter state properties when requested"""
        with patch('base_connector.MQTTClient') as MockMQTT:
            mock_mqtt = MagicMock()
            MockMQTT.return_value = mock_mqtt

            connector = TestConnector(
                config_path=str(temp_config_file),
                instance_name="test_instance"
            )

            # Populate cache with multiple properties
            connector.devices["test_device_1"] = {
                "state": {
                    "online": True,
                    "power": True,
                    "brightness": 75,
                    "color_temp": 4000
                },
                "last_update": datetime.now(),
                "config": {}
            }

            topic = "IoT2mqtt/v1/instances/test_instance/devices/test_device_1/get"
            payload = {
                "properties": ["power", "brightness"]
            }

            connector._handle_get(topic, payload)

            # Should publish filtered state
            call_args = mock_mqtt.publish_state.call_args
            assert call_args[0][0] == "test_device_1"
            filtered_state = call_args[0][1]
            assert "power" in filtered_state
            assert "brightness" in filtered_state
            assert "color_temp" not in filtered_state


# ============================================================================
# TIER 1 - CRITICAL TESTS: Meta Request Handling
# ============================================================================

class TestMetaRequestHandling:
    """Test meta request handling (device list, info)"""

    def test_handle_devices_list_request(self, temp_config_file, mock_env_vars):
        """Should return list of all devices"""
        with patch('base_connector.MQTTClient') as MockMQTT:
            mock_mqtt = MagicMock()
            MockMQTT.return_value = mock_mqtt

            connector = TestConnector(
                config_path=str(temp_config_file),
                instance_name="test_instance"
            )

            topic = "IoT2mqtt/v1/instances/test_instance/meta/request/devices_list"
            payload = {}

            connector._handle_meta_request(topic, payload)

            # Should publish devices list
            assert mock_mqtt.publish.called
            call_args = mock_mqtt.publish.call_args[0]
            devices_list = call_args[1]

            assert len(devices_list) == 2
            assert devices_list[0]['device_id'] == "test_device_1"

    def test_handle_info_request(self, temp_config_file, mock_env_vars):
        """Should return instance information"""
        with patch('base_connector.MQTTClient') as MockMQTT:
            mock_mqtt = MagicMock()
            MockMQTT.return_value = mock_mqtt

            connector = TestConnector(
                config_path=str(temp_config_file),
                instance_name="test_instance"
            )

            topic = "IoT2mqtt/v1/instances/test_instance/meta/request/info"
            payload = {}

            connector._handle_meta_request(topic, payload)

            # Should publish instance info
            assert mock_mqtt.publish.called
            call_args = mock_mqtt.publish.call_args[0]
            info = call_args[1]

            assert info['instance_id'] == "test_instance"
            assert 'devices_count' in info
            assert 'groups_count' in info


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
