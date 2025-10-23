"""
Camera Motion Detection Parasitic Connector

Extends camera devices with FFmpeg-based motion detection without modifying parent connectors.
Publishes motion fields to parent camera MQTT topics while maintaining independent control.

Architecture:
- Parasitic connector: extends parent cameras
- Dual-topic publishing: own state + parent extensions
- Independent CMD control plane
- Scales to 100+ cameras from multiple instances
"""

import sys
import os
import logging
from typing import Dict, Any, Optional
from datetime import datetime

# Add shared libraries to path
sys.path.insert(0, '/app/shared')

from base_connector import BaseConnector
from motion_detector import MotionDetector

logger = logging.getLogger(__name__)


class Connector(BaseConnector):
    """
    Motion Detection Parasitic Connector for Cameras

    Extends camera devices by analyzing their RTSP streams and publishing
    motion detection results to parent camera state topics.

    Features:
    - FFmpeg-based motion detection (fast, low CPU)
    - Supports 100+ concurrent camera streams
    - Real-time sensitivity adjustment via CMD
    - Independent enable/disable per camera
    - Graceful handling of offline cameras
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Verify parasitic mode
        if not self.is_parasite_mode:
            raise ValueError(
                "cameras-motion requires parasite_targets configuration. "
                "This is a parasitic connector that extends camera devices."
            )

        logger.info(f"cameras-motion initialized in parasite mode")
        logger.info(f"Monitoring {len(self.parasite_targets)} camera(s) for motion")

        # Motion detection configuration
        sensitivity = self.config.get('config', {}).get('sensitivity', 0.7)
        check_interval = self.config.get('config', {}).get('check_interval', 1.0)

        # Initialize motion detector
        self.motion_detector = MotionDetector(
            sensitivity=sensitivity,
            check_interval=check_interval
        )

        logger.info(f"Motion detector configured: sensitivity={sensitivity}, interval={check_interval}s")

        # Track cameras by device_id for quick lookup
        self.camera_info = {}  # {device_id: target_config}
        for target in self.parasite_targets:
            device_id = target['device_id']
            self.camera_info[device_id] = target

        # Track which cameras have been added to motion detector
        self.cameras_added = set()  # device_ids that have been successfully added

    def initialize_connection(self):
        """
        Initialize motion detection for all parent cameras.

        Note: Cameras may not be added immediately if parent state is not yet available.
        They will be added automatically when parent state updates arrive via MQTT.
        """
        logger.info("🔧 Initializing camera motion detection...")

        # Start motion detector
        self.motion_detector.start()

        # Try to add cameras from extracted_data or cached parent state
        # Don't fail if cameras aren't added - they'll be added on parent state update
        for target in self.parasite_targets:
            device_id = target['device_id']
            self._try_add_camera(device_id, target)

        cameras_count = len(self.cameras_added)
        logger.info(f"🎬 Motion detection initialized: {cameras_count} camera(s) added immediately")

        if cameras_count == 0:
            logger.info("⏳ No cameras added yet - waiting for parent state updates from MQTT...")

    def _select_best_stream(self, stream_urls: Dict[str, str],
                           stream_validation: Dict[str, Any]) -> Optional[tuple]:
        """
        Select the best working stream from available options.

        Priority order (best to worst):
        1. mp4/m3u8/flv/ts - Good for FFmpeg, well-supported
        2. rtsp - If working
        3. mjpeg - If working
        4. jpeg - Fallback (snapshot mode, less ideal)

        Args:
            stream_urls: Dictionary of stream URLs {format: url}
            stream_validation: Dictionary of validation results {format: {status, error, ...}}

        Returns:
            Tuple of (stream_url, format_name) or None if no working stream found
        """
        # Priority order for stream formats
        stream_priority = ['mp4', 'm3u8', 'flv', 'ts', 'rtsp', 'mjpeg', 'jpeg']

        for format_name in stream_priority:
            if format_name not in stream_urls:
                continue

            stream_url = stream_urls[format_name]
            validation = stream_validation.get(format_name, {})
            status = validation.get('status', 'unknown')

            # Check if stream is validated as working
            if status == 'ok':
                logger.debug(f"Selected {format_name} stream (validated: ok)")
                return (stream_url, format_name)

        # Fallback: if no validated streams, try any available stream in priority order
        logger.warning("No validated streams found, trying first available stream")
        for format_name in stream_priority:
            if format_name in stream_urls:
                logger.debug(f"Using unvalidated {format_name} stream as fallback")
                return (stream_urls[format_name], format_name)

        return None

    def _try_add_camera(self, device_id: str, target: Dict[str, Any]) -> bool:
        """
        Try to add camera to motion detector using best available stream.

        Args:
            device_id: Device identifier
            target: Parasite target configuration

        Returns:
            True if camera was added successfully
        """
        # Skip if already added
        if device_id in self.cameras_added:
            logger.debug(f"Camera {device_id} already added to motion detection")
            return True

        mqtt_path = target['mqtt_path']
        extracted_data = target.get('extracted_data', {})

        # Try to get camera info from extracted_data or parent state
        camera_name = extracted_data.get('name')
        stream_urls = {}
        stream_validation = {}

        # First, try parent state (most up-to-date)
        parent_state = self.get_parent_state(mqtt_path)
        if parent_state:
            stream_urls = parent_state.get('stream_urls', {})
            stream_validation = parent_state.get('stream_validation', {})
            if not camera_name:
                camera_name = parent_state.get('name', device_id)

        # Fallback: check extracted_data for individual stream URLs
        if not stream_urls and extracted_data:
            # extracted_data might have individual fields like 'rtsp', 'mp4', etc.
            # Build stream_urls dict from extracted_data
            for key, value in extracted_data.items():
                if key in ['rtsp', 'mp4', 'm3u8', 'flv', 'ts', 'mjpeg', 'jpeg'] and value:
                    stream_urls[key] = value

        if not stream_urls:
            logger.debug(f"No stream URLs available for {device_id} yet, will try again on parent state update")
            return False

        # Select best working stream
        result = self._select_best_stream(stream_urls, stream_validation)
        if not result:
            logger.warning(f"No suitable stream found for {device_id}")
            return False

        stream_url, format_name = result

        try:
            # Add stream to motion detector
            self.motion_detector.add_stream(device_id, stream_url, camera_name or device_id)
            self.cameras_added.add(device_id)
            logger.info(f"✅ Added camera to motion detection: {camera_name or device_id} ({device_id}) using {format_name} stream")
            return True

        except Exception as e:
            logger.error(f"❌ Error adding camera {device_id} to motion detection: {e}", exc_info=True)
            return False

    def _on_parent_state_update(self, mqtt_path: str, topic: str, payload: Dict[str, Any]):
        """
        Override parent state update handler to automatically add cameras when state arrives.

        This solves the timing issue where initialize_connection() runs before parent state
        is received via MQTT.

        Args:
            mqtt_path: Base MQTT path of parent device
            topic: Full MQTT topic
            payload: State payload from parent device
        """
        # Call parent implementation to update cache
        super()._on_parent_state_update(mqtt_path, topic, payload)

        # Find which device_id this mqtt_path belongs to
        device_id = None
        target = None
        for dev_id, cam_info in self.camera_info.items():
            if cam_info['mqtt_path'] == mqtt_path:
                device_id = dev_id
                target = cam_info
                break

        if not device_id or not target:
            logger.debug(f"Received parent state update for unknown mqtt_path: {mqtt_path}")
            return

        # Try to add camera if not already added
        if device_id not in self.cameras_added:
            logger.debug(f"Received parent state update for {device_id}, attempting to add camera...")
            if self._try_add_camera(device_id, target):
                logger.info(f"🎥 Camera {device_id} automatically added after receiving parent state")

    def cleanup_connection(self):
        """
        Cleanup when connector stops.

        Stops all motion detection threads gracefully.
        """
        logger.info("🛑 Stopping camera motion detection...")
        self.motion_detector.stop()
        logger.info("✅ Motion detection stopped")

    def get_device_state(self, device_id: str, device_config: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Get connector's operational state and publish motion fields to parent camera.

        This method is called periodically by BaseConnector's polling loop.

        Returns:
            Own operational state (published to own instance MQTT topic)
        """
        try:
            # Get motion detection state
            motion_state = self.motion_detector.get_motion_state(device_id)

            # Build own operational state (for this connector's instance topic)
            own_state = {
                "online": True,
                "status": "detecting" if device_id in self.motion_detector.enabled_streams else "paused",
                "frames_analyzed": motion_state.get('frame_count', 0),
                "errors": motion_state.get('error_count', 0),
                "last_update": datetime.utcnow().isoformat() + 'Z'
            }

            # Publish extension fields to PARENT camera topic
            if device_id in self.camera_info:
                target = self.camera_info[device_id]
                mqtt_path = target['mqtt_path']

                # Fields to extend parent camera with
                motion_fields = {
                    "motion": motion_state.get('detected', False),
                    "motion_confidence": motion_state.get('confidence', 0.0),
                    "motion_last_detected": motion_state.get('last_detected')
                }

                # Publish to parent device
                self.publish_parasite_fields(mqtt_path, motion_fields)

                logger.debug(f"Published motion fields to parent {mqtt_path}: motion={motion_fields['motion']}")

            return own_state

        except Exception as e:
            logger.error(f"Error getting device state for {device_id}: {e}", exc_info=True)
            return {
                "online": False,
                "error": str(e),
                "last_update": datetime.utcnow().isoformat() + 'Z'
            }

    def set_device_state(self, device_id: str, device_config: Dict[str, Any],
                         command: Dict[str, Any]) -> bool:
        """
        Handle commands sent to THIS connector's CMD topic.

        Commands are sent to: iot2mqtt/v1/instances/cameras_motion_xyz/devices/{device_id}/cmd
        NOT to parent camera CMD topics.

        Supported commands:
        - sensitivity: float (0.1 - 1.0) - Adjust motion detection sensitivity
        - enabled: bool - Enable/disable motion detection for this camera
        - reset_stats: bool - Reset frame count and error statistics

        Args:
            device_id: Device identifier
            device_config: Device configuration
            command: Command dictionary from MQTT

        Returns:
            True if command handled successfully
        """
        try:
            logger.info(f"📥 Received command for {device_id}: {command}")

            # Handle sensitivity adjustment
            if 'sensitivity' in command:
                try:
                    sensitivity = float(command['sensitivity'])
                    sensitivity = max(0.1, min(1.0, sensitivity))  # Clamp to valid range

                    self.motion_detector.set_sensitivity(device_id, sensitivity)
                    logger.info(f"✅ Updated sensitivity for {device_id}: {sensitivity}")

                except (ValueError, TypeError) as e:
                    logger.error(f"❌ Invalid sensitivity value: {command['sensitivity']}")
                    return False

            # Handle enable/disable
            if 'enabled' in command:
                try:
                    enabled = bool(command['enabled'])

                    if enabled:
                        self.motion_detector.enable(device_id)
                        logger.info(f"✅ Enabled motion detection for {device_id}")
                    else:
                        self.motion_detector.disable(device_id)
                        logger.info(f"⏸️  Disabled motion detection for {device_id}")

                except (ValueError, TypeError) as e:
                    logger.error(f"❌ Invalid enabled value: {command['enabled']}")
                    return False

            # Handle stats reset
            if 'reset_stats' in command and command['reset_stats']:
                self.motion_detector.reset_stats(device_id)
                logger.info(f"🔄 Reset statistics for {device_id}")

            return True

        except Exception as e:
            logger.error(f"❌ Error handling command for {device_id}: {e}", exc_info=True)
            return False


if __name__ == '__main__':
    connector = Connector()
    connector.run_forever()
