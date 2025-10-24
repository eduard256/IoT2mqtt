"""
Comprehensive tests for Cameras Connector

Tests cover:
1. Connector initialization with go2rtc integration
2. Port configuration from instance config
3. External host detection and configuration
4. go2rtc readiness waiting
5. Stream URL generation for all formats
6. Device state retrieval from go2rtc API
7. Stream validation integration
8. Home Assistant discovery with stream URLs
9. Device config caching
10. Error handling and API failures
"""

import pytest
import json
import socket
from unittest.mock import Mock, MagicMock, patch, call
from pathlib import Path
import sys
import tempfile
import requests

# Add paths
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / 'shared'))
sys.path.insert(0, str(Path(__file__).parent.parent))

from connector import Connector, get_host_ip


# ============================================================================
# Test Fixtures
# ============================================================================

@pytest.fixture
def cameras_config():
    """Sample cameras instance config"""
    return {
        "instance_id": "cameras_test",
        "connector_type": "cameras",
        "ports": {
            "go2rtc_api": "1984",
            "go2rtc_rtsp": "8554",
            "go2rtc_webrtc": "8555",
            "go2rtc_homekit": "8443"
        },
        "mqtt": {
            "qos": 1,
            "retain_state": True
        },
        "ha_discovery_enabled": True,
        "update_interval": 30,
        "devices": [
            {
                "device_id": "camera1",
                "name": "Front Door Camera",
                "enabled": True,
                "brand": "Hikvision",
                "model": "DS-2CD2142",
                "ip": "192.168.1.10",
                "stream_type": "FFMPEG",
                "stream_url": "rtsp://192.168.1.10:554/stream",
                "username": "admin",
                "password": "password123"
            },
            {
                "device_id": "camera2",
                "name": "Back Yard Camera",
                "enabled": False,
                "brand": "Dahua",
                "model": "IPC-HDW",
                "ip": "192.168.1.11",
                "stream_type": "ONVIF"
            },
            {
                "device_id": "camera3",
                "name": "Garage Camera",
                "enabled": True,
                "brand": "Generic",
                "model": "JPEG Camera",
                "ip": "192.168.1.12",
                "stream_type": "JPEG"
            }
        ]
    }


@pytest.fixture
def temp_cameras_config(cameras_config, tmp_path):
    """Create temporary config file"""
    config_file = tmp_path / "cameras_test.json"
    with open(config_file, 'w') as f:
        json.dump(cameras_config, f)
    return config_file


@pytest.fixture
def mock_go2rtc_api():
    """Mock go2rtc API responses"""
    return {
        "version": "1.8.5",
        "streams": {
            "camera1": {
                "producers": [{"type": "rtsp", "url": "rtsp://..."}],
                "consumers": []
            },
            "camera3": {
                "producers": [{"type": "exec"}],
                "consumers": [{"type": "http"}]
            }
        }
    }


# ============================================================================
# TIER 1 - CRITICAL TESTS: Host IP Detection
# ============================================================================

class TestHostIPDetection:
    """Test external host IP detection"""

    def test_get_host_ip_from_env(self, monkeypatch):
        """Should use EXTERNAL_HOST from environment if set"""
        monkeypatch.setenv("EXTERNAL_HOST", "192.168.1.100")

        result = get_host_ip()

        assert result == "192.168.1.100"

    def test_get_host_ip_auto_detect(self, monkeypatch):
        """Should auto-detect IP by connecting to MQTT broker"""
        monkeypatch.delenv("EXTERNAL_HOST", raising=False)
        monkeypatch.setenv("MQTT_HOST", "mqtt.local")
        monkeypatch.setenv("MQTT_PORT", "1883")

        # Mock socket
        with patch('socket.socket') as mock_socket:
            mock_sock_instance = MagicMock()
            mock_sock_instance.getsockname.return_value = ("192.168.1.50", 12345)
            mock_socket.return_value = mock_sock_instance

            result = get_host_ip()

            assert result == "192.168.1.50"
            mock_sock_instance.connect.assert_called_once_with(("mqtt.local", 1883))

    def test_get_host_ip_fallback_to_localhost(self, monkeypatch):
        """Should fallback to localhost if auto-detect fails"""
        monkeypatch.delenv("EXTERNAL_HOST", raising=False)

        # Mock socket to raise exception
        with patch('socket.socket') as mock_socket:
            mock_socket.side_effect = Exception("Network error")

            result = get_host_ip()

            assert result == "localhost"


