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

    def initialize_connection(self):
        """
        Initialize motion detection for all parent cameras.

        Called after MQTT connection is established and parent state subscriptions are set up.
        """
        logger.info("🔧 Initializing camera motion detection...")

        # Start motion detector
        self.motion_detector.start()

        # Add each camera stream to motion detector
        cameras_added = 0
        cameras_failed = 0

        for target in self.parasite_targets:
            device_id = target['device_id']
            mqtt_path = target['mqtt_path']

            try:
                # Try to get RTSP URL from extracted_data (from mqtt_device_picker)
                extracted_data = target.get('extracted_data', {})
                rtsp_url = extracted_data.get('rtsp')
                camera_name = extracted_data.get('name', device_id)

                # Fallback: try to get from parent state cache
                if not rtsp_url:
                    logger.debug(f"No RTSP URL in extracted_data for {device_id}, checking parent state...")
                    parent_state = self.get_parent_state(mqtt_path)

                    if parent_state:
                        stream_urls = parent_state.get('stream_urls', {})
                        rtsp_url = stream_urls.get('rtsp')
                        if not camera_name:
                            camera_name = parent_state.get('name', device_id)

                if rtsp_url:
                    # Add stream to motion detector
                    self.motion_detector.add_stream(device_id, rtsp_url, camera_name)
                    cameras_added += 1
                    logger.info(f"✅ Added camera to motion detection: {camera_name} ({device_id})")
                else:
                    cameras_failed += 1
                    logger.error(f"❌ Cannot start motion detection for {device_id}: No RTSP URL available")

            except Exception as e:
                cameras_failed += 1
                logger.error(f"❌ Error initializing motion detection for {device_id}: {e}", exc_info=True)

        logger.info(f"🎬 Motion detection initialized: {cameras_added} camera(s) active, {cameras_failed} failed")

        if cameras_added == 0:
            logger.warning("⚠️  No cameras successfully added to motion detection!")

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
