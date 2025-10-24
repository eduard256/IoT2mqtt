#!/usr/bin/env python3
"""
Unit tests for validate_stream.py
Tests ONVIF credential injection and stream validation logic
"""

import unittest
import json
import sys
from pathlib import Path
from urllib.parse import urlparse
from unittest.mock import patch, MagicMock

# Add parent directory to path to import validate_stream
sys.path.insert(0, str(Path(__file__).parent.parent / "actions"))

from validate_stream import parse_frame_rate, load_payload


class TestParseFrameRate(unittest.TestCase):
    """Test frame rate parsing function"""

    def test_parse_standard_frame_rate(self):
        """Test parsing standard frame rates like 30/1"""
        self.assertEqual(parse_frame_rate("30/1"), 30.0)
        self.assertEqual(parse_frame_rate("25/1"), 25.0)
        self.assertEqual(parse_frame_rate("60/1"), 60.0)

    def test_parse_ntsc_frame_rate(self):
        """Test parsing NTSC frame rate 30000/1001"""
        self.assertEqual(parse_frame_rate("30000/1001"), 29.97)

    def test_parse_direct_number(self):
        """Test parsing direct number without fraction"""
        self.assertEqual(parse_frame_rate("30"), 30.0)
        self.assertEqual(parse_frame_rate("25.5"), 25.5)

    def test_parse_invalid_input(self):
        """Test parsing invalid inputs returns 0.0"""
        self.assertEqual(parse_frame_rate(""), 0.0)
        self.assertEqual(parse_frame_rate(None), 0.0)
        self.assertEqual(parse_frame_rate("invalid"), 0.0)
        self.assertEqual(parse_frame_rate("30/0"), 0.0)  # Division by zero
        self.assertEqual(parse_frame_rate("abc/def"), 0.0)


class TestLoadPayload(unittest.TestCase):
    """Test payload loading from stdin"""

    @patch('sys.stdin')
    def test_load_simple_payload(self, mock_stdin):
        """Test loading simple JSON payload"""
        mock_stdin.read.return_value = '{"stream_url": "rtsp://test", "stream_type": "ONVIF"}'
        payload = load_payload()
        self.assertEqual(payload["stream_url"], "rtsp://test")
        self.assertEqual(payload["stream_type"], "ONVIF")

    @patch('sys.stdin')
    def test_load_nested_payload(self, mock_stdin):
        """Test loading nested payload with 'input' key"""
        mock_stdin.read.return_value = '{"input": {"stream_url": "rtsp://test", "username": "admin"}}'
        payload = load_payload()
        self.assertEqual(payload["stream_url"], "rtsp://test")
        self.assertEqual(payload["username"], "admin")

    @patch('sys.stdin')
    def test_load_empty_payload(self, mock_stdin):
        """Test loading empty payload returns empty dict"""
        mock_stdin.read.return_value = ''
        payload = load_payload()
        self.assertEqual(payload, {})

    @patch('sys.stdin')
    def test_load_invalid_json(self, mock_stdin):
        """Test loading invalid JSON returns empty dict"""
        mock_stdin.read.return_value = 'not valid json'
        payload = load_payload()
        self.assertEqual(payload, {})


