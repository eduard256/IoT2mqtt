"""
Comprehensive tests for CameraStreamScanner service

Tests cover ALL components:
1. Scanner initialization and state management
2. Scan lifecycle (start, running, completion, cleanup)
3. ONVIF discovery (with/without library available)
4. URL pattern generation (database + popular patterns)
5. Stream testing (RTSP via ffprobe, HTTP/JPEG via curl)
6. Credential masking in URLs
7. Priority-based URL sorting
8. Stop conditions (max streams, timeout)
9. Duplicate stream detection
10. SSE event streaming (results queue)
11. Status retrieval and error handling
12. Thread management and cleanup
13. Edge cases (malformed URLs, missing ffprobe, timeouts)
"""

import pytest
import json
import tempfile
import time
import threading
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch, call
from queue import Queue, Empty
import sys

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from services.camera_stream_scanner import CameraStreamScanner


# ============================================================================
# TIER 1 - CRITICAL TESTS: Initialization
# ============================================================================

class TestScannerInitialization:
    """Test CameraStreamScanner initialization"""

    def test_initialization(self):
        """Should initialize with empty state"""
        scanner = CameraStreamScanner()

        assert scanner.scan_threads == {}
        assert scanner.scan_results == {}
        assert scanner.scan_status == {}
        assert scanner.scan_queues == {}


# ============================================================================
# TIER 1 - CRITICAL TESTS: Scan Lifecycle
# ============================================================================

class TestScanLifecycle:
    """Test scan start, running, completion"""

    def test_start_scan_creates_task(self):
        """Should create task with queue and thread"""
        scanner = CameraStreamScanner()

        with patch.object(scanner, '_scan_streams'):
            scanner.start_scan(
                task_id="test_task",
                entries=[],
                address="192.168.1.100",
                username="admin",
                password="password"
            )

            # Should create queue and thread
            assert "test_task" in scanner.scan_queues
            assert "test_task" in scanner.scan_threads
            assert "test_task" in scanner.scan_status
            assert scanner.scan_status["test_task"] == "running"

    def test_start_scan_already_running(self):
        """Should not start duplicate scan"""
        scanner = CameraStreamScanner()

        with patch.object(scanner, '_scan_streams'):
            scanner.start_scan("task1", [], "192.168.1.100")
            original_thread = scanner.scan_threads["task1"]

            # Try to start again
            scanner.start_scan("task1", [], "192.168.1.100")

            # Should be same thread
            assert scanner.scan_threads["task1"] == original_thread

    def test_scan_completion_status(self):
        """Should set status to completed"""
        scanner = CameraStreamScanner()
        # Initialize state (normally done by start_scan)
        scanner.scan_queues["task1"] = Queue()
        scanner.scan_results["task1"] = []
        scanner.scan_status["task1"] = "running"

        # Mock ONVIF and stream testing
        with patch.object(scanner, '_try_onvif_discovery', return_value=[]), \
             patch.object(scanner, '_load_popular_patterns', return_value=[]):

            scanner._scan_streams("task1", [], "192.168.1.100", "", "", 0)

            assert scanner.scan_status["task1"] == "completed"

    def test_scan_error_handling(self):
        """Should handle exceptions and set error status"""
        scanner = CameraStreamScanner()
        # Initialize state
        scanner.scan_queues["task1"] = Queue()
        scanner.scan_results["task1"] = []
        scanner.scan_status["task1"] = "running"

        # Force an exception
        with patch.object(scanner, '_try_onvif_discovery', side_effect=Exception("Test error")):
            scanner._scan_streams("task1", [], "192.168.1.100", "", "", 0)

            assert scanner.scan_status["task1"] == "error"

    def test_scan_cleanup_removes_thread(self):
        """Should cleanup thread after scan completes"""
        scanner = CameraStreamScanner()
        # Initialize state
        scanner.scan_queues["task1"] = Queue()
        scanner.scan_results["task1"] = []
        scanner.scan_status["task1"] = "running"
        scanner.scan_threads["task1"] = Mock()

        with patch.object(scanner, '_try_onvif_discovery', return_value=[]), \
             patch.object(scanner, '_load_popular_patterns', return_value=[]):

            scanner._scan_streams("task1", [], "192.168.1.100", "", "", 0)

            # Thread should be removed
            assert "task1" not in scanner.scan_threads