# ============================================================================
# TIER 1 - CRITICAL TESTS: Connector Initialization
# ============================================================================

class TestConnectorInitialization:
    """Test connector initialization"""

    def test_initialization_with_config(self, temp_cameras_config, monkeypatch):
        """Should initialize with config file"""
        monkeypatch.setenv("INSTANCE_NAME", "cameras_test")
        monkeypatch.setenv("EXTERNAL_HOST", "192.168.1.100")

        with patch('base_connector.MQTTClient'), \
             patch('base_connector.DiscoveryGenerator'), \
             patch('connector.StreamValidator'):

            # Mock config loading
            with patch.object(Connector, '_load_config') as mock_load:
                mock_load.return_value = json.loads(temp_cameras_config.read_text())

                connector = Connector(
                    config_path=str(temp_cameras_config),
                    instance_name="cameras_test"
                )

                assert connector.instance_name == "cameras_test"
                assert connector.instance_id == "cameras_test"
                assert connector.external_host == "192.168.1.100"

    def test_port_configuration_from_instance_config(self, cameras_config):
        """Should read ports from instance config"""
        with patch('base_connector.MQTTClient'), \
             patch('base_connector.DiscoveryGenerator'), \
             patch('connector.StreamValidator'), \
             patch.object(Connector, '_load_config', return_value=cameras_config):

            connector = Connector(
                config_path="/tmp/test.json",
                instance_name="cameras_test"
            )

            assert connector.go2rtc_api_port == "1984"
            assert connector.go2rtc_rtsp_port == "8554"
            assert connector.go2rtc_webrtc_port == "8555"
            assert connector.go2rtc_homekit_port == "8443"

    def test_port_fallback_to_env_vars(self, monkeypatch):
        """Should fallback to env vars if ports not in config"""
        monkeypatch.setenv("GO2RTC_API_PORT", "2000")
        monkeypatch.setenv("GO2RTC_RTSP_PORT", "9000")

        config = {
            "instance_id": "cameras_test",
            "devices": []
        }

        with patch('base_connector.MQTTClient'), \
             patch('base_connector.DiscoveryGenerator'), \
             patch('connector.StreamValidator'), \
             patch.object(Connector, '_load_config', return_value=config):

            connector = Connector(
                config_path="/tmp/test.json",
                instance_name="cameras_test"
            )

            assert connector.go2rtc_api_port == "2000"
            assert connector.go2rtc_rtsp_port == "9000"

    def test_device_config_caching(self, cameras_config):
        """Should cache enabled device configs by device_id"""
        with patch('base_connector.MQTTClient'), \
             patch('base_connector.DiscoveryGenerator'), \
             patch('connector.StreamValidator'), \
             patch.object(Connector, '_load_config', return_value=cameras_config):

            connector = Connector(
                config_path="/tmp/test.json",
                instance_name="cameras_test"
            )

            # Only enabled devices should be cached
            assert "camera1" in connector.device_configs
            assert "camera3" in connector.device_configs
            assert "camera2" not in connector.device_configs  # Disabled

    def test_go2rtc_api_url_construction(self, cameras_config):
        """Should construct correct go2rtc API URL"""
        with patch('base_connector.MQTTClient'), \
             patch('base_connector.DiscoveryGenerator'), \
             patch('connector.StreamValidator'), \
             patch.object(Connector, '_load_config', return_value=cameras_config):

            connector = Connector(
                config_path="/tmp/test.json",
                instance_name="cameras_test"
            )

            assert connector.go2rtc_api == "http://localhost:1984/api"

    def test_stream_validator_initialization(self, cameras_config):
        """Should initialize StreamValidator"""
        with patch('base_connector.MQTTClient'), \
             patch('base_connector.DiscoveryGenerator'), \
             patch('connector.StreamValidator') as MockValidator:

            with patch.object(Connector, '_load_config', return_value=cameras_config):
                connector = Connector(
                    config_path="/tmp/test.json",
                    instance_name="cameras_test"
                )

                MockValidator.assert_called_once_with(
                    validation_interval=300,
                    timeout=5
                )


