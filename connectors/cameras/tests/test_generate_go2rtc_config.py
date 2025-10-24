"""
Comprehensive tests for Go2RTCConfigGenerator

Tests cover:
1. Instance config loading
2. Port configuration from instance config and env
3. Credential injection into URLs
4. RTSP/FFMPEG stream source building
5. JPEG snapshot with FFmpeg exec
6. MJPEG stream support
7. HTTP stream support
8. ONVIF camera discovery
9. Authentication method detection
10. YAML config generation
11. URL sanitization for logging
12. Error handling and validation
"""

import pytest
import json
import yaml
import tempfile
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch, call
import sys

# Add cameras connector to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from generate_go2rtc_config import Go2RTCConfigGenerator


# ============================================================================
# Test Fixtures
# ============================================================================

@pytest.fixture
def temp_instance_config():
    """Create temporary instance config file"""
    config = {
        "instance_id": "cameras_test",
        "connector_type": "cameras",
        "ports": {
            "go2rtc_api": "1984",
            "go2rtc_rtsp": "8554",
            "go2rtc_webrtc": "8555",
            "go2rtc_homekit": "8443"
        },
        "devices": [
            {
                "device_id": "camera1",
                "name": "Front Door",
                "enabled": True,
                "stream_type": "FFMPEG",
                "stream_url": "rtsp://192.168.1.10:554/stream",
                "username": "admin",
                "password": "password123"
            },
            {
                "device_id": "camera2",
                "name": "Back Yard",
                "enabled": False,
                "stream_type": "FFMPEG",
                "stream_url": "rtsp://192.168.1.11:554/stream"
            }
        ]
    }

    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump(config, f)
        temp_path = f.name

    yield Path(temp_path)

    # Cleanup
    Path(temp_path).unlink()


# ============================================================================
# TIER 1 - CRITICAL TESTS: Initialization and Config Loading
# ============================================================================

class TestInitialization:
    """Test Go2RTCConfigGenerator initialization"""

    def test_initialization_with_instance_name(self, temp_instance_config, monkeypatch):
        """Should initialize with instance name and load config"""
        # Mock the config path
        monkeypatch.setattr('generate_go2rtc_config.Go2RTCConfigGenerator.load_instance_config',
                           lambda self: json.loads(temp_instance_config.read_text()))

        generator = Go2RTCConfigGenerator("cameras_test")

        assert generator.instance_name == "cameras_test"
        assert generator.config_path == "/app/instances/cameras_test.json"

    def test_port_configuration_from_instance_config(self, temp_instance_config, monkeypatch):
        """Should load ports from instance config"""
        config_data = json.loads(temp_instance_config.read_text())

        with patch.object(Go2RTCConfigGenerator, 'load_instance_config', return_value=config_data):
            generator = Go2RTCConfigGenerator("cameras_test")

            assert generator.api_port == "1984"
            assert generator.rtsp_port == "8554"
            assert generator.webrtc_port == "8555"
            assert generator.homekit_port == "8443"

    def test_port_configuration_from_env_fallback(self, monkeypatch):
        """Should fallback to env vars if ports not in instance config"""
        monkeypatch.setenv("GO2RTC_API_PORT", "2000")
        monkeypatch.setenv("GO2RTC_RTSP_PORT", "9000")

        config_data = {"instance_id": "test", "devices": []}

        with patch.object(Go2RTCConfigGenerator, 'load_instance_config', return_value=config_data):
            generator = Go2RTCConfigGenerator("test")

            assert generator.api_port == "2000"
            assert generator.rtsp_port == "9000"

    def test_load_instance_config_file_not_found(self):
        """Should raise FileNotFoundError if config doesn't exist"""
        config_data = {"instance_id": "test", "devices": []}

        with patch.object(Go2RTCConfigGenerator, 'load_instance_config', return_value=config_data):
            generator = Go2RTCConfigGenerator("nonexistent")

        # Now test load_instance_config directly
        generator.config_path = "/app/instances/nonexistent.json"

        with pytest.raises(FileNotFoundError, match="Instance config not found"):
            generator.load_instance_config()

    def test_load_instance_config_invalid_json(self, tmp_path):
        """Should raise JSONDecodeError for invalid JSON"""
        bad_config = tmp_path / "bad.json"
        bad_config.write_text("{ invalid json")

        config_data = {"instance_id": "test", "devices": []}

        with patch.object(Go2RTCConfigGenerator, 'load_instance_config', return_value=config_data):
            generator = Go2RTCConfigGenerator("test")

        # Now set bad config path and test
        generator.config_path = str(bad_config)

        with pytest.raises(json.JSONDecodeError):
            generator.load_instance_config()


