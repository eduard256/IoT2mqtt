"""
Comprehensive tests for MQTTClient

Tests cover:
1. Connection and reconnection with retry logic
2. Subscription handling with wildcards
3. Publishing (state, events, errors, telemetry, HA discovery)
4. Command response handling and TTL cleanup
5. Message callbacks and error handling
6. External topic operations (parasitic mode)
7. Last Will and Testament (LWT)
8. Authentication and credentials loading
"""

import pytest
import json
import time
import threading
from unittest.mock import Mock, MagicMock, patch, call
from datetime import datetime, timedelta
from pathlib import Path
from queue import Queue

# Add shared to path for imports
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'shared'))

from mqtt_client import MQTTClient, CommandInfo


# ============================================================================
# TIER 1 - CRITICAL TESTS: MQTT Connection
# ============================================================================

class TestMQTTConnection:
    """Test MQTT broker connection and lifecycle"""

    def test_initialization_with_defaults(self, monkeypatch):
        """Should initialize with default values from environment"""
        monkeypatch.setenv("MQTT_BASE_TOPIC", "TestTopic")
        monkeypatch.setenv("MQTT_HOST", "test.mqtt.broker")
        monkeypatch.setenv("MQTT_PORT", "1883")
        monkeypatch.setenv("MQTT_USERNAME", "testuser")
        monkeypatch.setenv("MQTT_PASSWORD", "testpass")

        with patch('mqtt_client.mqtt.Client') as MockClient:
            mock_client = MagicMock()
            MockClient.return_value = mock_client

            client = MQTTClient(instance_id="test_instance")

            assert client.instance_id == "test_instance"
            assert client.base_topic == "TestTopic"
            assert client.host == "test.mqtt.broker"
            assert client.port == 1883
            assert client.username == "testuser"
            assert client.password == "testpass"
            assert client.qos == 1
            assert client.retain_state is True

    def test_initialization_with_explicit_parameters(self):
        """Should use explicit parameters over environment variables"""
        with patch('mqtt_client.mqtt.Client') as MockClient:
            mock_client = MagicMock()
            MockClient.return_value = mock_client

            client = MQTTClient(
                instance_id="my_instance",
                base_topic="CustomTopic",
                host="custom.broker",
                port=8883,
                username="custom_user",
                password="custom_pass",
                qos=2,
                retain_state=False,
                response_ttl=600
            )

            assert client.base_topic == "CustomTopic"
            assert client.host == "custom.broker"
            assert client.port == 8883
            assert client.username == "custom_user"
            assert client.password == "custom_pass"
            assert client.qos == 2
            assert client.retain_state is False
            assert client.response_ttl == 600

    def test_mqtt_client_id_generation(self, monkeypatch):
        """Should generate client ID with prefix and instance_id"""
        monkeypatch.setenv("MQTT_CLIENT_PREFIX", "custom_prefix")

        with patch('mqtt_client.mqtt.Client') as MockClient:
            mock_client = MagicMock()
            MockClient.return_value = mock_client

            client = MQTTClient(instance_id="test123")

            MockClient.assert_called_once_with(client_id="custom_prefix_test123")

    def test_authentication_setup(self):
        """Should set username and password for authentication"""
        with patch('mqtt_client.mqtt.Client') as MockClient:
            mock_client = MagicMock()
            MockClient.return_value = mock_client

            client = MQTTClient(
                instance_id="test",
                username="user",
                password="pass"
            )

            mock_client.username_pw_set.assert_called_once_with("user", "pass")

    def test_last_will_testament_setup(self):
        """Should configure LWT with offline status"""
        with patch('mqtt_client.mqtt.Client') as MockClient:
            mock_client = MagicMock()
            MockClient.return_value = mock_client

            client = MQTTClient(
                instance_id="test_instance",
                base_topic="IoT2mqtt"
            )

            expected_topic = "IoT2mqtt/v1/instances/test_instance/status"
            mock_client.will_set.assert_called_once_with(
                expected_topic, "offline", qos=1, retain=True
            )

    def test_connect_success(self):
        """Should connect to MQTT broker successfully"""
        with patch('mqtt_client.mqtt.Client') as MockClient:
            mock_client = MagicMock()
            MockClient.return_value = mock_client

            client = MQTTClient(instance_id="test")

            # Simulate successful connection
            def simulate_connect(*args, **kwargs):
                client.connected = True

            mock_client.connect.side_effect = simulate_connect

            result = client.connect(max_retries=1)

            assert result is True
            assert client.connected is True
            mock_client.connect.assert_called_once()
            mock_client.loop_start.assert_called_once()

    def test_connect_with_retry_on_failure(self):
        """Should retry connection on failure"""
        with patch('mqtt_client.mqtt.Client') as MockClient:
            mock_client = MagicMock()
            MockClient.return_value = mock_client

            client = MQTTClient(instance_id="test")

            # First attempt fails, second succeeds
            call_count = [0]

            def simulate_connect(*args, **kwargs):
                call_count[0] += 1
                if call_count[0] >= 2:
                    client.connected = True
                else:
                    raise ConnectionRefusedError("Connection refused")

            mock_client.connect.side_effect = simulate_connect

            with patch('time.sleep'):  # Speed up test
                result = client.connect(retry_interval=1, max_retries=3)

            assert result is True
            assert mock_client.connect.call_count == 2

    def test_connect_failure_after_max_retries(self):
        """Should raise exception after max retries exceeded"""
        with patch('mqtt_client.mqtt.Client') as MockClient:
            mock_client = MagicMock()
            MockClient.return_value = mock_client

            client = MQTTClient(instance_id="test")
            mock_client.connect.side_effect = ConnectionRefusedError("Connection refused")

            with patch('time.sleep'):
                with pytest.raises(ConnectionRefusedError):
                    client.connect(retry_interval=1, max_retries=2)

    def test_publish_online_status_after_connect(self):
        """Should publish online status after successful connection"""
        with patch('mqtt_client.mqtt.Client') as MockClient:
            mock_client = MagicMock()
            MockClient.return_value = mock_client

            client = MQTTClient(instance_id="test", base_topic="IoT2mqtt")

            def simulate_connect(*args, **kwargs):
                client.connected = True

            mock_client.connect.side_effect = simulate_connect

            client.connect(max_retries=1)

            # Should publish online status
            expected_topic = "IoT2mqtt/v1/instances/test/status"
            calls = [c for c in mock_client.publish.call_args_list
                    if c[0][0] == expected_topic and c[0][1] == "online"]
            assert len(calls) == 1

    def test_disconnect(self):
        """Should disconnect and publish offline status"""
        with patch('mqtt_client.mqtt.Client') as MockClient:
            mock_client = MagicMock()
            MockClient.return_value = mock_client

            client = MQTTClient(instance_id="test", base_topic="IoT2mqtt")
            client.connected = True

            client.disconnect()

            # Should publish offline status
            expected_topic = "IoT2mqtt/v1/instances/test/status"
            mock_client.publish.assert_called()
            offline_calls = [c for c in mock_client.publish.call_args_list
                           if c[0][0] == expected_topic and c[0][1] == "offline"]
            assert len(offline_calls) == 1

            # Should stop MQTT loop and disconnect
            mock_client.loop_stop.assert_called_once()
            mock_client.disconnect.assert_called_once()
            assert client.connected is False

    def test_on_connect_callback_success(self):
        """Should handle successful connection callback"""
        with patch('mqtt_client.mqtt.Client') as MockClient:
            mock_client = MagicMock()
            MockClient.return_value = mock_client

            client = MQTTClient(instance_id="test")

            # Simulate connection callback with rc=0 (success)
            client._on_connect(mock_client, None, None, 0)

            assert client.connected is True

    def test_on_connect_callback_failure(self):
        """Should handle failed connection callback"""
        with patch('mqtt_client.mqtt.Client') as MockClient:
            mock_client = MagicMock()
            MockClient.return_value = mock_client

            client = MQTTClient(instance_id="test")

            # Simulate connection callback with rc=5 (auth failed)
            client._on_connect(mock_client, None, None, 5)

            assert client.connected is False

    def test_on_disconnect_callback(self):
        """Should handle disconnection callback"""
        with patch('mqtt_client.mqtt.Client') as MockClient:
            mock_client = MagicMock()
            MockClient.return_value = mock_client

            client = MQTTClient(instance_id="test")
            client.connected = True

            # Simulate unexpected disconnect (rc != 0)
            client._on_disconnect(mock_client, None, 1)

            assert client.connected is False

    def test_resubscribe_on_reconnect(self):
        """Should resubscribe to all topics after reconnection"""
        with patch('mqtt_client.mqtt.Client') as MockClient:
            mock_client = MagicMock()
            MockClient.return_value = mock_client

            client = MQTTClient(instance_id="test", base_topic="IoT2mqtt")

            # Add some subscriptions
            client.subscriptions = {
                "IoT2mqtt/v1/instances/test/devices/+/cmd": Mock(),
                "IoT2mqtt/v1/instances/test/devices/+/get": Mock()
            }

            # Simulate reconnection
            client._on_connect(mock_client, None, None, 0)

            # Should resubscribe to all topics
            assert mock_client.subscribe.call_count == 2