# ============================================================================
# TIER 1 - CRITICAL TESTS: go2rtc Readiness Waiting
# ============================================================================

class TestGo2RTCReadiness:
    """Test waiting for go2rtc to be ready"""

    def test_wait_for_go2rtc_success(self, cameras_config):
        """Should wait for go2rtc and return True when ready"""
        with patch('base_connector.MQTTClient'), \
             patch('base_connector.DiscoveryGenerator'), \
             patch('connector.StreamValidator'), \
             patch.object(Connector, '_load_config', return_value=cameras_config):

            connector = Connector(
                config_path="/tmp/test.json",
                instance_name="cameras_test"
            )

            # Mock successful go2rtc response
            with patch('requests.get') as mock_get:
                mock_response = Mock()
                mock_response.ok = True
                mock_response.json.return_value = {"version": "1.8.5"}
                mock_get.return_value = mock_response

                result = connector._wait_for_go2rtc()

                assert result is True

    def test_wait_for_go2rtc_retry_on_failure(self, cameras_config):
        """Should retry if go2rtc not ready"""
        with patch('base_connector.MQTTClient'), \
             patch('base_connector.DiscoveryGenerator'), \
             patch('connector.StreamValidator'), \
             patch.object(Connector, '_load_config', return_value=cameras_config):

            connector = Connector(
                config_path="/tmp/test.json",
                instance_name="cameras_test"
            )
            connector.max_retries = 3

            call_count = [0]

            def mock_get_side_effect(*args, **kwargs):
                call_count[0] += 1
                if call_count[0] < 3:
                    raise requests.exceptions.ConnectionError("Connection refused")
                else:
                    mock_resp = Mock()
                    mock_resp.ok = True
                    mock_resp.json.return_value = {"version": "1.8.5"}
                    return mock_resp

            with patch('requests.get', side_effect=mock_get_side_effect), \
                 patch('time.sleep'):

                result = connector._wait_for_go2rtc()

                assert result is True
                assert call_count[0] == 3

    def test_wait_for_go2rtc_timeout(self, cameras_config):
        """Should return False after max retries"""
        with patch('base_connector.MQTTClient'), \
             patch('base_connector.DiscoveryGenerator'), \
             patch('connector.StreamValidator'), \
             patch.object(Connector, '_load_config', return_value=cameras_config):

            connector = Connector(
                config_path="/tmp/test.json",
                instance_name="cameras_test"
            )
            connector.max_retries = 3

            # Mock always failing
            with patch('requests.get') as mock_get:
                mock_get.side_effect = requests.exceptions.ConnectionError("Connection refused")

                with patch('time.sleep'):
                    result = connector._wait_for_go2rtc()

                assert result is False

    def test_initialize_connection_success(self, cameras_config):
        """Should initialize connection and start validator"""
        with patch('base_connector.MQTTClient'), \
             patch('base_connector.DiscoveryGenerator'), \
             patch('connector.StreamValidator') as MockValidator:

            mock_validator_instance = MockValidator.return_value

            with patch.object(Connector, '_load_config', return_value=cameras_config):
                connector = Connector(
                    config_path="/tmp/test.json",
                    instance_name="cameras_test"
                )

                with patch.object(connector, '_wait_for_go2rtc', return_value=True):
                    connector.initialize_connection()

                    mock_validator_instance.start.assert_called_once()

    def test_initialize_connection_go2rtc_failure(self, cameras_config):
        """Should raise RuntimeError if go2rtc fails to start"""
        with patch('base_connector.MQTTClient'), \
             patch('base_connector.DiscoveryGenerator'), \
             patch('connector.StreamValidator'), \
             patch.object(Connector, '_load_config', return_value=cameras_config):

            connector = Connector(
                config_path="/tmp/test.json",
                instance_name="cameras_test"
            )

            with patch.object(connector, '_wait_for_go2rtc', return_value=False):
                with pytest.raises(RuntimeError, match="go2rtc failed to start"):
                    connector.initialize_connection()