# ============================================================================
# TIER 1 - CRITICAL TESTS: Credential Injection
# ============================================================================

class TestCredentialInjection:
    """Test credential injection into URLs"""

    def test_inject_credentials_into_rtsp_url(self):
        """Should inject credentials into RTSP URL"""
        config_data = {"instance_id": "test", "devices": []}

        with patch.object(Go2RTCConfigGenerator, 'load_instance_config', return_value=config_data):
            generator = Go2RTCConfigGenerator("test")

            url = "rtsp://192.168.1.10:554/stream"
            result = generator._inject_credentials(url, "admin", "pass123")

            assert result == "rtsp://admin:pass123@192.168.1.10:554/stream"

    def test_inject_credentials_into_http_url(self):
        """Should inject credentials into HTTP URL"""
        config_data = {"instance_id": "test", "devices": []}

        with patch.object(Go2RTCConfigGenerator, 'load_instance_config', return_value=config_data):
            generator = Go2RTCConfigGenerator("test")

            url = "http://192.168.1.10/snapshot.jpg"
            result = generator._inject_credentials(url, "user", "password")

            assert result == "http://user:password@192.168.1.10/snapshot.jpg"

    def test_dont_inject_if_credentials_already_present(self):
        """Should not inject if URL already has credentials"""
        config_data = {"instance_id": "test", "devices": []}

        with patch.object(Go2RTCConfigGenerator, 'load_instance_config', return_value=config_data):
            generator = Go2RTCConfigGenerator("test")

            url = "rtsp://existing:creds@192.168.1.10:554/stream"
            result = generator._inject_credentials(url, "new", "user")

            # Should keep existing credentials
            assert result == url

    def test_inject_credentials_with_query_params(self):
        """Should inject credentials preserving query parameters"""
        config_data = {"instance_id": "test", "devices": []}

        with patch.object(Go2RTCConfigGenerator, 'load_instance_config', return_value=config_data):
            generator = Go2RTCConfigGenerator("test")

            url = "http://192.168.1.10/snapshot.jpg?channel=1"
            result = generator._inject_credentials(url, "admin", "pass")

            assert result == "http://admin:pass@192.168.1.10/snapshot.jpg?channel=1"

    def test_inject_credentials_no_username(self):
        """Should return URL unchanged if no username"""
        config_data = {"instance_id": "test", "devices": []}

        with patch.object(Go2RTCConfigGenerator, 'load_instance_config', return_value=config_data):
            generator = Go2RTCConfigGenerator("test")

            url = "rtsp://192.168.1.10:554/stream"
            result = generator._inject_credentials(url, "", "password")

            assert result == url


# ============================================================================
# TIER 1 - CRITICAL TESTS: RTSP/FFMPEG Stream Source
# ============================================================================