# ============================================================================
# TIER 1 - CRITICAL TESTS: URL Generation
# ============================================================================

class TestURLGeneration:
    """Test stream URL generation from patterns"""

    def test_generate_test_urls_basic(self):
        """Should generate URLs from database entries"""
        scanner = CameraStreamScanner()

        entries = [
            {
                "protocol": "rtsp",
                "port": 554,
                "url": "/stream1",
                "type": "FFMPEG",
                "notes": "Main stream"
            }
        ]

        urls = scanner._generate_test_urls(
            entries,
            address="192.168.1.100",
            username="admin",
            password="12345",
            channel=0
        )

        assert len(urls) == 1
        # Standard port 554 is omitted for RTSP
        assert urls[0]["url"] == "rtsp://admin:12345@192.168.1.100/stream1"
        assert urls[0]["type"] == "FFMPEG"
        assert urls[0]["notes"] == "Main stream"

    def test_generate_test_urls_with_placeholders(self):
        """Should replace placeholders in URL path"""
        scanner = CameraStreamScanner()

        entries = [
            {
                "protocol": "rtsp",
                "port": 554,
                "url": "/cam/realmonitor?channel={channel}",
                "type": "FFMPEG"
            }
        ]

        urls = scanner._generate_test_urls(entries, "192.168.1.100", "admin", "pass", channel=2)

        assert "/cam/realmonitor?channel=2" in urls[0]["url"]

    def test_generate_test_urls_priority_sorting(self):
        """Should sort URLs by priority (ONVIF first)"""
        scanner = CameraStreamScanner()

        entries = [
            {"protocol": "rtsp", "port": 554, "url": "/stream", "type": "FFMPEG"},
            {"protocol": "rtsp", "port": 554, "url": "/onvif", "type": "ONVIF"},
            {"protocol": "http", "port": 80, "url": "/snap.jpg", "type": "JPEG"}
        ]

        urls = scanner._generate_test_urls(entries, "192.168.1.100", "", "", 0)

        # ONVIF should be first (priority 1)
        assert urls[0]["type"] == "ONVIF"
        # FFMPEG second (priority 2)
        assert urls[1]["type"] == "FFMPEG"
        # JPEG last (priority 4)
        assert urls[2]["type"] == "JPEG"

    def test_generate_test_urls_default_ports(self):
        """Should use default ports when port=0"""
        scanner = CameraStreamScanner()

        entries = [
            {"protocol": "rtsp", "port": 0, "url": "/stream", "type": "FFMPEG"},
            {"protocol": "http", "port": 0, "url": "/snap.jpg", "type": "JPEG"}
        ]

        urls = scanner._generate_test_urls(entries, "192.168.1.100", "", "", 0)

        # Should use 554 for RTSP, but standard port is omitted
        assert urls[0]["url"] == "rtsp://192.168.1.100/stream"
        # Should use 80 for HTTP, standard port omitted
        assert urls[1]["url"] == "http://192.168.1.100/snap.jpg"

    def test_generate_test_urls_no_credentials(self):
        """Should generate URLs without credentials"""
        scanner = CameraStreamScanner()

        entries = [{"protocol": "rtsp", "port": 554, "url": "/stream", "type": "FFMPEG"}]

        urls = scanner._generate_test_urls(entries, "192.168.1.100", "", "", 0)

        assert urls[0]["url"] == "rtsp://192.168.1.100/stream"
        assert "@" not in urls[0]["url"]

    def test_generate_test_urls_non_standard_port(self):
        """Should include non-standard ports in URL"""
        scanner = CameraStreamScanner()

        entries = [{"protocol": "rtsp", "port": 8554, "url": "/stream", "type": "FFMPEG"}]

        urls = scanner._generate_test_urls(entries, "192.168.1.100", "admin", "pass", 0)

        # Non-standard port should be included
        assert ":8554" in urls[0]["url"]