# ============================================================================
# TIER 1 - CRITICAL TESTS: Stream URL Generation
# ============================================================================

class TestStreamURLGeneration:
    """Test stream URL generation"""

    def test_generate_stream_urls_all_formats(self, cameras_config, monkeypatch):
        """Should generate URLs for all stream formats"""
        monkeypatch.setenv("EXTERNAL_HOST", "192.168.1.100")

        with patch('base_connector.MQTTClient'), \
             patch('base_connector.DiscoveryGenerator'), \
             patch('connector.StreamValidator'), \
             patch.object(Connector, '_load_config', return_value=cameras_config):

            connector = Connector(
                config_path="/tmp/test.json",
                instance_name="cameras_test"
            )

            urls = connector._generate_stream_urls("camera1")

            # Check all formats present
            assert "mp4" in urls
            assert "m3u8" in urls
            assert "mjpeg" in urls
            assert "flv" in urls
            assert "ts" in urls
            assert "aac" in urls
            assert "jpeg" in urls
            assert "ws" in urls
            assert "rtsp" in urls

    def test_stream_urls_use_external_host(self, cameras_config, monkeypatch):
        """Should use external host in URLs"""
        monkeypatch.setenv("EXTERNAL_HOST", "192.168.1.100")

        with patch('base_connector.MQTTClient'), \
             patch('base_connector.DiscoveryGenerator'), \
             patch('connector.StreamValidator'), \
             patch.object(Connector, '_load_config', return_value=cameras_config):

            connector = Connector(
                config_path="/tmp/test.json",
                instance_name="cameras_test"
            )

            urls = connector._generate_stream_urls("camera1")

            # All HTTP URLs should use external host
            assert "192.168.1.100" in urls["mp4"]
            assert "192.168.1.100" in urls["m3u8"]
            assert "192.168.1.100" in urls["jpeg"]

    def test_stream_urls_use_configured_ports(self, cameras_config):
        """Should use ports from instance config"""
        with patch('base_connector.MQTTClient'), \
             patch('base_connector.DiscoveryGenerator'), \
             patch('connector.StreamValidator'), \
             patch.object(Connector, '_load_config', return_value=cameras_config):

            connector = Connector(
                config_path="/tmp/test.json",
                instance_name="cameras_test"
            )

            urls = connector._generate_stream_urls("camera1")

            # Check API port
            assert ":1984/api/stream.mp4" in urls["mp4"]
            assert ":1984/api/frame.jpeg" in urls["jpeg"]

            # Check RTSP port
            assert ":8554/camera1" in urls["rtsp"]

    def test_stream_urls_include_device_id_parameter(self, cameras_config):
        """Should include device_id as src parameter"""
        with patch('base_connector.MQTTClient'), \
             patch('base_connector.DiscoveryGenerator'), \
             patch('connector.StreamValidator'), \
             patch.object(Connector, '_load_config', return_value=cameras_config):

            connector = Connector(
                config_path="/tmp/test.json",
                instance_name="cameras_test"
            )

            urls = connector._generate_stream_urls("camera1")

            assert "src=camera1" in urls["mp4"]
            assert "src=camera1" in urls["m3u8"]
            assert "src=camera1" in urls["jpeg"]

    def test_rtsp_url_format(self, cameras_config):
        """Should generate correct RTSP URL format"""
        with patch('base_connector.MQTTClient'), \
             patch('base_connector.DiscoveryGenerator'), \
             patch('connector.StreamValidator'), \
             patch.object(Connector, '_load_config', return_value=cameras_config):

            connector = Connector(
                config_path="/tmp/test.json",
                instance_name="cameras_test"
            )

            urls = connector._generate_stream_urls("camera1")

            # RTSP URL should be rtsp://host:port/device_id
            assert urls["rtsp"].startswith("rtsp://")
            assert urls["rtsp"].endswith("/camera1")

    def test_websocket_url_format(self, cameras_config):
        """Should generate WebSocket URL"""
        with patch('base_connector.MQTTClient'), \
             patch('base_connector.DiscoveryGenerator'), \
             patch('connector.StreamValidator'), \
             patch.object(Connector, '_load_config', return_value=cameras_config):

            connector = Connector(
                config_path="/tmp/test.json",
                instance_name="cameras_test"
            )

            urls = connector._generate_stream_urls("camera1")

            assert urls["ws"].startswith("ws://")
            assert "api/ws" in urls["ws"]