class TestRTSPFFmpegSource:
    """Test RTSP/FFMPEG stream source building"""

    def test_build_rtsp_source_with_credentials(self):
        """Should build RTSP source with injected credentials"""
        config_data = {"instance_id": "test", "devices": []}

        with patch.object(Go2RTCConfigGenerator, 'load_instance_config', return_value=config_data):
            generator = Go2RTCConfigGenerator("test")

            device = {
                "device_id": "cam1",
                "stream_type": "FFMPEG",
                "stream_url": "rtsp://192.168.1.10:554/stream",
                "username": "admin",
                "password": "pass123"
            }

            result = generator.build_go2rtc_source(device)

            assert result == "rtsp://admin:pass123@192.168.1.10:554/stream"

    def test_build_rtsp_source_without_credentials(self):
        """Should build RTSP source without credentials if not provided"""
        config_data = {"instance_id": "test", "devices": []}

        with patch.object(Go2RTCConfigGenerator, 'load_instance_config', return_value=config_data):
            generator = Go2RTCConfigGenerator("test")

            device = {
                "device_id": "cam1",
                "stream_type": "FFMPEG",
                "stream_url": "rtsp://192.168.1.10:554/stream"
            }

            result = generator.build_go2rtc_source(device)

            assert result == "rtsp://192.168.1.10:554/stream"

    def test_build_rtmp_source(self):
        """Should support RTMP streams"""
        config_data = {"instance_id": "test", "devices": []}

        with patch.object(Go2RTCConfigGenerator, 'load_instance_config', return_value=config_data):
            generator = Go2RTCConfigGenerator("test")

            device = {
                "device_id": "cam1",
                "stream_type": "FFMPEG",
                "stream_url": "rtmp://192.168.1.10/live/stream",
                "username": "user",
                "password": "pass"
            }

            result = generator.build_go2rtc_source(device)

            assert result.startswith("rtmp://user:pass@")

    def test_rtsp_missing_stream_url(self):
        """Should return None if stream_url missing for FFMPEG type"""
        config_data = {"instance_id": "test", "devices": []}

        with patch.object(Go2RTCConfigGenerator, 'load_instance_config', return_value=config_data):
            generator = Go2RTCConfigGenerator("test")

            device = {
                "device_id": "cam1",
                "stream_type": "FFMPEG"
                # Missing stream_url
            }

            result = generator.build_go2rtc_source(device)

            assert result is None


# ============================================================================
# TIER 1 - CRITICAL TESTS: JPEG Snapshot with FFmpeg
# ============================================================================

class TestJPEGSnapshotFFmpeg:
    """Test JPEG snapshot stream with FFmpeg exec"""

    def test_build_jpeg_ffmpeg_source_basic(self):
        """Should build exec:ffmpeg source for JPEG"""
        config_data = {"instance_id": "test", "devices": []}

        with patch.object(Go2RTCConfigGenerator, 'load_instance_config', return_value=config_data), \
             patch.object(Go2RTCConfigGenerator, '_test_jpeg_url', return_value=True):

            generator = Go2RTCConfigGenerator("test")

            device = {
                "device_id": "cam1",
                "stream_type": "JPEG",
                "stream_url": "http://192.168.1.10/snapshot.jpg",
                "username": "admin",
                "password": "pass",
                "framerate": 5
            }

            result = generator.build_go2rtc_source(device)

            assert result.startswith("exec:ffmpeg")
            assert "-framerate 5" in result
            assert "-f mjpeg" in result
            assert "http://" in result

    def test_jpeg_ffmpeg_with_custom_framerate(self):
        """Should use custom framerate from device config"""
        config_data = {"instance_id": "test", "devices": []}

        with patch.object(Go2RTCConfigGenerator, 'load_instance_config', return_value=config_data), \
             patch.object(Go2RTCConfigGenerator, '_test_jpeg_url', return_value=True):

            generator = Go2RTCConfigGenerator("test")

            device = {
                "device_id": "cam1",
                "stream_type": "JPEG",
                "stream_url": "http://192.168.1.10/snapshot.jpg",
                "framerate": 10
            }

            result = generator.build_go2rtc_source(device)

            assert "-framerate 10" in result

    def test_jpeg_ffmpeg_default_framerate(self):
        """Should use default framerate of 5 if not specified"""
        config_data = {"instance_id": "test", "devices": []}

        with patch.object(Go2RTCConfigGenerator, 'load_instance_config', return_value=config_data), \
             patch.object(Go2RTCConfigGenerator, '_test_jpeg_url', return_value=True):

            generator = Go2RTCConfigGenerator("test")

            device = {
                "device_id": "cam1",
                "stream_type": "JPEG",
                "stream_url": "http://192.168.1.10/snapshot.jpg"
            }

            result = generator.build_go2rtc_source(device)

            assert "-framerate 5" in result

    def test_jpeg_auth_method_detection(self):
        """Should test multiple auth methods and use working one"""
        config_data = {"instance_id": "test", "devices": []}

        with patch.object(Go2RTCConfigGenerator, 'load_instance_config', return_value=config_data):
            generator = Go2RTCConfigGenerator("test")

            # Mock: basic_auth fails, query_params works
            def mock_test_url(url):
                if "admin:pass@" in url:
                    return False  # Basic auth doesn't work
                else:
                    return True   # Query params work

            with patch.object(generator, '_test_jpeg_url', side_effect=mock_test_url):
                device = {
                    "device_id": "cam1",
                    "stream_type": "JPEG",
                    "stream_url": "http://192.168.1.10/snapshot.jpg?user=admin&pwd=pass",
                    "username": "admin",
                    "password": "pass"
                }

                result = generator.build_go2rtc_source(device)

                # Should use URL without basic auth since that worked
                assert "exec:ffmpeg" in result
                assert result is not None