class TestONVIFCredentialInjection(unittest.TestCase):
    """Test ONVIF credential injection logic"""

    def inject_credentials(self, stream_url, stream_type, username, password):
        """
        Replicate credential injection logic from validate_stream.py main()
        """
        parsed = urlparse(stream_url)
        protocol = parsed.scheme.lower()

        # For ONVIF streams: inject credentials if URL doesn't have them
        if stream_type == "ONVIF" and protocol == "rtsp":
            # Check if URL already has credentials
            if not parsed.username and not parsed.password:
                # URL has no credentials, but we have username/password - inject them
                if username and password:
                    # Rebuild URL with credentials
                    if parsed.port:
                        netloc_with_auth = f"{username}:{password}@{parsed.hostname}:{parsed.port}"
                    else:
                        netloc_with_auth = f"{username}:{password}@{parsed.hostname}"

                    parsed = parsed._replace(netloc=netloc_with_auth)
                    stream_url = parsed.geturl()

        return stream_url

    def test_onvif_rtsp_without_credentials_adds_them(self):
        """Test ONVIF RTSP stream without credentials gets credentials added"""
        original = "rtsp://10.0.20.111:554/live/main"
        result = self.inject_credentials(original, "ONVIF", "admin", "pass123")

        self.assertNotEqual(result, original)
        self.assertIn("admin:pass123", result)
        self.assertEqual(result, "rtsp://admin:pass123@10.0.20.111:554/live/main")

    def test_onvif_rtsp_standard_port_adds_credentials(self):
        """Test ONVIF RTSP without explicit port gets credentials added"""
        original = "rtsp://10.0.20.111/live/main"
        result = self.inject_credentials(original, "ONVIF", "admin", "pass123")

        self.assertNotEqual(result, original)
        self.assertIn("admin:pass123", result)
        self.assertEqual(result, "rtsp://admin:pass123@10.0.20.111/live/main")

    def test_onvif_rtsp_with_credentials_unchanged(self):
        """Test ONVIF RTSP stream with existing credentials is not modified"""
        original = "rtsp://existinguser:existingpass@10.0.20.111:554/live/main"
        result = self.inject_credentials(original, "ONVIF", "admin", "pass123")

        self.assertEqual(result, original)
        self.assertIn("existinguser:existingpass", result)

    def test_ffmpeg_rtsp_with_credentials_unchanged(self):
        """Test FFMPEG RTSP stream with credentials is not modified"""
        original = "rtsp://admin:pass123@10.0.20.111:554/live/main"
        result = self.inject_credentials(original, "FFMPEG", "admin", "pass123")

        self.assertEqual(result, original)

    def test_ffmpeg_rtsp_without_credentials_unchanged(self):
        """Test FFMPEG RTSP stream without credentials is not modified"""
        original = "rtsp://10.0.20.111:554/stream"
        result = self.inject_credentials(original, "FFMPEG", "admin", "pass123")

        self.assertEqual(result, original)

    def test_http_stream_unchanged(self):
        """Test HTTP stream is not modified"""
        original = "http://10.0.20.111/cgi-bin/snapshot.cgi?user=admin&pwd=pass"
        result = self.inject_credentials(original, "MJPEG", "admin", "pass123")

        self.assertEqual(result, original)

    def test_https_stream_unchanged(self):
        """Test HTTPS stream is not modified"""
        original = "https://10.0.20.111:443/image.jpg"
        result = self.inject_credentials(original, "JPEG", "admin", "pass123")

        self.assertEqual(result, original)

    def test_onvif_without_username_password_unchanged(self):
        """Test ONVIF stream without provided credentials is not modified"""
        original = "rtsp://10.0.20.111:554/live/main"
        result = self.inject_credentials(original, "ONVIF", "", "")

        self.assertEqual(result, original)

    def test_onvif_with_only_username_unchanged(self):
        """Test ONVIF stream with only username (no password) is not modified"""
        original = "rtsp://10.0.20.111:554/live/main"
        result = self.inject_credentials(original, "ONVIF", "admin", "")

        self.assertEqual(result, original)

    def test_onvif_with_only_password_unchanged(self):
        """Test ONVIF stream with only password (no username) is not modified"""
        original = "rtsp://10.0.20.111:554/live/main"
        result = self.inject_credentials(original, "ONVIF", "", "pass123")

        self.assertEqual(result, original)

    def test_special_characters_in_credentials(self):
        """Test ONVIF stream with special characters in credentials"""
        original = "rtsp://10.0.20.111:554/live/main"
        result = self.inject_credentials(original, "ONVIF", "admin@domain", "p@ss:123")

        self.assertIn("admin@domain:p@ss:123", result)


class TestStreamValidationIntegration(unittest.TestCase):
    """Integration tests for stream validation main logic"""

    @patch('validate_stream.validate_rtsp_stream')
    @patch('sys.stdin')
    @patch('builtins.print')
    def test_onvif_stream_validation_with_credential_injection(self, mock_print, mock_stdin, mock_validate_rtsp):
        """Test full ONVIF stream validation with credential injection"""
        # Mock input payload
        mock_stdin.read.return_value = json.dumps({
            "stream_url": "rtsp://10.0.20.111:554/live/main",
            "stream_type": "ONVIF",
            "username": "admin",
            "password": "pass123"
        })

        # Mock successful validation
        mock_validate_rtsp.return_value = {
            "ok": True,
            "result": {
                "stream_type": "RTSP",
                "video_codec": "h264",
                "resolution": "1920x1080",
                "fps": 30.0,
                "validated": True
            }
        }

        # Import and run main
        from validate_stream import main
        main()

        # Verify validate_rtsp_stream was called with credentials injected
        called_url = mock_validate_rtsp.call_args[0][0]
        self.assertIn("admin:pass123", called_url)
        self.assertEqual(called_url, "rtsp://admin:pass123@10.0.20.111:554/live/main")

    @patch('validate_stream.validate_rtsp_stream')
    @patch('sys.stdin')
    @patch('builtins.print')
    def test_ffmpeg_stream_validation_no_modification(self, mock_print, mock_stdin, mock_validate_rtsp):
        """Test FFMPEG stream validation without credential injection"""
        # Mock input payload with embedded credentials
        original_url = "rtsp://admin:pass123@10.0.20.111:554/live/main"
        mock_stdin.read.return_value = json.dumps({
            "stream_url": original_url,
            "stream_type": "FFMPEG",
            "username": "admin",
            "password": "pass123"
        })

        # Mock successful validation
        mock_validate_rtsp.return_value = {
            "ok": True,
            "result": {"validated": True}
        }

        # Import and run main
        from validate_stream import main
        main()

        # Verify URL was not modified
        called_url = mock_validate_rtsp.call_args[0][0]
        self.assertEqual(called_url, original_url)


if __name__ == '__main__':
    unittest.main()