# ============================================================================
# TIER 1 - CRITICAL TESTS: Device State Retrieval
# ============================================================================

class TestDeviceStateRetrieval:
    """Test device state retrieval from go2rtc"""

    def test_get_device_state_success(self, cameras_config, mock_go2rtc_api):
        """Should get device state from go2rtc API"""
        with patch('base_connector.MQTTClient'), \
             patch('base_connector.DiscoveryGenerator'), \
             patch('connector.StreamValidator') as MockValidator:

            mock_validator = MockValidator.return_value

            with patch.object(Connector, '_load_config', return_value=cameras_config):
                connector = Connector(
                    config_path="/tmp/test.json",
                    instance_name="cameras_test"
                )

                # Mock go2rtc API response
                with patch('requests.get') as mock_get:
                    mock_response = Mock()
                    mock_response.ok = True
                    mock_response.json.return_value = mock_go2rtc_api["streams"]
                    mock_get.return_value = mock_response

                    device_config = cameras_config["devices"][0]
                    state = connector.get_device_state("camera1", device_config)

                    assert state["online"] is True
                    assert state["device_id"] == "camera1"
                    assert state["name"] == "Front Door Camera"
                    assert "stream_urls" in state

    def test_get_device_state_includes_all_metadata(self, cameras_config, mock_go2rtc_api):
        """Should include all device metadata in state"""
        with patch('base_connector.MQTTClient'), \
             patch('base_connector.DiscoveryGenerator'), \
             patch('connector.StreamValidator'):

            with patch.object(Connector, '_load_config', return_value=cameras_config):
                connector = Connector(
                    config_path="/tmp/test.json",
                    instance_name="cameras_test"
                )

                with patch('requests.get') as mock_get:
                    mock_response = Mock()
                    mock_response.ok = True
                    mock_response.json.return_value = mock_go2rtc_api["streams"]
                    mock_get.return_value = mock_response

                    device_config = cameras_config["devices"][0]
                    state = connector.get_device_state("camera1", device_config)

                    assert state["brand"] == "Hikvision"
                    assert state["model"] == "DS-2CD2142"
                    assert state["ip"] == "192.168.1.10"
                    assert state["stream_type"] == "FFMPEG"

    def test_get_device_state_adds_streams_to_validator(self, cameras_config, mock_go2rtc_api):
        """Should add streams to validator queue"""
        with patch('base_connector.MQTTClient'), \
             patch('base_connector.DiscoveryGenerator'), \
             patch('connector.StreamValidator') as MockValidator:

            mock_validator = MockValidator.return_value

            with patch.object(Connector, '_load_config', return_value=cameras_config):
                connector = Connector(
                    config_path="/tmp/test.json",
                    instance_name="cameras_test"
                )

                with patch('requests.get') as mock_get:
                    mock_response = Mock()
                    mock_response.ok = True
                    mock_response.json.return_value = mock_go2rtc_api["streams"]
                    mock_get.return_value = mock_response

                    device_config = cameras_config["devices"][0]
                    connector.get_device_state("camera1", device_config)

                    # Should have called add_stream for HTTP formats (not rtsp/ws)
                    assert mock_validator.add_stream.called

    def test_get_device_state_device_not_in_go2rtc(self, cameras_config):
        """Should return offline state if device not in go2rtc"""
        with patch('base_connector.MQTTClient'), \
             patch('base_connector.DiscoveryGenerator'), \
             patch('connector.StreamValidator'):

            with patch.object(Connector, '_load_config', return_value=cameras_config):
                connector = Connector(
                    config_path="/tmp/test.json",
                    instance_name="cameras_test"
                )

                with patch('requests.get') as mock_get:
                    mock_response = Mock()
                    mock_response.ok = True
                    mock_response.json.return_value = {}  # Empty streams
                    mock_get.return_value = mock_response

                    device_config = cameras_config["devices"][0]
                    state = connector.get_device_state("camera1", device_config)

                    assert state["online"] is False
                    assert "error" in state
                    assert "not configured in go2rtc" in state["error"]

    def test_get_device_state_go2rtc_api_error(self, cameras_config):
        """Should handle go2rtc API errors"""
        with patch('base_connector.MQTTClient'), \
             patch('base_connector.DiscoveryGenerator'), \
             patch('connector.StreamValidator'):

            with patch.object(Connector, '_load_config', return_value=cameras_config):
                connector = Connector(
                    config_path="/tmp/test.json",
                    instance_name="cameras_test"
                )

                with patch('requests.get') as mock_get:
                    mock_response = Mock()
                    mock_response.ok = False
                    mock_response.status_code = 500
                    mock_get.return_value = mock_response

                    device_config = cameras_config["devices"][0]
                    state = connector.get_device_state("camera1", device_config)

                    assert state["online"] is False
                    assert "error" in state

    def test_get_device_state_includes_validation_status(self, cameras_config, mock_go2rtc_api):
        """Should include validation status in state"""
        with patch('base_connector.MQTTClient'), \
             patch('base_connector.DiscoveryGenerator'), \
             patch('connector.StreamValidator') as MockValidator:

            mock_validator = MockValidator.return_value
            mock_validator.get_status.return_value = {
                "mp4": {"status": "ok", "last_check": "2025-10-24T10:00:00Z"}
            }

            with patch.object(Connector, '_load_config', return_value=cameras_config):
                connector = Connector(
                    config_path="/tmp/test.json",
                    instance_name="cameras_test"
                )

                with patch('requests.get') as mock_get:
                    mock_response = Mock()
                    mock_response.ok = True
                    mock_response.json.return_value = mock_go2rtc_api["streams"]
                    mock_get.return_value = mock_response

                    device_config = cameras_config["devices"][0]
                    state = connector.get_device_state("camera1", device_config)

                    assert "stream_validation" in state
                    assert "mp4" in state["stream_validation"]

    def test_get_device_state_includes_producers_consumers(self, cameras_config, mock_go2rtc_api):
        """Should include producer/consumer counts from go2rtc"""
        with patch('base_connector.MQTTClient'), \
             patch('base_connector.DiscoveryGenerator'), \
             patch('connector.StreamValidator'):

            with patch.object(Connector, '_load_config', return_value=cameras_config):
                connector = Connector(
                    config_path="/tmp/test.json",
                    instance_name="cameras_test"
                )

                with patch('requests.get') as mock_get:
                    mock_response = Mock()
                    mock_response.ok = True
                    mock_response.json.return_value = mock_go2rtc_api["streams"]
                    mock_get.return_value = mock_response

                    device_config = cameras_config["devices"][0]
                    state = connector.get_device_state("camera1", device_config)

                    assert "producers" in state
                    assert "consumers" in state
                    assert state["producers"] == 1  # From mock data


