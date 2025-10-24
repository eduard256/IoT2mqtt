"""
Comprehensive tests for StreamValidator

Tests cover:
1. Validator initialization
2. Thread lifecycle (start/stop)
3. Stream queue management
4. Stream validation with ffprobe
5. Validation result caching
6. Cache expiration and cleanup
7. Status retrieval
8. Error handling
"""

import pytest
import time
import threading
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime, timedelta
import subprocess
import sys
from pathlib import Path

# Add cameras connector to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from stream_validator import StreamValidator


# ============================================================================
# TIER 1 - CRITICAL TESTS: Initialization
# ============================================================================

class TestStreamValidatorInitialization:
    """Test StreamValidator initialization"""

    def test_initialization_with_defaults(self):
        """Should initialize with default values"""
        validator = StreamValidator()

        assert validator.validation_interval == 300
        assert validator.timeout == 5
        assert validator.validation_cache == {}
        assert validator.validation_queue == []
        assert validator.running is False

    def test_initialization_with_custom_params(self):
        """Should initialize with custom parameters"""
        validator = StreamValidator(validation_interval=60, timeout=10)

        assert validator.validation_interval == 60
        assert validator.timeout == 10


# ============================================================================
# TIER 1 - CRITICAL TESTS: Thread Lifecycle
# ============================================================================

class TestThreadLifecycle:
    """Test validator thread start/stop"""

    def test_start_thread(self):
        """Should start validation thread"""
        validator = StreamValidator(validation_interval=1)

        assert validator.running is False
        assert validator.validator_thread is None

        validator.start()

        assert validator.running is True
        assert validator.validator_thread is not None
        assert validator.validator_thread.is_alive()

        # Cleanup
        validator.stop()

    def test_start_already_running(self):
        """Should not start if already running"""
        validator = StreamValidator(validation_interval=1)
        validator.start()

        original_thread = validator.validator_thread

        # Try to start again
        validator.start()

        # Should be same thread
        assert validator.validator_thread == original_thread

        validator.stop()

    def test_stop_thread(self):
        """Should stop validation thread"""
        validator = StreamValidator(validation_interval=1)
        validator.start()

        time.sleep(0.1)  # Let thread start
        assert validator.running is True

        validator.stop()

        assert validator.running is False
        # Give thread time to finish
        time.sleep(0.2)
        assert not validator.validator_thread.is_alive()

    def test_stop_not_running(self):
        """Should handle stop when not running gracefully"""
        validator = StreamValidator()

        # Should not raise exception
        validator.stop()


# ============================================================================
# TIER 1 - CRITICAL TESTS: Queue Management
# ============================================================================

class TestQueueManagement:
    """Test stream queue operations"""

    def test_add_stream_to_queue(self):
        """Should add stream to validation queue"""
        validator = StreamValidator()

        validator.add_stream("cam1", "http://localhost/stream.mp4", "mp4")

        assert len(validator.validation_queue) == 1
        assert validator.validation_queue[0] == ("cam1", "http://localhost/stream.mp4", "mp4")

    def test_add_multiple_streams(self):
        """Should add multiple streams to queue"""
        validator = StreamValidator()

        validator.add_stream("cam1", "http://localhost/stream1.mp4", "mp4")
        validator.add_stream("cam2", "http://localhost/stream2.m3u8", "m3u8")

        assert len(validator.validation_queue) == 2

    def test_dont_add_duplicate_streams(self):
        """Should not add duplicate streams"""
        validator = StreamValidator()

        validator.add_stream("cam1", "http://localhost/stream.mp4", "mp4")
        validator.add_stream("cam1", "http://localhost/stream.mp4", "mp4")

        # Should only have one entry
        assert len(validator.validation_queue) == 1

    def test_add_different_stream_types_for_same_device(self):
        """Should allow different stream types for same device"""
        validator = StreamValidator()

        validator.add_stream("cam1", "http://localhost/stream.mp4", "mp4")
        validator.add_stream("cam1", "http://localhost/stream.m3u8", "m3u8")

        assert len(validator.validation_queue) == 2


# ============================================================================
# TIER 1 - CRITICAL TESTS: Stream Validation
# ============================================================================