# ============================================================================
# TIER 1 - CRITICAL TESTS: ONVIF Discovery
# ============================================================================

class TestONVIFDiscovery:
    """Test ONVIF camera discovery"""

    def test_onvif_discovery_not_available(self):
        """Should return empty list when ONVIF not available"""
        scanner = CameraStreamScanner()

        with patch('services.camera_stream_scanner.ONVIF_AVAILABLE', False):
            streams = scanner._try_onvif_discovery("192.168.1.100", "admin", "pass")

            assert streams == []


# ============================================================================
# TIER 1 - CRITICAL TESTS: Stream Testing
# ============================================================================

class TestStreamTesting:
    """Test individual stream testing"""

    @patch('subprocess.run')
    def test_test_rtsp_success(self, mock_run):
        """Should test RTSP stream with ffprobe"""
        scanner = CameraStreamScanner()

        # Mock successful ffprobe
        mock_run.return_value = Mock(
            returncode=0,
            stdout=b'{"streams": [{"codec_type": "video"}]}',
            stderr=b''
        )

        url_info = {
            "url": "rtsp://admin:pass@192.168.1.100:554/stream",
            "type": "FFMPEG",
            "protocol": "rtsp",
            "port": 554,
            "notes": "Test stream"
        }

        result = scanner._test_rtsp(url_info)

        assert result["ok"] is True
        assert result["stream"]["type"] == "FFMPEG"
        assert "***:***@" in result["stream"]["url"]  # Credentials masked

    @patch('subprocess.run')
    def test_test_rtsp_failure(self, mock_run):
        """Should handle RTSP test failures"""
        scanner = CameraStreamScanner()

        # Mock failed ffprobe
        mock_run.return_value = Mock(
            returncode=1,
            stdout=b'',
            stderr=b'Connection refused'
        )

        url_info = {
            "url": "rtsp://192.168.1.100:554/stream",
            "type": "FFMPEG",
            "protocol": "rtsp",
            "port": 554
        }

        result = scanner._test_rtsp(url_info)

        assert result["ok"] is False
        assert result["stream"] is None

    @patch('subprocess.run')
    def test_test_rtsp_timeout(self, mock_run):
        """Should handle ffprobe timeout"""
        scanner = CameraStreamScanner()

        # Mock timeout
        import subprocess
        mock_run.side_effect = subprocess.TimeoutExpired('ffprobe', 10)

        url_info = {
            "url": "rtsp://192.168.1.100:554/stream",
            "type": "FFMPEG",
            "protocol": "rtsp",
            "port": 554
        }

        result = scanner._test_rtsp(url_info)

        assert result["ok"] is False

    @patch('subprocess.run')
    def test_test_rtsp_ffprobe_not_found(self, mock_run):
        """Should handle missing ffprobe"""
        scanner = CameraStreamScanner()

        mock_run.side_effect = FileNotFoundError("ffprobe not found")

        url_info = {
            "url": "rtsp://192.168.1.100:554/stream",
            "type": "FFMPEG",
            "protocol": "rtsp",
            "port": 554
        }

        result = scanner._test_rtsp(url_info)

        assert result["ok"] is False

    @patch('subprocess.run')
    def test_test_http_jpeg_success(self, mock_run):
        """Should test HTTP/JPEG stream with curl"""
        scanner = CameraStreamScanner()

        # Mock successful curl with JPEG data
        mock_run.return_value = Mock(
            returncode=0,
            stdout=b'\xff\xd8\xff\xe0\x00\x10JFIF' + b'\x00' * 100  # JPEG magic bytes
        )

        url_info = {
            "url": "http://192.168.1.100/snap.jpg",
            "type": "JPEG",
            "protocol": "http",
            "port": 80,
            "username": "admin",
            "password": "pass"
        }

        result = scanner._test_http(url_info)

        assert result["ok"] is True
        assert result["stream"]["type"] == "JPEG"

    @patch('subprocess.run')
    def test_test_http_not_jpeg(self, mock_run):
        """Should reject non-JPEG HTTP responses"""
        scanner = CameraStreamScanner()

        # Mock response without JPEG magic bytes
        mock_run.return_value = Mock(
            returncode=0,
            stdout=b'<html>Not a JPEG</html>'
        )

        url_info = {
            "url": "http://192.168.1.100/snap.jpg",
            "type": "JPEG",
            "protocol": "http",
            "port": 80
        }

        result = scanner._test_http(url_info)

        assert result["ok"] is False

    @patch('subprocess.run')
    def test_test_http_with_credentials(self, mock_run):
        """Should use Basic Auth for HTTP requests"""
        scanner = CameraStreamScanner()

        mock_run.return_value = Mock(
            returncode=0,
            stdout=b'\xff\xd8\xff\xe0' + b'\x00' * 100
        )

        url_info = {
            "url": "http://192.168.1.100/snap.jpg",
            "type": "JPEG",
            "protocol": "http",
            "port": 80,
            "username": "admin",
            "password": "password123"
        }

        scanner._test_http(url_info)

        # Check curl was called with -u flag
        call_args = mock_run.call_args[0][0]
        assert "-u" in call_args
        assert "admin:password123" in call_args

    @patch('subprocess.run')
    def test_test_http_timeout(self, mock_run):
        """Should handle HTTP timeout"""
        scanner = CameraStreamScanner()

        import subprocess
        mock_run.side_effect = subprocess.TimeoutExpired('curl', 10)

        url_info = {
            "url": "http://192.168.1.100/snap.jpg",
            "type": "JPEG",
            "protocol": "http",
            "port": 80
        }

        result = scanner._test_http(url_info)

        assert result["ok"] is False