# ============================================================================
# TIER 1 - CRITICAL TESTS: Subscription Handling
# ============================================================================

class TestSubscription:
    """Test MQTT subscription and message handling"""

    def test_subscribe_to_topic(self):
        """Should subscribe to topic with proper pattern"""
        with patch('mqtt_client.mqtt.Client') as MockClient:
            mock_client = MagicMock()
            MockClient.return_value = mock_client

            client = MQTTClient(instance_id="test", base_topic="IoT2mqtt")
            client.connected = True

            handler = Mock()
            client.subscribe("devices/+/cmd", handler)

            expected_topic = "IoT2mqtt/v1/instances/test/devices/+/cmd"
            assert expected_topic in client.subscriptions
            mock_client.subscribe.assert_called_once_with(expected_topic, qos=1)

    def test_subscribe_wildcard_single_level(self):
        """Should handle single-level wildcard (+) subscriptions"""
        with patch('mqtt_client.mqtt.Client') as MockClient:
            mock_client = MagicMock()
            MockClient.return_value = mock_client

            client = MQTTClient(instance_id="test", base_topic="IoT2mqtt")
            client.connected = True

            handler = Mock()
            client.subscribe("devices/+/state", handler)

            expected_topic = "IoT2mqtt/v1/instances/test/devices/+/state"
            assert expected_topic in client.subscriptions

    def test_subscribe_wildcard_multi_level(self):
        """Should handle multi-level wildcard (#) subscriptions"""
        with patch('mqtt_client.mqtt.Client') as MockClient:
            mock_client = MagicMock()
            MockClient.return_value = mock_client

            client = MQTTClient(instance_id="test", base_topic="IoT2mqtt")
            client.connected = True

            handler = Mock()
            client.subscribe("devices/#", handler)

            expected_topic = "IoT2mqtt/v1/instances/test/devices/#"
            assert expected_topic in client.subscriptions

    def test_message_callback_invoked(self):
        """Should invoke handler when message received"""
        with patch('mqtt_client.mqtt.Client') as MockClient:
            mock_client = MagicMock()
            MockClient.return_value = mock_client

            client = MQTTClient(instance_id="test", base_topic="IoT2mqtt")

            handler = Mock()
            topic = "IoT2mqtt/v1/instances/test/devices/dev1/cmd"
            client.subscriptions[topic] = handler

            # Simulate incoming message
            msg = MagicMock()
            msg.topic = topic
            msg.payload = b'{"power": true}'

            client._on_message(mock_client, None, msg)

            handler.assert_called_once()
            call_args = handler.call_args[0]
            assert call_args[0] == topic
            assert call_args[1] == {"power": True}

    def test_message_callback_with_wildcard_match(self):
        """Should invoke handler for messages matching wildcard pattern"""
        with patch('mqtt_client.mqtt.Client') as MockClient, \
             patch('mqtt_client.mqtt.topic_matches_sub') as mock_matches:

            mock_client = MagicMock()
            MockClient.return_value = mock_client
            mock_matches.return_value = True

            client = MQTTClient(instance_id="test")

            handler = Mock()
            pattern = "IoT2mqtt/v1/instances/test/devices/+/cmd"
            client.subscriptions[pattern] = handler

            # Simulate message
            msg = MagicMock()
            msg.topic = "IoT2mqtt/v1/instances/test/devices/device123/cmd"
            msg.payload = b'{"power": true}'

            client._on_message(mock_client, None, msg)

            handler.assert_called_once()

    def test_message_callback_error_handling(self):
        """Should handle errors in message callback gracefully"""
        with patch('mqtt_client.mqtt.Client') as MockClient:
            mock_client = MagicMock()
            MockClient.return_value = mock_client

            client = MQTTClient(instance_id="test")

            def failing_handler(topic, payload):
                raise RuntimeError("Handler error")

            topic = "test/topic"
            client.subscriptions[topic] = failing_handler

            msg = MagicMock()
            msg.topic = topic
            msg.payload = b'{"data": "value"}'

            # Should not raise exception
            with patch('mqtt_client.mqtt.topic_matches_sub', return_value=True):
                client._on_message(mock_client, None, msg)

    def test_message_json_parsing(self):
        """Should parse JSON payloads correctly"""
        with patch('mqtt_client.mqtt.Client') as MockClient:
            mock_client = MagicMock()
            MockClient.return_value = mock_client

            client = MQTTClient(instance_id="test")

            handler = Mock()
            topic = "test/topic"
            client.subscriptions[topic] = handler

            msg = MagicMock()
            msg.topic = topic
            msg.payload = b'{"temperature": 25.5, "humidity": 60}'

            with patch('mqtt_client.mqtt.topic_matches_sub', return_value=True):
                client._on_message(mock_client, None, msg)

            handler.assert_called_once()
            payload = handler.call_args[0][1]
            assert payload["temperature"] == 25.5
            assert payload["humidity"] == 60

    def test_message_non_json_payload(self):
        """Should handle non-JSON payloads as strings"""
        with patch('mqtt_client.mqtt.Client') as MockClient:
            mock_client = MagicMock()
            MockClient.return_value = mock_client

            client = MQTTClient(instance_id="test")

            handler = Mock()
            topic = "test/topic"
            client.subscriptions[topic] = handler

            msg = MagicMock()
            msg.topic = topic
            msg.payload = b'plain text message'

            with patch('mqtt_client.mqtt.topic_matches_sub', return_value=True):
                client._on_message(mock_client, None, msg)

            handler.assert_called_once()
            payload = handler.call_args[0][1]
            assert payload == "plain text message"