# ============================================================================
# TIER 1 - CRITICAL TESTS: MJPEG Stream Support
# ============================================================================

class TestMJPEGStream:
    """Test MJPEG stream support"""

    def test_build_mjpeg_source_with_credentials(self):
        """Should build MJPEG source with credentials"""
        config_data = {"instance_id": "test", "devices": []}

        with patch.object(Go2RTCConfigGenerator, 'load_instance_config', return_value=config_data):
            generator = Go2RTCConfigGenerator("test")

            device = {
                "device_id": "cam1",
                "stream_type": "MJPEG",
                "stream_url": "http://192.168.1.10/mjpeg",
                "username": "admin",
                "password": "pass123"
            }

            result = generator.build_go2rtc_source(device)

            assert result == "http://admin:pass123@192.168.1.10/mjpeg"

    def test_mjpeg_missing_stream_url(self):
        """Should return None if stream_url missing for MJPEG"""
        config_data = {"instance_id": "test", "devices": []}

        with patch.object(Go2RTCConfigGenerator, 'load_instance_config', return_value=config_data):
            generator = Go2RTCConfigGenerator("test")

            device = {
                "device_id": "cam1",
                "stream_type": "MJPEG"
            }

            result = generator.build_go2rtc_source(device)

            assert result is None


# ============================================================================
# TIER 1 - CRITICAL TESTS: HTTP Stream Support
# ============================================================================

class TestHTTPStream:
    """Test HTTP stream support (FLV, MPEG-TS)"""

    def test_build_http_stream_source(self):
        """Should build HTTP stream source"""
        config_data = {"instance_id": "test", "devices": []}

        with patch.object(Go2RTCConfigGenerator, 'load_instance_config', return_value=config_data):
            generator = Go2RTCConfigGenerator("test")

            device = {
                "device_id": "cam1",
                "stream_type": "HTTP",
                "stream_url": "http://192.168.1.10/stream.flv",
                "username": "user",
                "password": "pass"
            }

            result = generator.build_go2rtc_source(device)

            assert result == "http://user:pass@192.168.1.10/stream.flv"


# ============================================================================
# TIER 1 - CRITICAL TESTS: ONVIF Camera Discovery
# ============================================================================

class TestONVIFDiscovery:
    """Test ONVIF camera discovery"""

    def test_build_onvif_source_with_ip(self):
        """Should build ONVIF discovery URL from IP"""
        config_data = {"instance_id": "test", "devices": []}

        with patch.object(Go2RTCConfigGenerator, 'load_instance_config', return_value=config_data):
            generator = Go2RTCConfigGenerator("test")

            device = {
                "device_id": "cam1",
                "stream_type": "ONVIF",
                "ip": "192.168.1.10",
                "port": 80,
                "username": "admin",
                "password": "pass123"
            }

            result = generator.build_go2rtc_source(device)

            assert result == "onvif://admin:pass123@192.168.1.10:80"

    def test_onvif_with_concrete_stream_url(self):
        """Should prefer concrete stream_url over ONVIF discovery"""
        config_data = {"instance_id": "test", "devices": []}

        with patch.object(Go2RTCConfigGenerator, 'load_instance_config', return_value=config_data):
            generator = Go2RTCConfigGenerator("test")

            device = {
                "device_id": "cam1",
                "stream_type": "ONVIF",
                "stream_url": "rtsp://192.168.1.10:554/live/main",
                "username": "admin",
                "password": "pass",
                "ip": "192.168.1.10"
            }

            result = generator.build_go2rtc_source(device)

            # Should use concrete RTSP URL with credentials
            assert result == "rtsp://admin:pass@192.168.1.10:554/live/main"

    def test_onvif_missing_ip(self):
        """Should return None if IP missing for ONVIF without stream_url"""
        config_data = {"instance_id": "test", "devices": []}

        with patch.object(Go2RTCConfigGenerator, 'load_instance_config', return_value=config_data):
            generator = Go2RTCConfigGenerator("test")

            device = {
                "device_id": "cam1",
                "stream_type": "ONVIF",
                "username": "admin",
                "password": "pass"
            }

            result = generator.build_go2rtc_source(device)

            assert result is None

    def test_onvif_missing_username(self):
        """Should return None if username missing for ONVIF"""
        config_data = {"instance_id": "test", "devices": []}

        with patch.object(Go2RTCConfigGenerator, 'load_instance_config', return_value=config_data):
            generator = Go2RTCConfigGenerator("test")

            device = {
                "device_id": "cam1",
                "stream_type": "ONVIF",
                "ip": "192.168.1.10",
                "password": "pass"
            }

            result = generator.build_go2rtc_source(device)

            assert result is None