# ============================================================================
# TIER 1 - CRITICAL TESTS: Home Assistant Discovery
# ============================================================================

class TestHomeAssistantDiscovery:
    """Test HA discovery with stream URLs"""

    def test_publish_ha_discovery_adds_stream_urls(self, cameras_config):
        """Should add stream URLs to device config for discovery"""
        with patch('base_connector.MQTTClient') as MockMQTT, \
             patch('base_connector.DiscoveryGenerator') as MockDiscovery, \
             patch('connector.StreamValidator'):

            mock_mqtt = MockMQTT.return_value
            mock_discovery = MockDiscovery.return_value

            with patch.object(Connector, '_load_config', return_value=cameras_config):
                connector = Connector(
                    config_path="/tmp/test.json",
                    instance_name="cameras_test"
                )

                connector._publish_ha_discovery()

                # Should have called generate_device_discovery
                assert mock_discovery.generate_device_discovery.called

                # Check that stream_urls were added
                call_args = mock_discovery.generate_device_discovery.call_args_list
                for call in call_args:
                    device_config = call[1]['device_config']
                    if 'stream_urls' in device_config:
                        assert 'mp4' in device_config['stream_urls']
                        assert 'rtsp' in device_config['stream_urls']

    def test_publish_ha_discovery_sets_camera_class(self, cameras_config):
        """Should set device class to security.camera"""
        with patch('base_connector.MQTTClient') as MockMQTT, \
             patch('base_connector.DiscoveryGenerator') as MockDiscovery, \
             patch('connector.StreamValidator'):

            mock_discovery = MockDiscovery.return_value

            with patch.object(Connector, '_load_config', return_value=cameras_config):
                connector = Connector(
                    config_path="/tmp/test.json",
                    instance_name="cameras_test"
                )

                connector._publish_ha_discovery()

                call_args = mock_discovery.generate_device_discovery.call_args_list
                for call in call_args:
                    device_config = call[1]['device_config']
                    assert device_config['class'] == 'security.camera'

    def test_publish_ha_discovery_only_enabled_devices(self, cameras_config):
        """Should only publish discovery for enabled devices"""
        with patch('base_connector.MQTTClient') as MockMQTT, \
             patch('base_connector.DiscoveryGenerator') as MockDiscovery, \
             patch('connector.StreamValidator'):

            mock_discovery = MockDiscovery.return_value

            with patch.object(Connector, '_load_config', return_value=cameras_config):
                connector = Connector(
                    config_path="/tmp/test.json",
                    instance_name="cameras_test"
                )

                connector._publish_ha_discovery()

                # Should call generate_device_discovery for enabled devices only
                call_count = mock_discovery.generate_device_discovery.call_count
                assert call_count == 2  # camera1 and camera3 (camera2 is disabled)


