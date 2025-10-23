"""
FFmpeg-based Motion Detection Engine
Efficiently detects motion in multiple RTSP streams simultaneously
"""

import subprocess
import threading
import logging
import time
from typing import Dict, Any, Optional
from datetime import datetime
from collections import defaultdict

logger = logging.getLogger(__name__)


class MotionDetector:
    """
    FFmpeg-based motion detector supporting multiple concurrent streams.

    Uses FFmpeg's scene detection filter for fast, CPU-efficient motion detection.
    Designed to scale to 100+ camera streams.
    """

    def __init__(self, sensitivity: float = 0.7, check_interval: float = 1.0):
        """
        Initialize motion detector.

        Args:
            sensitivity: Motion detection sensitivity (0.1 = very sensitive, 1.0 = less sensitive)
            check_interval: How often to check for motion (seconds)
        """
        self.sensitivity = sensitivity
        self.check_interval = check_interval

        # Stream management
        self.streams = {}  # {device_id: stream_config}
        self.processes = {}  # {device_id: subprocess.Popen}
        self.threads = {}  # {device_id: Thread}

        # Motion state
        self.motion_states = defaultdict(lambda: {
            'detected': False,
            'confidence': 0.0,
            'last_detected': None,
            'frame_count': 0,
            'error_count': 0
        })

        # Control flags
        self.enabled_streams = set()  # device_ids that are enabled
        self.running = False
        self.lock = threading.Lock()

        logger.info(f"MotionDetector initialized (sensitivity={sensitivity}, interval={check_interval}s)")

    def add_stream(self, device_id: str, stream_url: str, name: str = None):
        """
        Add RTSP stream for motion detection.

        Args:
            device_id: Unique device identifier
            stream_url: RTSP URL or other FFmpeg-compatible stream
            name: Human-readable camera name (optional)
        """
        with self.lock:
            if device_id in self.streams:
                logger.warning(f"Stream {device_id} already exists, updating URL")
                self.remove_stream(device_id)

            self.streams[device_id] = {
                'url': stream_url,
                'name': name or device_id,
                'added_at': datetime.now()
            }

            self.enabled_streams.add(device_id)

            # Start detection thread if running
            if self.running:
                self._start_detection_thread(device_id)

            logger.info(f"Added stream: {device_id} ({name}) - {stream_url[:50]}...")

    def remove_stream(self, device_id: str):
        """
        Remove stream from motion detection.

        Args:
            device_id: Device identifier to remove
        """
        with self.lock:
            if device_id not in self.streams:
                logger.warning(f"Stream {device_id} not found")
                return

            # Stop detection thread
            self._stop_detection_thread(device_id)

            # Clean up
            self.streams.pop(device_id, None)
            self.enabled_streams.discard(device_id)
            self.motion_states.pop(device_id, None)

            logger.info(f"Removed stream: {device_id}")

    def start(self):
        """Start motion detection for all added streams."""
        with self.lock:
            if self.running:
                logger.warning("MotionDetector already running")
                return

            self.running = True
            logger.info(f"Starting motion detection for {len(self.streams)} stream(s)")

            # Start detection thread for each stream
            for device_id in list(self.streams.keys()):
                if device_id in self.enabled_streams:
                    self._start_detection_thread(device_id)

    def stop(self):
        """Stop motion detection for all streams."""
        with self.lock:
            if not self.running:
                return

            logger.info("Stopping motion detection...")
            self.running = False

            # Stop all detection threads
            for device_id in list(self.processes.keys()):
                self._stop_detection_thread(device_id)

            logger.info("Motion detection stopped")

    def enable(self, device_id: str):
        """Enable motion detection for specific device."""
        with self.lock:
            if device_id not in self.streams:
                logger.error(f"Cannot enable {device_id}: stream not found")
                return

            self.enabled_streams.add(device_id)

            if self.running and device_id not in self.processes:
                self._start_detection_thread(device_id)

            logger.info(f"Enabled motion detection for {device_id}")

    def disable(self, device_id: str):
        """Disable motion detection for specific device (pause without removing)."""
        with self.lock:
            self.enabled_streams.discard(device_id)

            if device_id in self.processes:
                self._stop_detection_thread(device_id)

            # Clear motion state
            if device_id in self.motion_states:
                self.motion_states[device_id]['detected'] = False
                self.motion_states[device_id]['confidence'] = 0.0

            logger.info(f"Disabled motion detection for {device_id}")

    def set_sensitivity(self, device_id: str, sensitivity: float):
        """
        Update sensitivity for specific device.

        Note: Requires restarting the detection thread to apply.

        Args:
            device_id: Device to update
            sensitivity: New sensitivity value (0.1 - 1.0)
        """
        sensitivity = max(0.1, min(1.0, sensitivity))

        with self.lock:
            if device_id not in self.streams:
                logger.error(f"Cannot set sensitivity for {device_id}: stream not found")
                return

            self.streams[device_id]['sensitivity'] = sensitivity

            # Restart detection thread if running
            if device_id in self.processes:
                self._stop_detection_thread(device_id)
                if device_id in self.enabled_streams:
                    self._start_detection_thread(device_id)

            logger.info(f"Updated sensitivity for {device_id}: {sensitivity}")

    def get_motion_state(self, device_id: str) -> Dict[str, Any]:
        """
        Get current motion detection state for device.

        Args:
            device_id: Device identifier

        Returns:
            Dictionary with: detected, confidence, last_detected, frame_count, error_count
        """
        with self.lock:
            return dict(self.motion_states.get(device_id, {
                'detected': False,
                'confidence': 0.0,
                'last_detected': None,
                'frame_count': 0,
                'error_count': 0
            }))

    def reset_stats(self, device_id: str):
        """Reset statistics for specific device."""
        with self.lock:
            if device_id in self.motion_states:
                self.motion_states[device_id]['frame_count'] = 0
                self.motion_states[device_id]['error_count'] = 0
                logger.info(f"Reset stats for {device_id}")

    def _start_detection_thread(self, device_id: str):
        """Start FFmpeg detection thread for device (internal)."""
        if device_id in self.processes:
            logger.warning(f"Detection thread already running for {device_id}")
            return

        stream_config = self.streams[device_id]
        thread = threading.Thread(
            target=self._detection_worker,
            args=(device_id, stream_config),
            name=f"MotionDetector-{device_id}",
            daemon=True
        )
        thread.start()
        self.threads[device_id] = thread

        logger.debug(f"Started detection thread for {device_id}")

    def _stop_detection_thread(self, device_id: str):
        """Stop FFmpeg detection thread for device (internal)."""
        # Kill subprocess
        if device_id in self.processes:
            try:
                proc = self.processes[device_id]
                proc.terminate()
                proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                proc.kill()
            except Exception as e:
                logger.error(f"Error stopping process for {device_id}: {e}")
            finally:
                self.processes.pop(device_id, None)

        # Wait for thread
        if device_id in self.threads:
            thread = self.threads.pop(device_id)
            # Thread will exit on its own when process is killed
            thread.join(timeout=3)

        logger.debug(f"Stopped detection thread for {device_id}")

    def _detection_worker(self, device_id: str, stream_config: Dict[str, Any]):
        """
        Worker thread that runs FFmpeg for motion detection.

        Uses FFmpeg scene detection filter to detect changes between frames.
        """
        stream_url = stream_config['url']
        sensitivity = stream_config.get('sensitivity', self.sensitivity)

        # FFmpeg command for motion detection
        # Uses select filter with scene detection
        # Outputs frame count when motion detected
        cmd = [
            'ffmpeg',
            '-i', stream_url,
            '-vf', f"select='gt(scene,{sensitivity})',metadata=print:file=-",
            '-f', 'null',
            '-'
        ]

        logger.info(f"Starting FFmpeg for {device_id} with sensitivity={sensitivity}")

        try:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True
            )

            with self.lock:
                self.processes[device_id] = proc

            # Read stderr for motion detection output
            last_motion_time = None
            motion_timeout = 5.0  # Consider motion stopped after 5s without detection

            while self.running and device_id in self.enabled_streams:
                try:
                    # Check if process is still running
                    if proc.poll() is not None:
                        logger.warning(f"FFmpeg process died for {device_id}, restarting...")
                        with self.lock:
                            self.motion_states[device_id]['error_count'] += 1
                        time.sleep(5)  # Wait before restart
                        break

                    # Read stderr line (non-blocking with timeout)
                    line = proc.stderr.readline()

                    if not line:
                        time.sleep(0.1)
                        continue

                    # Parse FFmpeg output for scene changes
                    if 'scene:' in line.lower() or 'pts_time:' in line.lower():
                        # Motion detected!
                        now = datetime.now()
                        last_motion_time = now

                        with self.lock:
                            self.motion_states[device_id]['detected'] = True
                            self.motion_states[device_id]['confidence'] = 0.85  # Estimated
                            self.motion_states[device_id]['last_detected'] = now.isoformat() + 'Z'
                            self.motion_states[device_id]['frame_count'] += 1

                        logger.debug(f"Motion detected: {device_id}")

                    # Check if motion should timeout
                    if last_motion_time:
                        time_since_motion = (datetime.now() - last_motion_time).total_seconds()
                        if time_since_motion > motion_timeout:
                            with self.lock:
                                self.motion_states[device_id]['detected'] = False
                                self.motion_states[device_id]['confidence'] = 0.0

                except Exception as e:
                    logger.error(f"Error processing FFmpeg output for {device_id}: {e}")
                    with self.lock:
                        self.motion_states[device_id]['error_count'] += 1
                    time.sleep(1)

        except Exception as e:
            logger.error(f"Fatal error in detection worker for {device_id}: {e}")
            with self.lock:
                self.motion_states[device_id]['error_count'] += 1

        finally:
            # Cleanup
            if proc and proc.poll() is None:
                try:
                    proc.terminate()
                    proc.wait(timeout=2)
                except:
                    proc.kill()

            with self.lock:
                self.processes.pop(device_id, None)

            logger.info(f"Detection worker stopped for {device_id}")