# ============================================================================
# TIER 1 - CRITICAL TESTS: Go2RTC Config Generation
# ============================================================================

class TestGo2RTCConfigGeneration:
    """Test complete go2rtc YAML config generation"""

    def test_generate_config_basic_structure(self):
        """Should generate config with correct structure"""
        config_data = {
            "instance_id": "cameras_test",
            "devices": []
        }

        with patch.object(Go2RTCConfigGenerator, 'load_instance_config', return_value=config_data):
            generator = Go2RTCConfigGenerator("cameras_test")

            result = generator.generate_go2rtc_config(config_data)

            assert 'log' in result
            assert 'api' in result
            assert 'rtsp' in result
            assert 'webrtc' in result
            assert 'srtp' in result
            assert 'streams' in result

    def test_generate_config_with_devices(self):
        """Should add enabled devices to streams"""
        config_data = {
            "instance_id": "cameras_test",
            "devices": [
                {
                    "device_id": "cam1",
                    "enabled": True,
                    "stream_type": "FFMPEG",
                    "stream_url": "rtsp://192.168.1.10/stream"
                },
                {
                    "device_id": "cam2",
                    "enabled": False,
                    "stream_type": "FFMPEG",
                    "stream_url": "rtsp://192.168.1.11/stream"
                }
            ]
        }

        with patch.object(Go2RTCConfigGenerator, 'load_instance_config', return_value=config_data):
            generator = Go2RTCConfigGenerator("cameras_test")

            result = generator.generate_go2rtc_config(config_data)

            # Only enabled device should be in streams
            assert 'cam1' in result['streams']
            assert 'cam2' not in result['streams']

    def test_generate_config_port_configuration(self):
        """Should configure correct ports in config"""
        config_data = {
            "instance_id": "cameras_test",
            "ports": {
                "go2rtc_api": "2000",
                "go2rtc_rtsp": "9000"
            },
            "devices": []
        }

        with patch.object(Go2RTCConfigGenerator, 'load_instance_config', return_value=config_data):
            generator = Go2RTCConfigGenerator("cameras_test")

            result = generator.generate_go2rtc_config(config_data)

            assert result['api']['listen'] == ":2000"
            assert result['rtsp']['listen'] == ":9000"

    def test_generate_config_stream_array_format(self):
        """Should format streams as arrays"""
        config_data = {
            "instance_id": "cameras_test",
            "devices": [
                {
                    "device_id": "cam1",
                    "enabled": True,
                    "stream_type": "FFMPEG",
                    "stream_url": "rtsp://192.168.1.10/stream"
                }
            ]
        }

        with patch.object(Go2RTCConfigGenerator, 'load_instance_config', return_value=config_data):
            generator = Go2RTCConfigGenerator("cameras_test")

            result = generator.generate_go2rtc_config(config_data)

            # Stream should be array with source URL
            assert isinstance(result['streams']['cam1'], list)
            assert len(result['streams']['cam1']) == 1


# ============================================================================
# TIER 1 - CRITICAL TESTS: URL Sanitization
# ============================================================================

