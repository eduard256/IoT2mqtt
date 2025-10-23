"""
Background Stream Validator for Camera Connector
Validates go2rtc stream URLs using ffprobe in a separate thread
"""

import threading
import time
import logging
import subprocess
from typing import Dict, Any, Optional
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class StreamValidator:
    """
    Validates camera streams from go2rtc in the background

    - Runs in separate thread to not block main MQTT loop
    - Sequential validation to minimize resource usage
    - Caches validation results (5 minute TTL)
    - Validates go2rtc output streams, NOT camera source streams
    """

    def __init__(self, validation_interval: int = 300, timeout: int = 5):
        """
        Initialize validator

        Args:
            validation_interval: Seconds between validation runs (default: 300 = 5 min)
            timeout: Timeout for each stream check in seconds (default: 5)
        """
        self.validation_interval = validation_interval
        self.timeout = timeout

        # Cache: {device_id: {stream_type: {status, last_check, error}}}
        self.validation_cache: Dict[str, Dict[str, Dict[str, Any]]] = {}

        # Validation queue: [(device_id, stream_url, stream_type), ...]
        self.validation_queue = []

        # Thread control
        self.running = False
        self.validator_thread: Optional[threading.Thread] = None
        self.lock = threading.Lock()

    def start(self):
        """Start background validation thread"""
        if self.running:
            logger.warning("StreamValidator already running")
            return

        self.running = True
        self.validator_thread = threading.Thread(target=self._validation_loop, daemon=True)
        self.validator_thread.start()
        logger.info(f"StreamValidator started (interval: {self.validation_interval}s)")

    def stop(self):
        """Stop background validation thread"""
        logger.info("Stopping StreamValidator...")
        self.running = False
        if self.validator_thread:
            self.validator_thread.join(timeout=10)
        logger.info("StreamValidator stopped")

    def add_stream(self, device_id: str, stream_url: str, stream_type: str):
        """
        Add stream to validation queue

        Args:
            device_id: Camera device ID
            stream_url: go2rtc stream URL to validate
            stream_type: Type of stream (mp4, m3u8, mjpeg, etc)
        """
        with self.lock:
            # Check if already in queue
            stream_tuple = (device_id, stream_url, stream_type)
            if stream_tuple not in self.validation_queue:
                self.validation_queue.append(stream_tuple)

    def get_status(self, device_id: str, stream_type: Optional[str] = None) -> Dict[str, Any]:
        """
        Get validation status for device

        Args:
            device_id: Camera device ID
            stream_type: Specific stream type, or None for all

        Returns:
            Dict with validation status per stream type
        """
        with self.lock:
            if device_id not in self.validation_cache:
                return {}

            if stream_type:
                return self.validation_cache[device_id].get(stream_type, {})
            else:
                return self.validation_cache[device_id]

    def _validation_loop(self):
        """Background validation loop"""
        logger.info("StreamValidator loop started")

        while self.running:
            try:
                # Process validation queue
                self._process_queue()

                # Clean expired cache entries
                self._clean_cache()

                # Sleep until next interval
                time.sleep(self.validation_interval)

            except Exception as e:
                logger.error(f"Error in validation loop: {e}", exc_info=True)
                time.sleep(10)  # Wait before retry

        logger.info("StreamValidator loop terminated")

    def _process_queue(self):
        """Process validation queue sequentially"""
        with self.lock:
            queue_copy = self.validation_queue.copy()
            self.validation_queue.clear()

        if not queue_copy:
            return

        logger.info(f"Validating {len(queue_copy)} stream(s)...")

        for device_id, stream_url, stream_type in queue_copy:
            try:
                # Validate stream
                result = self._validate_stream(stream_url)

                # Store result in cache
                with self.lock:
                    if device_id not in self.validation_cache:
                        self.validation_cache[device_id] = {}

                    self.validation_cache[device_id][stream_type] = {
                        "status": "ok" if result["ok"] else "error",
                        "last_check": datetime.utcnow().isoformat() + 'Z',
                        "error": result.get("error"),
                        "details": result.get("result")
                    }

                status = "✅" if result["ok"] else "❌"
                logger.debug(f"{status} {device_id}/{stream_type}: {result.get('error', {}).get('message', 'OK')}")

                # Small delay between checks to reduce load
                time.sleep(0.5)

            except Exception as e:
                logger.error(f"Error validating {device_id}/{stream_type}: {e}")
                with self.lock:
                    if device_id not in self.validation_cache:
                        self.validation_cache[device_id] = {}
                    self.validation_cache[device_id][stream_type] = {
                        "status": "error",
                        "last_check": datetime.utcnow().isoformat() + 'Z',
                        "error": {"code": "validation_exception", "message": str(e)}
                    }

    def _validate_stream(self, stream_url: str) -> Dict[str, Any]:
        """
        Validate single stream using ffprobe

        Args:
            stream_url: Stream URL to validate

        Returns:
            {"ok": bool, "error": {...} or "result": {...}}
        """
        try:
            # Use ffprobe to check stream
            result = subprocess.run(
                [
                    "ffprobe",
                    "-v", "error",
                    "-timeout", str(self.timeout * 1000000),  # microseconds
                    "-print_format", "json",
                    "-show_format",
                    "-show_streams",
                    stream_url
                ],
                capture_output=True,
                timeout=self.timeout + 2,
                text=True
            )

            if result.returncode != 0:
                return {
                    "ok": False,
                    "error": {
                        "code": "stream_unreachable",
                        "message": f"ffprobe failed: {result.stderr[:200]}",
                        "retriable": True
                    }
                }

            # Stream is accessible
            return {
                "ok": True,
                "result": {
                    "validated": True,
                    "message": "Stream accessible"
                }
            }

        except subprocess.TimeoutExpired:
            return {
                "ok": False,
                "error": {
                    "code": "timeout",
                    "message": f"Validation timeout after {self.timeout}s",
                    "retriable": True
                }
            }
        except FileNotFoundError:
            return {
                "ok": False,
                "error": {
                    "code": "missing_dependency",
                    "message": "ffprobe not installed",
                    "retriable": False
                }
            }
        except Exception as e:
            return {
                "ok": False,
                "error": {
                    "code": "validation_error",
                    "message": str(e),
                    "retriable": True
                }
            }

    def _clean_cache(self):
        """Remove expired cache entries (older than validation_interval * 2)"""
        expiry_threshold = datetime.utcnow() - timedelta(seconds=self.validation_interval * 2)

        with self.lock:
            devices_to_remove = []
            total_streams_removed = 0

            for device_id, streams in self.validation_cache.items():
                streams_to_remove = []

                for stream_type, data in streams.items():
                    try:
                        last_check = datetime.fromisoformat(data["last_check"].replace('Z', '+00:00'))
                        if last_check.replace(tzinfo=None) < expiry_threshold:
                            streams_to_remove.append(stream_type)
                    except:
                        # Invalid timestamp, remove it
                        streams_to_remove.append(stream_type)

                # Remove expired streams
                for stream_type in streams_to_remove:
                    del streams[stream_type]

                total_streams_removed += len(streams_to_remove)

                # If no streams left, mark device for removal
                if not streams:
                    devices_to_remove.append(device_id)

            # Remove empty devices
            for device_id in devices_to_remove:
                del self.validation_cache[device_id]

            if devices_to_remove or total_streams_removed:
                logger.debug(f"Cleaned cache: {len(devices_to_remove)} device(s), {total_streams_removed} stream(s)")