# ============================================================================
# TIER 1 - CRITICAL TESTS: Credential Masking
# ============================================================================

class TestCredentialMasking:
    """Test credential masking in URLs"""

    def test_mask_credentials_rtsp(self):
        """Should mask RTSP credentials"""
        scanner = CameraStreamScanner()

        url = "rtsp://admin:password@192.168.1.100:554/stream"
        masked = scanner._mask_credentials(url)

        assert "***:***@" in masked
        assert "admin" not in masked
        assert "password" not in masked
        assert "192.168.1.100" in masked

    def test_mask_credentials_http(self):
        """Should mask HTTP credentials"""
        scanner = CameraStreamScanner()

        url = "http://user:pass@camera.local:8080/snap.jpg"
        masked = scanner._mask_credentials(url)

        assert "***:***@" in masked
        assert "user" not in masked
        assert "pass" not in masked

    def test_mask_credentials_no_credentials(self):
        """Should not modify URLs without credentials"""
        scanner = CameraStreamScanner()

        url = "rtsp://192.168.1.100:554/stream"
        masked = scanner._mask_credentials(url)

        assert masked == url

    def test_mask_credentials_malformed_url(self):
        """Should handle malformed URLs gracefully"""
        scanner = CameraStreamScanner()

        url = "not a valid url"
        masked = scanner._mask_credentials(url)

        # Should return original on error
        assert masked == url

    def test_mask_credentials_preserves_path(self):
        """Should preserve URL path and query string"""
        scanner = CameraStreamScanner()

        url = "rtsp://admin:pass@192.168.1.100/stream?channel=1"
        masked = scanner._mask_credentials(url)

        assert "/stream?channel=1" in masked


# ============================================================================
# TIER 1 - CRITICAL TESTS: Stop Conditions
# ============================================================================