# ============================================================================
# TIER 1 - CRITICAL TESTS: Cleanup
# ============================================================================

class TestCleanup:
    """Test connector cleanup"""

    def test_cleanup_connection_stops_validator(self, cameras_config):
        """Should stop stream validator on cleanup"""
        with patch('base_connector.MQTTClient'), \
             patch('base_connector.DiscoveryGenerator'), \
             patch('connector.StreamValidator') as MockValidator:

            mock_validator = MockValidator.return_value

            with patch.object(Connector, '_load_config', return_value=cameras_config):
                connector = Connector(
                    config_path="/tmp/test.json",
                    instance_name="cameras_test"
                )

                connector.cleanup_connection()

                mock_validator.stop.assert_called_once()


# ============================================================================
# TIER 1 - CRITICAL TESTS: Command Handling
# ============================================================================

class TestCommandHandling:
    """Test camera command handling"""

    def test_set_device_state_logs_command(self, cameras_config):
        """Should log commands received (PTZ not yet implemented)"""
        with patch('base_connector.MQTTClient'), \
             patch('base_connector.DiscoveryGenerator'), \
             patch('connector.StreamValidator'), \
             patch.object(Connector, '_load_config', return_value=cameras_config):

            connector = Connector(
                config_path="/tmp/test.json",
                instance_name="cameras_test"
            )

            device_config = cameras_config["devices"][0]
            command = {"ptz": {"pan": 90, "tilt": 45}}

            # Should not raise exception
            result = connector.set_device_state("camera1", device_config, command)

            # Currently returns True (stub implementation)
            assert result is True


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