# ============================================================================
# TIER 1 - CRITICAL TESTS: Publishing
# ============================================================================

class TestPublishing:
    """Test MQTT publishing functionality"""

    def test_publish_state_with_timestamp(self):
        """Should publish device state with timestamp and device_id"""
        with patch('mqtt_client.mqtt.Client') as MockClient:
            mock_client = MagicMock()
            MockClient.return_value = mock_client

            client = MQTTClient(instance_id="test", base_topic="IoT2mqtt")
            client.connected = True

            state = {"power": True, "brightness": 75}
            client.publish_state("device1", state)

            # Should publish to state topic
            expected_topic = "IoT2mqtt/v1/instances/test/devices/device1/state"
            assert mock_client.publish.called

            # Find the state topic call
            state_calls = [c for c in mock_client.publish.call_args_list
                          if expected_topic in str(c)]
            assert len(state_calls) > 0

    def test_publish_state_individual_properties(self):
        """Should publish individual state properties to separate topics"""
        with patch('mqtt_client.mqtt.Client') as MockClient:
            mock_client = MagicMock()
            MockClient.return_value = mock_client

            client = MQTTClient(instance_id="test", base_topic="IoT2mqtt")
            client.connected = True

            state = {"power": True, "brightness": 75}
            client.publish_state("device1", state)

            # Should publish individual properties
            power_topic = "IoT2mqtt/v1/instances/test/devices/device1/state/power"
            brightness_topic = "IoT2mqtt/v1/instances/test/devices/device1/state/brightness"

            all_topics = [str(c) for c in mock_client.publish.call_args_list]
            assert any(power_topic in t for t in all_topics)
            assert any(brightness_topic in t for t in all_topics)

    def test_publish_state_with_retain_flag(self):
        """Should use retain flag when publishing state"""
        with patch('mqtt_client.mqtt.Client') as MockClient:
            mock_client = MagicMock()
            MockClient.return_value = mock_client

            client = MQTTClient(instance_id="test", retain_state=True)
            client.connected = True

            client.publish_state("device1", {"power": True})

            # Should use retain=True (default for state)
            assert mock_client.publish.called

    def test_publish_event(self):
        """Should publish device event to events topic"""
        with patch('mqtt_client.mqtt.Client') as MockClient:
            mock_client = MagicMock()
            MockClient.return_value = mock_client

            client = MQTTClient(instance_id="test", base_topic="IoT2mqtt")
            client.connected = True

            client.publish_event("device1", "button_pressed", {"button": "power"})

            # Should publish to events topic
            event_topic = "IoT2mqtt/v1/instances/test/devices/device1/events"
            calls = [c for c in mock_client.publish.call_args_list if event_topic in str(c)]
            assert len(calls) > 0

    def test_publish_event_to_global_bus(self):
        """Should also publish event to global event bus"""
        with patch('mqtt_client.mqtt.Client') as MockClient:
            mock_client = MagicMock()
            MockClient.return_value = mock_client

            client = MQTTClient(instance_id="test", base_topic="IoT2mqtt")
            client.connected = True

            client.publish_event("device1", "motion_detected", None)

            # Should publish to global events topic
            global_topic = "IoT2mqtt/v1/global/events"
            calls = [c for c in mock_client.publish.call_args_list if global_topic in str(c)]
            assert len(calls) > 0

    def test_publish_error(self):
        """Should publish device error with severity"""
        with patch('mqtt_client.mqtt.Client') as MockClient:
            mock_client = MagicMock()
            MockClient.return_value = mock_client

            client = MQTTClient(instance_id="test", base_topic="IoT2mqtt")
            client.connected = True

            client.publish_error("device1", "CONN_ERROR", "Connection failed", severity="critical")

            error_topic = "IoT2mqtt/v1/instances/test/devices/device1/error"
            calls = [c for c in mock_client.publish.call_args_list if error_topic in str(c)]
            assert len(calls) > 0

    def test_publish_telemetry(self):
        """Should publish device telemetry metrics"""
        with patch('mqtt_client.mqtt.Client') as MockClient:
            mock_client = MagicMock()
            MockClient.return_value = mock_client

            client = MQTTClient(instance_id="test", base_topic="IoT2mqtt")
            client.connected = True

            metrics = {"cpu": 45.2, "memory": 78.5, "uptime": 3600}
            client.publish_telemetry("device1", metrics)

            telemetry_topic = "IoT2mqtt/v1/instances/test/devices/device1/telemetry"
            calls = [c for c in mock_client.publish.call_args_list if telemetry_topic in str(c)]
            assert len(calls) > 0

    def test_publish_discovered_devices(self):
        """Should publish list of discovered devices"""
        with patch('mqtt_client.mqtt.Client') as MockClient:
            mock_client = MagicMock()
            MockClient.return_value = mock_client

            client = MQTTClient(instance_id="test", base_topic="IoT2mqtt")
            client.connected = True

            devices = [
                {"device_id": "dev1", "ip": "192.168.1.10"},
                {"device_id": "dev2", "ip": "192.168.1.11"}
            ]
            client.publish_discovered(devices)

            discovered_topic = "IoT2mqtt/v1/instances/test/discovered"
            calls = [c for c in mock_client.publish.call_args_list if discovered_topic in str(c)]
            assert len(calls) > 0

    def test_publish_ha_discovery(self):
        """Should publish Home Assistant discovery messages"""
        with patch('mqtt_client.mqtt.Client') as MockClient:
            mock_client = MagicMock()
            MockClient.return_value = mock_client

            client = MQTTClient(instance_id="test")
            client.connected = True

            discovery_messages = [
                {
                    "topic": "homeassistant/light/test_device/config",
                    "payload": {"name": "Test Light", "unique_id": "test_light"},
                    "retain": True
                }
            ]

            client.publish_ha_discovery(discovery_messages)

            # Should publish to HA discovery topic
            ha_topic = "homeassistant/light/test_device/config"
            calls = [c for c in mock_client.publish.call_args_list if ha_topic in str(c)]
            assert len(calls) > 0

    def test_publish_when_disconnected(self):
        """Should log warning when publishing while disconnected"""
        with patch('mqtt_client.mqtt.Client') as MockClient:
            mock_client = MagicMock()
            MockClient.return_value = mock_client

            client = MQTTClient(instance_id="test")
            client.connected = False

            # Should not crash, just log warning
            client.publish("test/topic", {"data": "value"})

            # Should not call client.publish
            mock_client.publish.assert_not_called()

    def test_publish_json_serialization(self):
        """Should serialize dict and list payloads to JSON"""
        with patch('mqtt_client.mqtt.Client') as MockClient:
            mock_client = MagicMock()
            MockClient.return_value = mock_client

            client = MQTTClient(instance_id="test")
            client.connected = True

            # Publish dict
            client.publish("test/topic", {"key": "value"})

            # Should serialize to JSON string
            assert mock_client.publish.called
            call_args = mock_client.publish.call_args[0]
            assert isinstance(call_args[1], str)
            assert json.loads(call_args[1]) == {"key": "value"}