class TestStreamValidation:
    """Test stream validation with ffprobe"""

    def test_validate_stream_success(self):
        """Should validate stream successfully with ffprobe"""
        validator = StreamValidator()

        # Mock successful ffprobe
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(returncode=0, stderr='', stdout='{}')

            result = validator._validate_stream("http://localhost/stream.mp4")

            assert result['ok'] is True
            assert 'result' in result

    def test_validate_stream_ffprobe_failure(self):
        """Should handle ffprobe failure"""
        validator = StreamValidator()

        # Mock failed ffprobe
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(returncode=1, stderr='Connection refused')

            result = validator._validate_stream("http://localhost/stream.mp4")

            assert result['ok'] is False
            assert result['error']['code'] == 'stream_unreachable'

    def test_validate_stream_timeout(self):
        """Should handle validation timeout"""
        validator = StreamValidator(timeout=2)

        # Mock timeout
        with patch('subprocess.run') as mock_run:
            mock_run.side_effect = subprocess.TimeoutExpired('ffprobe', 2)

            result = validator._validate_stream("http://localhost/stream.mp4")

            assert result['ok'] is False
            assert result['error']['code'] == 'timeout'

    def test_validate_stream_ffprobe_not_installed(self):
        """Should handle missing ffprobe"""
        validator = StreamValidator()

        # Mock FileNotFoundError
        with patch('subprocess.run') as mock_run:
            mock_run.side_effect = FileNotFoundError("ffprobe not found")

            result = validator._validate_stream("http://localhost/stream.mp4")

            assert result['ok'] is False
            assert result['error']['code'] == 'missing_dependency'
            assert result['error']['retriable'] is False


# ============================================================================
# TIER 1 - CRITICAL TESTS: Validation Caching
# ============================================================================

class TestValidationCaching:
    """Test validation result caching"""

    def test_cache_validation_result_success(self):
        """Should cache successful validation result"""
        validator = StreamValidator(validation_interval=1)

        with patch.object(validator, '_validate_stream', return_value={'ok': True, 'result': {'validated': True}}):
            validator.start()

            validator.add_stream("cam1", "http://localhost/stream.mp4", "mp4")

            # Wait for validation
            time.sleep(1.5)

            validator.stop()

        # Check cache
        status = validator.get_status("cam1", "mp4")
        assert status['status'] == 'ok'
        assert 'last_check' in status

    def test_cache_validation_result_error(self):
        """Should cache failed validation result"""
        validator = StreamValidator(validation_interval=1)

        with patch.object(validator, '_validate_stream', return_value={
            'ok': False,
            'error': {'code': 'timeout', 'message': 'Timeout'}
        }):
            validator.start()

            validator.add_stream("cam1", "http://localhost/stream.mp4", "mp4")

            time.sleep(1.5)
            validator.stop()

        status = validator.get_status("cam1", "mp4")
        assert status['status'] == 'error'
        assert status['error']['code'] == 'timeout'

    def test_cache_multiple_stream_types(self):
        """Should cache multiple stream types per device"""
        validator = StreamValidator(validation_interval=1)

        with patch.object(validator, '_validate_stream', return_value={'ok': True, 'result': {}}):
            validator.start()

            validator.add_stream("cam1", "http://localhost/stream.mp4", "mp4")
            validator.add_stream("cam1", "http://localhost/stream.m3u8", "m3u8")

            time.sleep(1.5)
            validator.stop()

        all_status = validator.get_status("cam1")
        assert 'mp4' in all_status
        assert 'm3u8' in all_status


# ============================================================================
# TIER 1 - CRITICAL TESTS: Status Retrieval
# ============================================================================

class TestStatusRetrieval:
    """Test validation status retrieval"""

    def test_get_status_specific_stream_type(self):
        """Should get status for specific stream type"""
        validator = StreamValidator()

        # Manually populate cache
        validator.validation_cache["cam1"] = {
            "mp4": {"status": "ok", "last_check": datetime.utcnow().isoformat() + 'Z'},
            "m3u8": {"status": "error", "last_check": datetime.utcnow().isoformat() + 'Z'}
        }

        status = validator.get_status("cam1", "mp4")

        assert status['status'] == 'ok'

    def test_get_status_all_stream_types(self):
        """Should get status for all stream types when type not specified"""
        validator = StreamValidator()

        validator.validation_cache["cam1"] = {
            "mp4": {"status": "ok"},
            "m3u8": {"status": "ok"}
        }

        status = validator.get_status("cam1")

        assert 'mp4' in status
        assert 'm3u8' in status

    def test_get_status_nonexistent_device(self):
        """Should return empty dict for nonexistent device"""
        validator = StreamValidator()

        status = validator.get_status("nonexistent")

        assert status == {}

    def test_get_status_nonexistent_stream_type(self):
        """Should return empty dict for nonexistent stream type"""
        validator = StreamValidator()

        validator.validation_cache["cam1"] = {
            "mp4": {"status": "ok"}
        }

        status = validator.get_status("cam1", "m3u8")

        assert status == {}


# ============================================================================
# TIER 1 - CRITICAL TESTS: Cache Cleanup
# ============================================================================