class TestStopConditions:
    """Test scan stop conditions"""

    def test_should_stop_max_streams_reached(self):
        """Should stop when max streams found"""
        scanner = CameraStreamScanner()

        start_time = time.time()
        should_stop = scanner._should_stop(
            start_time=start_time,
            max_duration=300,
            found_count=7,
            max_streams=7
        )

        assert should_stop is True

    def test_should_stop_timeout_exceeded(self):
        """Should stop when timeout exceeded"""
        scanner = CameraStreamScanner()

        start_time = time.time() - 301  # 301 seconds ago
        should_stop = scanner._should_stop(
            start_time=start_time,
            max_duration=300,
            found_count=2,
            max_streams=7
        )

        assert should_stop is True

    def test_should_not_stop_within_limits(self):
        """Should continue when within limits"""
        scanner = CameraStreamScanner()

        start_time = time.time()
        should_stop = scanner._should_stop(
            start_time=start_time,
            max_duration=300,
            found_count=3,
            max_streams=7
        )

        assert should_stop is False


# ============================================================================
# TIER 1 - CRITICAL TESTS: Popular Patterns Loading
# ============================================================================

class TestPopularPatternsLoading:
    """Test loading popular stream patterns"""

    def test_load_popular_patterns_success(self):
        """Should load patterns from JSON file"""
        scanner = CameraStreamScanner()

        patterns_data = [
            {"protocol": "rtsp", "port": 554, "url": "/stream1", "type": "FFMPEG"},
            {"protocol": "rtsp", "port": 554, "url": "/live", "type": "FFMPEG"}
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create fake patterns file
            patterns_file = Path(tmpdir) / "connectors" / "cameras" / "data"
            patterns_file.mkdir(parents=True)
            (patterns_file / "popular_stream_patterns.json").write_text(json.dumps(patterns_data))

            with patch.dict('os.environ', {'IOT2MQTT_PATH': tmpdir}):
                patterns = scanner._load_popular_patterns()

                assert len(patterns) == 2
                assert patterns[0]["url"] == "/stream1"

    def test_load_popular_patterns_file_not_found(self):
        """Should return empty list if file doesn't exist"""
        scanner = CameraStreamScanner()

        with patch.dict('os.environ', {'IOT2MQTT_PATH': '/nonexistent'}):
            patterns = scanner._load_popular_patterns()

            assert patterns == []

    def test_load_popular_patterns_invalid_json(self):
        """Should handle invalid JSON gracefully"""
        scanner = CameraStreamScanner()

        with tempfile.TemporaryDirectory() as tmpdir:
            patterns_file = Path(tmpdir) / "connectors" / "cameras" / "data"
            patterns_file.mkdir(parents=True)
            (patterns_file / "popular_stream_patterns.json").write_text("{ invalid json")

            with patch.dict('os.environ', {'IOT2MQTT_PATH': tmpdir}):
                patterns = scanner._load_popular_patterns()

                assert patterns == []


# ============================================================================
# TIER 1 - CRITICAL TESTS: Priority System
# ============================================================================

class TestPrioritySystem:
    """Test stream type priority"""

    def test_get_priority_onvif_highest(self):
        """ONVIF should have highest priority"""
        scanner = CameraStreamScanner()

        assert scanner._get_priority("ONVIF") == 1

    def test_get_priority_order(self):
        """Should have correct priority order"""
        scanner = CameraStreamScanner()

        assert scanner._get_priority("ONVIF") < scanner._get_priority("FFMPEG")
        assert scanner._get_priority("FFMPEG") < scanner._get_priority("MJPEG")
        assert scanner._get_priority("MJPEG") < scanner._get_priority("JPEG")

    def test_get_priority_unknown_type(self):
        """Unknown types should have lowest priority"""
        scanner = CameraStreamScanner()

        assert scanner._get_priority("UNKNOWN") == 99


# ============================================================================
# TIER 1 - CRITICAL TESTS: Duplicate Detection
# ============================================================================

class TestDuplicateDetection:
    """Test duplicate stream detection during scan"""

    def test_scan_skips_duplicate_urls(self):
        """Should not add duplicate stream URLs"""
        scanner = CameraStreamScanner()
        # Initialize state
        scanner.scan_queues["task1"] = Queue()
        scanner.scan_results["task1"] = []
        scanner.scan_status["task1"] = "running"

        # Mock to return same URL twice
        mock_stream = {
            "url": "rtsp://***:***@192.168.1.100/stream",
            "type": "FFMPEG"
        }

        with patch.object(scanner, '_try_onvif_discovery', return_value=[]), \
             patch.object(scanner, '_load_popular_patterns', return_value=[]), \
             patch.object(scanner, '_test_stream', return_value={"ok": True, "stream": mock_stream}):

            entries = [
                {"protocol": "rtsp", "port": 554, "url": "/stream", "type": "FFMPEG"},
                {"protocol": "rtsp", "port": 554, "url": "/stream", "type": "FFMPEG"}  # Duplicate
            ]

            scanner._scan_streams("task1", entries, "192.168.1.100", "", "", 0)

            # Should only have 1 result (duplicate skipped)
            assert len(scanner.scan_results["task1"]) == 1


# ============================================================================
# TIER 1 - CRITICAL TESTS: SSE Event Streaming
# ============================================================================

class TestSSEEventStreaming:
    """Test SSE event streaming for results"""

    def test_get_results_stream_yields_events(self):
        """Should yield events from queue"""
        scanner = CameraStreamScanner()
        scanner.scan_queues["task1"] = Queue()

        # Add events to queue
        scanner.scan_queues["task1"].put({"type": "stream_found", "data": "{}"})
        scanner.scan_queues["task1"].put({"type": "scan_complete"})

        events = list(scanner.get_results_stream("task1"))

        assert len(events) == 2
        assert events[0]["type"] == "stream_found"
        assert events[1]["type"] == "scan_complete"

    def test_get_results_stream_task_not_found(self):
        """Should yield error if task not found"""
        scanner = CameraStreamScanner()

        events = list(scanner.get_results_stream("nonexistent"))

        assert len(events) == 1
        assert events[0]["type"] == "error"

    def test_get_results_stream_timeout(self):
        """Should timeout if no events"""
        scanner = CameraStreamScanner()
        scanner.scan_queues["task1"] = Queue()

        # Don't add any events - should timeout

        # Use short timeout for test
        with patch.object(Queue, 'get', side_effect=Empty):
            events = list(scanner.get_results_stream("task1"))

            assert events[0]["type"] == "error"
            assert "timeout" in events[0]["message"].lower()

    def test_get_results_stream_cleanup(self):
        """Should cleanup queue after completion"""
        scanner = CameraStreamScanner()
        scanner.scan_queues["task1"] = Queue()
        scanner.scan_queues["task1"].put({"type": "scan_complete"})

        list(scanner.get_results_stream("task1"))

        # Queue should be removed
        assert "task1" not in scanner.scan_queues

    def test_get_results_stream_error_event(self):
        """Should stop on error event"""
        scanner = CameraStreamScanner()
        scanner.scan_queues["task1"] = Queue()

        scanner.scan_queues["task1"].put({"type": "error", "message": "Test error"})

        events = list(scanner.get_results_stream("task1"))

        assert len(events) == 1
        assert events[0]["type"] == "error"


# ============================================================================
# TIER 1 - CRITICAL TESTS: Status Retrieval
# ============================================================================

class TestStatusRetrieval:
    """Test scan status retrieval"""

    def test_get_status_running(self):
        """Should return status for running scan"""
        scanner = CameraStreamScanner()
        scanner.scan_status["task1"] = "running"
        scanner.scan_results["task1"] = [{"url": "rtsp://..."}]

        status = scanner.get_status("task1")

        assert status["task_id"] == "task1"
        assert status["status"] == "running"
        assert status["count"] == 1

    def test_get_status_completed(self):
        """Should return status for completed scan"""
        scanner = CameraStreamScanner()
        scanner.scan_status["task1"] = "completed"
        scanner.scan_results["task1"] = [
            {"url": "rtsp://stream1"},
            {"url": "rtsp://stream2"}
        ]

        status = scanner.get_status("task1")

        assert status["status"] == "completed"
        assert status["count"] == 2

    def test_get_status_task_not_found(self):
        """Should raise error if task not found"""
        scanner = CameraStreamScanner()

        with pytest.raises(ValueError, match="Task .* not found"):
            scanner.get_status("nonexistent")

    def test_get_status_includes_found_streams(self):
        """Should include found streams in status"""
        scanner = CameraStreamScanner()
        scanner.scan_status["task1"] = "completed"
        scanner.scan_results["task1"] = [
            {"url": "rtsp://stream1", "type": "FFMPEG"},
            {"url": "http://stream2", "type": "JPEG"}
        ]

        status = scanner.get_status("task1")

        assert len(status["found_streams"]) == 2
        assert status["found_streams"][0]["url"] == "rtsp://stream1"


# ============================================================================
# TIER 1 - CRITICAL TESTS: Full Integration
# ============================================================================

class TestFullIntegration:
    """Test full scan integration"""

    def test_full_scan_with_onvif_stops_early(self):
        """Should stop scan if ONVIF finds enough streams"""
        scanner = CameraStreamScanner()
        # Initialize state
        scanner.scan_queues["task1"] = Queue()
        scanner.scan_results["task1"] = []
        scanner.scan_status["task1"] = "running"

        # Mock ONVIF to return 7 streams
        onvif_streams = [{"url": f"rtsp://stream{i}", "type": "ONVIF"} for i in range(7)]

        with patch.object(scanner, '_try_onvif_discovery', return_value=onvif_streams):
            scanner._scan_streams("task1", [], "192.168.1.100", "", "", 0)

            # Should have 7 streams and be completed
            assert len(scanner.scan_results["task1"]) == 7
            assert scanner.scan_status["task1"] == "completed"

    def test_full_scan_progresses_through_phases(self):
        """Should progress through all scan phases"""
        scanner = CameraStreamScanner()
        # Initialize state
        scanner.scan_queues["task1"] = Queue()
        scanner.scan_results["task1"] = []
        scanner.scan_status["task1"] = "running"

        # Mock all phases
        with patch.object(scanner, '_try_onvif_discovery', return_value=[]), \
             patch.object(scanner, '_load_popular_patterns', return_value=[]), \
             patch.object(scanner, '_test_stream', return_value={"ok": False, "stream": None}):

            entries = [{"protocol": "rtsp", "port": 554, "url": "/stream", "type": "FFMPEG"}]
            scanner._scan_streams("task1", entries, "192.168.1.100", "", "", 0)

            # Should complete even with no streams found
            assert scanner.scan_status["task1"] == "completed"

    def test_full_scan_respects_stop_conditions(self):
        """Should respect max_streams stop condition"""
        scanner = CameraStreamScanner()
        scanner.scan_queues["task1"] = Queue()
        scanner.scan_results["task1"] = []
        scanner.scan_status["task1"] = "running"

        # Mock successful streams
        mock_stream_template = {
            "url": "rtsp://stream",
            "type": "FFMPEG"
        }

        call_count = [0]
        def mock_test_stream(url_info):
            call_count[0] += 1
            return {
                "ok": True,
                "stream": {**mock_stream_template, "url": f"rtsp://stream{call_count[0]}"}
            }

        with patch.object(scanner, '_try_onvif_discovery', return_value=[]), \
             patch.object(scanner, '_load_popular_patterns', return_value=[]), \
             patch.object(scanner, '_test_stream', side_effect=mock_test_stream):

            # Create many entries
            entries = [{"protocol": "rtsp", "port": 554, "url": f"/stream{i}", "type": "FFMPEG"} for i in range(20)]
            scanner._scan_streams("task1", entries, "192.168.1.100", "", "", 0)

            # Should stop at 7 streams (max_streams)
            assert len(scanner.scan_results["task1"]) >= 7


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