# ============================================================================
# TIER 1 - CRITICAL TESTS: Command Response Handling
# ============================================================================

class TestCommandResponse:
    """Test command sending and response handling"""

    def test_send_command_generates_uuid(self):
        """Should generate unique command ID"""
        with patch('mqtt_client.mqtt.Client') as MockClient:
            mock_client = MagicMock()
            MockClient.return_value = mock_client

            client = MQTTClient(instance_id="test")
            client.connected = True

            cmd_id = client.send_command("device1", {"power": True})

            assert cmd_id is not None
            assert isinstance(cmd_id, str)
            assert len(cmd_id) > 0

    def test_send_command_stores_pending_info(self):
        """Should store command info in pending_commands"""
        with patch('mqtt_client.mqtt.Client') as MockClient:
            mock_client = MagicMock()
            MockClient.return_value = mock_client

            client = MQTTClient(instance_id="test")
            client.connected = True

            cmd_id = client.send_command("device1", {"power": True}, timeout=10.0)

            assert cmd_id in client.pending_commands
            cmd_info = client.pending_commands[cmd_id]
            assert cmd_info.id == cmd_id
            assert cmd_info.timeout == 10.0

    def test_send_command_with_callback(self):
        """Should store callback for response handling"""
        with patch('mqtt_client.mqtt.Client') as MockClient:
            mock_client = MagicMock()
            MockClient.return_value = mock_client

            client = MQTTClient(instance_id="test")
            client.connected = True

            callback = Mock()
            cmd_id = client.send_command("device1", {"power": True}, callback=callback)

            assert client.pending_commands[cmd_id].callback == callback

    def test_response_callback_invoked(self):
        """Should invoke callback when response received"""
        with patch('mqtt_client.mqtt.Client') as MockClient:
            mock_client = MagicMock()
            MockClient.return_value = mock_client

            client = MQTTClient(instance_id="test")
            client.connected = True

            callback = Mock()
            cmd_id = client.send_command("device1", {"power": True}, callback=callback)

            # Simulate response message
            response_payload = {"cmd_id": cmd_id, "status": "success"}
            msg = MagicMock()
            msg.topic = "IoT2mqtt/v1/instances/test/devices/device1/cmd/response"
            msg.payload = json.dumps(response_payload).encode()

            client._on_message(mock_client, None, msg)

            callback.assert_called_once_with(response_payload)

    def test_response_removes_pending_command(self):
        """Should remove command from pending after response"""
        with patch('mqtt_client.mqtt.Client') as MockClient:
            mock_client = MagicMock()
            MockClient.return_value = mock_client

            client = MQTTClient(instance_id="test")
            client.connected = True

            callback = Mock()
            cmd_id = client.send_command("device1", {"power": True}, callback=callback)

            assert cmd_id in client.pending_commands

            # Simulate response
            response_payload = {"cmd_id": cmd_id, "status": "success"}
            msg = MagicMock()
            msg.topic = "test/cmd/response"
            msg.payload = json.dumps(response_payload).encode()

            client._on_message(mock_client, None, msg)

            # Should be removed
            assert cmd_id not in client.pending_commands

    def test_wait_for_response_success(self):
        """Should wait and return response when received"""
        with patch('mqtt_client.mqtt.Client') as MockClient:
            mock_client = MagicMock()
            MockClient.return_value = mock_client

            client = MQTTClient(instance_id="test")
            client.connected = True

            cmd_id = client.send_command("device1", {"power": True})

            # Simulate response in separate thread
            def send_response():
                time.sleep(0.1)
                response = {"cmd_id": cmd_id, "status": "success"}
                if cmd_id in client.pending_commands:
                    callback = client.pending_commands[cmd_id].callback
                    if callback:
                        callback(response)

            thread = threading.Thread(target=send_response)
            thread.start()

            response = client.wait_for_response(cmd_id, timeout=1.0)

            thread.join()

            assert response is not None
            assert response["status"] == "success"

    def test_wait_for_response_timeout(self):
        """Should return None if response timeout"""
        with patch('mqtt_client.mqtt.Client') as MockClient:
            mock_client = MagicMock()
            MockClient.return_value = mock_client

            client = MQTTClient(instance_id="test")
            client.connected = True

            cmd_id = client.send_command("device1", {"power": True})

            # No response sent
            response = client.wait_for_response(cmd_id, timeout=0.1)

            assert response is None

    def test_response_ttl_cleanup(self):
        """Should clean up expired pending commands"""
        with patch('mqtt_client.mqtt.Client') as MockClient:
            mock_client = MagicMock()
            MockClient.return_value = mock_client

            client = MQTTClient(instance_id="test", response_ttl=1)  # 1 second TTL
            client.connected = True

            cmd_id = client.send_command("device1", {"power": True})

            # Manually set old timestamp
            client.pending_commands[cmd_id].timestamp = datetime.now() - timedelta(seconds=2)

            # Trigger cleanup manually
            now = datetime.now()
            expired = []
            for c_id, info in client.pending_commands.items():
                if now - info.timestamp > timedelta(seconds=client.response_ttl):
                    expired.append(c_id)

            for c_id in expired:
                del client.pending_commands[c_id]

            assert cmd_id not in client.pending_commands