class TestCacheCleanup:
    """Test cache expiration and cleanup"""

    def test_clean_expired_cache_entries(self):
        """Should remove expired cache entries"""
        validator = StreamValidator(validation_interval=1)

        # Add old entry (expired)
        old_time = (datetime.utcnow() - timedelta(seconds=10)).isoformat() + 'Z'
        validator.validation_cache["cam1"] = {
            "mp4": {"status": "ok", "last_check": old_time}
        }

        # Add recent entry (not expired)
        recent_time = datetime.utcnow().isoformat() + 'Z'
        validator.validation_cache["cam2"] = {
            "mp4": {"status": "ok", "last_check": recent_time}
        }

        validator._clean_cache()

        # cam1 should be removed, cam2 should remain
        assert "cam1" not in validator.validation_cache
        assert "cam2" in validator.validation_cache

    def test_clean_expired_stream_types(self):
        """Should remove expired stream types but keep device if others remain"""
        validator = StreamValidator(validation_interval=1)

        old_time = (datetime.utcnow() - timedelta(seconds=10)).isoformat() + 'Z'
        recent_time = datetime.utcnow().isoformat() + 'Z'

        validator.validation_cache["cam1"] = {
            "mp4": {"status": "ok", "last_check": old_time},  # Expired
            "m3u8": {"status": "ok", "last_check": recent_time}  # Not expired
        }

        validator._clean_cache()

        # Only mp4 should be removed
        assert "cam1" in validator.validation_cache
        assert "mp4" not in validator.validation_cache["cam1"]
        assert "m3u8" in validator.validation_cache["cam1"]

    def test_remove_device_when_all_streams_expired(self):
        """Should remove device when all stream types are expired"""
        validator = StreamValidator(validation_interval=1)

        old_time = (datetime.utcnow() - timedelta(seconds=10)).isoformat() + 'Z'

        validator.validation_cache["cam1"] = {
            "mp4": {"status": "ok", "last_check": old_time},
            "m3u8": {"status": "ok", "last_check": old_time}
        }

        validator._clean_cache()

        # Device should be completely removed
        assert "cam1" not in validator.validation_cache


# ============================================================================
# TIER 1 - CRITICAL TESTS: Error Handling
# ============================================================================

class TestErrorHandling:
    """Test error handling in validation loop"""

    def test_handle_validation_exception(self):
        """Should handle exceptions during validation"""
        validator = StreamValidator(validation_interval=1)

        # Cause exception in validation
        with patch.object(validator, '_validate_stream', side_effect=Exception("Test error")):
            validator.start()

            validator.add_stream("cam1", "http://localhost/stream.mp4", "mp4")

            time.sleep(1.5)
            validator.stop()

        # Should have error in cache
        status = validator.get_status("cam1", "mp4")
        assert status['status'] == 'error'
        assert status['error']['code'] == 'validation_exception'

    def test_handle_invalid_timestamp_in_cache(self):
        """Should remove entries with invalid timestamps during cleanup"""
        validator = StreamValidator(validation_interval=1)

        # Add entry with invalid timestamp
        validator.validation_cache["cam1"] = {
            "mp4": {"status": "ok", "last_check": "invalid-timestamp"}
        }

        # Should not raise exception
        validator._clean_cache()

        # Entry should be removed
        assert "cam1" not in validator.validation_cache


# ============================================================================
# TIER 1 - CRITICAL TESTS: Thread Safety
# ============================================================================

class TestThreadSafety:
    """Test thread-safe operations"""

    def test_concurrent_add_streams(self):
        """Should handle concurrent add_stream calls safely"""
        validator = StreamValidator()

        def add_streams():
            for i in range(10):
                validator.add_stream(f"cam{i}", f"http://localhost/stream{i}.mp4", "mp4")

        # Run multiple threads adding streams
        threads = [threading.Thread(target=add_streams) for _ in range(3)]

        for t in threads:
            t.start()

        for t in threads:
            t.join()

        # Should have 10 unique streams (not duplicates)
        assert len(validator.validation_queue) == 10

    def test_concurrent_get_status(self):
        """Should handle concurrent get_status calls safely"""
        validator = StreamValidator()

        validator.validation_cache["cam1"] = {
            "mp4": {"status": "ok"}
        }

        results = []

        def get_status():
            result = validator.get_status("cam1", "mp4")
            results.append(result)

        threads = [threading.Thread(target=get_status) for _ in range(10)]

        for t in threads:
            t.start()

        for t in threads:
            t.join()

        # All threads should get the same result
        assert len(results) == 10
        assert all(r['status'] == 'ok' for r in results)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