class TestURLSanitization:
    """Test URL sanitization for safe logging"""

    def test_sanitize_rtsp_url_with_credentials(self):
        """Should replace credentials in RTSP URL"""
        url = "rtsp://admin:password123@192.168.1.10:554/stream"
        result = Go2RTCConfigGenerator._sanitize_url(url)

        assert result == "rtsp://***:***@192.168.1.10:554/stream"
        assert "admin" not in result
        assert "password123" not in result

    def test_sanitize_http_url_with_credentials(self):
        """Should replace credentials in HTTP URL"""
        url = "http://user:pass@192.168.1.10/snapshot.jpg"
        result = Go2RTCConfigGenerator._sanitize_url(url)

        assert result == "http://***:***@192.168.1.10/snapshot.jpg"

    def test_sanitize_onvif_url(self):
        """Should replace credentials in ONVIF URL"""
        url = "onvif://admin:secret@192.168.1.10:80"
        result = Go2RTCConfigGenerator._sanitize_url(url)

        assert result == "onvif://***:***@192.168.1.10:80"

    def test_sanitize_exec_ffmpeg_command(self):
        """Should replace credentials in exec:ffmpeg command"""
        url = "exec:ffmpeg -i http://admin:pass@192.168.1.10/snapshot.jpg -f mjpeg -"
        result = Go2RTCConfigGenerator._sanitize_url(url)

        assert "admin" not in result
        assert "pass" not in result
        assert "***:***@" in result

    def test_sanitize_url_without_credentials(self):
        """Should not modify URL without credentials"""
        url = "rtsp://192.168.1.10:554/stream"
        result = Go2RTCConfigGenerator._sanitize_url(url)

        assert result == url


# ============================================================================
# TIER 1 - CRITICAL TESTS: YAML File Writing
# ============================================================================

class TestYAMLWriting:
    """Test YAML config file writing"""

    def test_write_config_to_file(self, tmp_path):
        """Should write config to YAML file"""
        config_data = {"instance_id": "test", "devices": []}

        with patch.object(Go2RTCConfigGenerator, 'load_instance_config', return_value=config_data):
            generator = Go2RTCConfigGenerator("test")

            output_file = tmp_path / "go2rtc.yaml"

            config = {
                "log": {"level": "info"},
                "api": {"listen": ":1984"},
                "streams": {
                    "cam1": ["rtsp://192.168.1.10/stream"]
                }
            }

            generator.write_config(config, str(output_file))

            # Verify file was created
            assert output_file.exists()

            # Verify content is valid YAML
            with open(output_file) as f:
                loaded = yaml.safe_load(f)

            assert loaded['log']['level'] == "info"
            assert loaded['streams']['cam1'][0] == "rtsp://192.168.1.10/stream"


# ============================================================================
# TIER 1 - CRITICAL TESTS: Error Handling
# ============================================================================

class TestErrorHandling:
    """Test error handling and edge cases"""

    def test_unknown_stream_type_fallback(self):
        """Should use stream_url as-is for unknown stream type"""
        config_data = {"instance_id": "test", "devices": []}

        with patch.object(Go2RTCConfigGenerator, 'load_instance_config', return_value=config_data):
            generator = Go2RTCConfigGenerator("test")

            device = {
                "device_id": "cam1",
                "stream_type": "UNKNOWN_TYPE",
                "stream_url": "custom://192.168.1.10/stream"
            }

            result = generator.build_go2rtc_source(device)

            assert result == "custom://192.168.1.10/stream"

    def test_device_without_stream_url_and_unknown_type(self):
        """Should return None for unknown type without stream_url"""
        config_data = {"instance_id": "test", "devices": []}

        with patch.object(Go2RTCConfigGenerator, 'load_instance_config', return_value=config_data):
            generator = Go2RTCConfigGenerator("test")

            device = {
                "device_id": "cam1",
                "stream_type": "UNKNOWN_TYPE"
            }

            result = generator.build_go2rtc_source(device)

            assert result is None

    def test_config_generation_with_invalid_device(self):
        """Should skip devices that fail source building"""
        config_data = {
            "instance_id": "cameras_test",
            "devices": [
                {
                    "device_id": "good_cam",
                    "enabled": True,
                    "stream_type": "FFMPEG",
                    "stream_url": "rtsp://192.168.1.10/stream"
                },
                {
                    "device_id": "bad_cam",
                    "enabled": True,
                    "stream_type": "FFMPEG"
                    # Missing stream_url
                }
            ]
        }

        with patch.object(Go2RTCConfigGenerator, 'load_instance_config', return_value=config_data):
            generator = Go2RTCConfigGenerator("cameras_test")

            result = generator.generate_go2rtc_config(config_data)

            # Only good_cam should be in streams
            assert 'good_cam' in result['streams']
            assert 'bad_cam' not in result['streams']


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