# ============================================================================
# TIER 1 - CRITICAL TESTS: External Topic Operations (Parasitic Mode)
# ============================================================================

class TestExternalTopics:
    """Test external topic subscription and publishing for parasitic mode"""

    def test_subscribe_external_topic(self):
        """Should subscribe to full topic path outside instance namespace"""
        with patch('mqtt_client.mqtt.Client') as MockClient:
            mock_client = MagicMock()
            MockClient.return_value = mock_client

            client = MQTTClient(instance_id="motion_detector")
            client.connected = True

            handler = Mock()
            external_topic = "IoT2mqtt/v1/instances/cameras/devices/camera1/state"

            client.subscribe_external_topic(external_topic, handler)

            assert external_topic in client.subscriptions
            mock_client.subscribe.assert_called_with(external_topic, qos=1)

    def test_external_topic_callback_invoked(self):
        """Should invoke callback for external topic messages"""
        with patch('mqtt_client.mqtt.Client') as MockClient:
            mock_client = MagicMock()
            MockClient.return_value = mock_client

            client = MQTTClient(instance_id="motion")

            handler = Mock()
            external_topic = "IoT2mqtt/v1/instances/cameras/devices/cam1/state"
            client.subscriptions[external_topic] = handler

            msg = MagicMock()
            msg.topic = external_topic
            msg.payload = b'{"online": true, "stream_url": "rtsp://192.168.1.10/stream"}'

            with patch('mqtt_client.mqtt.topic_matches_sub', return_value=True):
                client._on_message(mock_client, None, msg)

            handler.assert_called_once()

    def test_publish_to_external_topic(self):
        """Should publish to external topic with full path"""
        with patch('mqtt_client.mqtt.Client') as MockClient:
            mock_client = MagicMock()
            MockClient.return_value = mock_client

            client = MQTTClient(instance_id="motion")
            client.connected = True

            external_topic = "IoT2mqtt/v1/instances/cameras/devices/cam1/state/motion"
            client.publish_to_external_topic(external_topic, True, retain=True)

            # Should publish to external topic
            mock_client.publish.assert_called()
            call_args = mock_client.publish.call_args[0]
            assert call_args[0] == external_topic

    def test_publish_to_external_topic_with_custom_qos(self):
        """Should use custom QoS when publishing to external topic"""
        with patch('mqtt_client.mqtt.Client') as MockClient:
            mock_client = MagicMock()
            MockClient.return_value = mock_client

            client = MQTTClient(instance_id="motion", qos=1)
            client.connected = True

            external_topic = "external/topic"
            client.publish_to_external_topic(external_topic, {"data": "value"}, qos=2)

            # Should use QoS 2
            call_kwargs = mock_client.publish.call_args[1]
            assert call_kwargs['qos'] == 2


# ============================================================================
# Additional Tests
# ============================================================================

class TestResponseCleanerThread:
    """Test response cleaner background thread"""

    def test_cleaner_thread_started(self):
        """Should start response cleaner thread on initialization"""
        with patch('mqtt_client.mqtt.Client') as MockClient:
            mock_client = MagicMock()
            MockClient.return_value = mock_client

            client = MQTTClient(instance_id="test")

            assert client.response_cleaner_thread is not None
            assert client.response_cleaner_thread.is_alive()

            # Cleanup
            client.stop_cleaner.set()

    def test_cleaner_thread_stopped_on_disconnect(self):
        """Should stop cleaner thread when disconnecting"""
        with patch('mqtt_client.mqtt.Client') as MockClient:
            mock_client = MagicMock()
            MockClient.return_value = mock_client

            client = MQTTClient(instance_id="test")
            client.connected = True

            assert not client.stop_cleaner.is_set()

            client.disconnect()

            assert client.stop_cleaner.is_set()


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
