"""
Tests for MQTT service
"""

import pytest
import asyncio
import json
from unittest.mock import Mock, patch, MagicMock, AsyncMock
from datetime import datetime

from services.mqtt_service import MQTTService
import paho.mqtt.client as mqtt


class TestMQTTService:
    """Test MQTT service functionality"""

    @pytest.fixture
    def mqtt_config(self):
        """Default MQTT configuration for testing"""
        return {
            "host": "localhost",
            "port": 1883,
            "username": "test_user",
            "password": "test_pass",
            "client_prefix": "test",
            "base_topic": "TestTopic",
            "keepalive": 60
        }

    @pytest.fixture
    def mock_mqtt_client(self):
        """Mock MQTT client"""
        mock_client = Mock()
        mock_client.connect.return_value = 0  # Success
        mock_client.reconnect.return_value = 0
        mock_client.publish.return_value.rc = 0
        mock_client.loop_start.return_value = None
        mock_client.loop_stop.return_value = None
        mock_client.disconnect.return_value = None
        mock_client.subscribe.return_value = (0, 1)
        mock_client.unsubscribe.return_value = (0, 1)
        return mock_client

    @pytest.fixture
    def mqtt_service(self, mqtt_config, mock_mqtt_client):
        """Create MQTTService with mocked client"""
        with patch('services.mqtt_service.mqtt.Client') as mock_mqtt:
            mock_mqtt.return_value = mock_mqtt_client
            service = MQTTService(mqtt_config)
            return service

    def test_init(self, mqtt_config):
        """Test MQTTService initialization"""
        service = MQTTService(mqtt_config)

        assert service.config == mqtt_config
        assert service.connected is False
        assert service.client is None
        assert len(service.subscriptions) == 0
        assert len(service.topic_cache) == 0

    def test_connect_success(self, mqtt_service, mock_mqtt_client):
        """Test successful MQTT connection"""
        result = mqtt_service.connect()

        # Should attempt to connect
        mock_mqtt_client.connect.assert_called_once_with(
            "localhost", 1883, keepalive=60
        )
        mock_mqtt_client.loop_start.assert_called_once()

        # Simulate successful connection callback
        mqtt_service._on_connect(mock_mqtt_client, None, None, 0)
        assert mqtt_service.connected is True

    def test_connect_with_auth(self, mqtt_service, mock_mqtt_client):
        """Test connection with authentication"""
        mqtt_service.connect()

        mock_mqtt_client.username_pw_set.assert_called_once_with(
            "test_user", "test_pass"
        )

    def test_connect_failure(self, mqtt_service, mock_mqtt_client):
        """Test failed MQTT connection"""
        mock_mqtt_client.connect.return_value = 1  # Connection failed

        result = mqtt_service.connect()

        # Simulate failed connection callback
        mqtt_service._on_connect(mock_mqtt_client, None, None, 1)
        assert mqtt_service.connected is False

    def test_disconnect(self, mqtt_service, mock_mqtt_client):
        """Test MQTT disconnection"""
        mqtt_service.client = mock_mqtt_client
        mqtt_service.connected = True

        mqtt_service.disconnect()

        mock_mqtt_client.loop_stop.assert_called_once()
        mock_mqtt_client.disconnect.assert_called_once()
        assert mqtt_service.connected is False

    def test_on_connect_callback(self, mqtt_service, mock_mqtt_client):
        """Test on_connect callback"""
        mqtt_service._on_connect(mock_mqtt_client, None, None, 0)

        assert mqtt_service.connected is True
        # Should subscribe to all topics
        mock_mqtt_client.subscribe.assert_called_with("#", qos=1)

    def test_on_disconnect_callback(self, mqtt_service, mock_mqtt_client):
        """Test on_disconnect callback"""
        mqtt_service.connected = True
        mqtt_service.client = mock_mqtt_client

        # Test unexpected disconnection
        mqtt_service._on_disconnect(mock_mqtt_client, None, 1)

        assert mqtt_service.connected is False
        mock_mqtt_client.reconnect.assert_called_once()

    def test_on_message_json_payload(self, mqtt_service):
        """Test on_message callback with JSON payload"""
        mock_msg = Mock()
        mock_msg.topic = "test/topic"
        mock_msg.payload = b'{"value": 42, "status": "ok"}'
        mock_msg.retain = False
        mock_msg.qos = 1

        mqtt_service._on_message(None, None, mock_msg)

        assert "test/topic" in mqtt_service.topic_cache
        cached = mqtt_service.topic_cache["test/topic"]
        assert cached["value"] == {"value": 42, "status": "ok"}
        assert cached["retained"] is False
        assert cached["qos"] == 1

    def test_on_message_text_payload(self, mqtt_service):
        """Test on_message callback with text payload"""
        mock_msg = Mock()
        mock_msg.topic = "test/topic"
        mock_msg.payload = b'plain text message'
        mock_msg.retain = True
        mock_msg.qos = 0

        mqtt_service._on_message(None, None, mock_msg)

        assert "test/topic" in mqtt_service.topic_cache
        cached = mqtt_service.topic_cache["test/topic"]
        assert cached["value"] == "plain text message"
        assert cached["retained"] is True

    def test_on_message_empty_payload(self, mqtt_service):
        """Test on_message callback with empty payload (topic deletion)"""
        # First add a topic
        mqtt_service.topic_cache["test/topic"] = {"value": "data"}

        mock_msg = Mock()
        mock_msg.topic = "test/topic"
        mock_msg.payload = b''
        mock_msg.retain = False

        mqtt_service._on_message(None, None, mock_msg)

        # Topic should be removed from cache
        assert "test/topic" not in mqtt_service.topic_cache

    def test_publish_json(self, mqtt_service, mock_mqtt_client):
        """Test publishing JSON message"""
        mqtt_service.client = mock_mqtt_client
        mqtt_service.connected = True

        data = {"temperature": 25.5, "humidity": 60}
        result = mqtt_service.publish("sensors/room1", data, qos=1, retain=True)

        assert result is True
        mock_mqtt_client.publish.assert_called_once_with(
            "sensors/room1",
            '{"temperature": 25.5, "humidity": 60}',
            qos=1,
            retain=True
        )

    def test_publish_string(self, mqtt_service, mock_mqtt_client):
        """Test publishing string message"""
        mqtt_service.client = mock_mqtt_client
        mqtt_service.connected = True

        result = mqtt_service.publish("status", "online")

        assert result is True
        mock_mqtt_client.publish.assert_called_once_with(
            "status", "online", qos=1, retain=False
        )

    def test_publish_not_connected(self, mqtt_service):
        """Test publishing when not connected"""
        mqtt_service.connected = False

        result = mqtt_service.publish("test/topic", "data")

        assert result is False

    def test_subscribe_unsubscribe(self, mqtt_service, mock_mqtt_client):
        """Test subscribing and unsubscribing to topics"""
        mqtt_service.client = mock_mqtt_client
        mqtt_service.connected = True

        mqtt_service.subscribe("sensors/+")
        mock_mqtt_client.subscribe.assert_called_with("sensors/+")

        mqtt_service.unsubscribe("sensors/+")
        mock_mqtt_client.unsubscribe.assert_called_with("sensors/+")

    def test_get_topics_list(self, mqtt_service):
        """Test getting topics list"""
        # Add some topics to cache
        mqtt_service.topic_cache = {
            "sensors/temp": {
                "value": 25.5,
                "timestamp": "2024-01-01T00:00:00",
                "retained": False,
                "qos": 1
            },
            "sensors/humidity": {
                "value": 60,
                "timestamp": "2024-01-01T00:01:00",
                "retained": True,
                "qos": 0
            }
        }

        topics = mqtt_service.get_topics_list()

        assert len(topics) == 2
        assert any(t["topic"] == "sensors/temp" and t["value"] == 25.5 for t in topics)
        assert any(t["topic"] == "sensors/humidity" and t["value"] == 60 for t in topics)

    def test_get_topic_value(self, mqtt_service):
        """Test getting cached topic value"""
        mqtt_service.topic_cache["test/topic"] = {
            "value": "test_value",
            "timestamp": "2024-01-01T00:00:00"
        }

        value = mqtt_service.get_topic_value("test/topic")
        assert value["value"] == "test_value"

        value = mqtt_service.get_topic_value("nonexistent/topic")
        assert value is None

    def test_send_command(self, mqtt_service, mock_mqtt_client):
        """Test sending device command"""
        mqtt_service.client = mock_mqtt_client
        mqtt_service.connected = True

        command = {"action": "turn_on", "brightness": 80}
        cmd_id = mqtt_service.send_command("instance1", "device1", command)

        assert cmd_id is not None
        assert len(cmd_id) == 36  # UUID length

        # Check if publish was called with correct topic and payload
        call_args = mock_mqtt_client.publish.call_args
        topic = call_args[0][0]
        payload = json.loads(call_args[0][1])

        assert topic == "TestTopic/v1/instances/instance1/devices/device1/cmd"
        assert payload["id"] == cmd_id
        assert payload["values"] == command
        assert "timestamp" in payload

    def test_get_device_state(self, mqtt_service):
        """Test getting device state"""
        # Add device state to cache
        state_topic = "TestTopic/v1/instances/instance1/devices/device1/state"
        mqtt_service.topic_cache[state_topic] = {
            "value": {"power": "on", "brightness": 75}
        }

        state = mqtt_service.get_device_state("instance1", "device1")
        assert state == {"power": "on", "brightness": 75}

        # Test non-existent device
        state = mqtt_service.get_device_state("instance1", "nonexistent")
        assert state is None

    def test_get_instance_devices(self, mqtt_service):
        """Test getting list of devices for instance"""
        # Add device topics to cache
        mqtt_service.topic_cache.update({
            "TestTopic/v1/instances/inst1/devices/device1/state": {"value": {}},
            "TestTopic/v1/instances/inst1/devices/device2/state": {"value": {}},
            "TestTopic/v1/instances/inst2/devices/device3/state": {"value": {}},
            "TestTopic/v1/instances/inst1/status": {"value": "online"}  # Not a device
        })

        devices = mqtt_service.get_instance_devices("inst1")
        assert set(devices) == {"device1", "device2"}

        devices = mqtt_service.get_instance_devices("nonexistent")
        assert devices == []

    @pytest.mark.asyncio
    async def test_websocket_handlers(self, mqtt_service):
        """Test WebSocket handler management"""
        handler1 = AsyncMock()
        handler2 = AsyncMock()

        # Add handlers
        mqtt_service.add_websocket_handler(handler1)
        mqtt_service.add_websocket_handler(handler2)

        assert len(mqtt_service.websocket_handlers) == 2

        # Remove handler
        mqtt_service.remove_websocket_handler(handler1)
        assert len(mqtt_service.websocket_handlers) == 1
        assert handler2 in mqtt_service.websocket_handlers

    def test_clear_instance_topics(self, mqtt_service, mock_mqtt_client):
        """Test clearing all topics for an instance"""
        mqtt_service.client = mock_mqtt_client
        mqtt_service.connected = True

        # Add instance topics to cache
        mqtt_service.topic_cache.update({
            "TestTopic/v1/instances/inst1/status": {"value": "online"},
            "TestTopic/v1/instances/inst1/devices/dev1/state": {"value": {}},
            "TestTopic/v1/instances/inst2/status": {"value": "online"}  # Different instance
        })

        result = mqtt_service.clear_instance_topics("inst1")

        assert result is True
        # Should have published empty messages to clear topics
        assert mock_mqtt_client.publish.call_count > 0

        # inst1 topics should be removed from cache
        remaining_topics = [t for t in mqtt_service.topic_cache.keys()
                          if "inst1" in t]
        assert len(remaining_topics) == 0

        # inst2 topics should remain
        remaining_topics = [t for t in mqtt_service.topic_cache.keys()
                          if "inst2" in t]
        assert len(remaining_topics) == 1

    def test_clear_all_iot2mqtt_topics(self, mqtt_service, mock_mqtt_client):
        """Test clearing all IoT2MQTT topics"""
        mqtt_service.client = mock_mqtt_client
        mqtt_service.connected = True

        # Add various topics to cache
        mqtt_service.topic_cache.update({
            "TestTopic/v1/instances/inst1/status": {"value": "online"},
            "TestTopic/v1/instances/inst2/status": {"value": "online"},
            "other/topic": {"value": "data"}  # Non-IoT2MQTT topic
        })

        result = mqtt_service.clear_all_iot2mqtt_topics()

        assert result is True

        # Only non-IoT2MQTT topics should remain
        remaining_topics = list(mqtt_service.topic_cache.keys())
        assert remaining_topics == ["other/topic"]