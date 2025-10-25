"""
Camera Connector for IoT2mqtt
Integrates with go2rtc for stream proxying and publishes stream URLs via MQTT
"""

import sys
import os
import time
import logging
import socket
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime

# Add shared libraries to path
sys.path.insert(0, '/app/shared')

from base_connector import BaseConnector
import requests

# Import stream validator
from stream_validator import StreamValidator

logger = logging.getLogger(__name__)


def get_host_ip() -> str:
    """
    Auto-detect host IP address for external URL generation

    Strategy:
    1. Try EXTERNAL_HOST from environment (manual override)
    2. Connect to MQTT broker and get local IP from socket
    3. Fallback to 'localhost'

    Returns: IP address or hostname
    """
    # 1. Check environment variable first (manual override)
    external_host = os.getenv('EXTERNAL_HOST')
    if external_host:
        logger.info(f"Using EXTERNAL_HOST from environment: {external_host}")
        return external_host

    # 2. Auto-detect by connecting to MQTT broker
    try:
        mqtt_host = os.getenv('MQTT_HOST', 'localhost')
        mqtt_port = int(os.getenv('MQTT_PORT', '1883'))

        # Create socket and connect to MQTT broker
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(2)
        s.connect((mqtt_host, mqtt_port))

        # Get local IP from socket
        local_ip = s.getsockname()[0]
        s.close()

        logger.info(f"Auto-detected host IP: {local_ip}")
        return local_ip

    except Exception as e:
        logger.warning(f"Failed to auto-detect IP: {e}, using 'localhost'")
        return 'localhost'


class Connector(BaseConnector):
    """
    Camera connector with go2rtc integration

    New architecture:
    - Reads stream info from go2rtc API (/api/streams)
    - Generates and publishes ONLY go2rtc output stream URLs
    - NEVER publishes camera source URLs (they contain credentials!)
    - Background validation of streams using ffprobe
    - Uses dynamic ports from instance config
    - Uses EXTERNAL_HOST from environment for public URLs
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Read ports from instance config (via self.config loaded by BaseConnector)
        instance_ports = self.config.get('ports', {})

        # go2rtc API configuration - read from instance ports, fallback to env, then defaults
        self.go2rtc_api_port = str(instance_ports.get('go2rtc_api') or os.getenv('GO2RTC_API_PORT', '1984'))
        self.go2rtc_rtsp_port = str(instance_ports.get('go2rtc_rtsp') or os.getenv('GO2RTC_RTSP_PORT', '8554'))
        self.go2rtc_webrtc_port = str(instance_ports.get('go2rtc_webrtc') or os.getenv('GO2RTC_WEBRTC_PORT', '8555'))

        self.go2rtc_api = f"http://localhost:{self.go2rtc_api_port}/api"

        # External host for publishing URLs - CRITICAL for remote access
        # Auto-detect if not set in environment
        self.external_host = get_host_ip()

        # Maximum retries for waiting go2rtc to start
        self.max_retries = 30  # 30 seconds

        # Stream validator (background thread)
        self.stream_validator = StreamValidator(
            validation_interval=300,  # 5 minutes
            timeout=5
        )

        # Cache device configs by device_id for quick lookup
        self.device_configs = {}
        for device in self.config.get('devices', []):
            if device.get('enabled', True):
                self.device_configs[device['device_id']] = device

        logger.info(f"Camera connector initialized: {len(self.device_configs)} device(s)")
        logger.info(f"External host: {self.external_host}")
        logger.info(f"go2rtc ports: API={self.go2rtc_api_port}, RTSP={self.go2rtc_rtsp_port}")

    def initialize_connection(self):
        """
        Initialize connector: Wait for go2rtc to be ready

        go2rtc is started by supervisord before this connector.
        We just need to verify it's responsive.
        """
        logger.info("🔧 Initializing camera connector...")

        # Wait for go2rtc HTTP API
        if not self._wait_for_go2rtc():
            raise RuntimeError("go2rtc failed to start - HTTP API not responding")

        # Start stream validator
        self.stream_validator.start()

        logger.info("✅ Camera connector initialized successfully")

    def _wait_for_go2rtc(self) -> bool:
        """
        Wait for go2rtc HTTP API to be ready

        Returns: True if go2rtc is ready, False if timeout
        """
        logger.info(f"⏳ Waiting for go2rtc to start (max {self.max_retries}s)...")

        for attempt in range(1, self.max_retries + 1):
            try:
                response = requests.get(f"{self.go2rtc_api}", timeout=1)

                if response.ok:
                    info = response.json()
                    version = info.get('version', 'unknown')
                    logger.info(f"✅ go2rtc ready (version: {version})")
                    return True

            except requests.exceptions.RequestException:
                pass

            # Log progress every 5 seconds
            if attempt % 5 == 0:
                logger.info(f"   Still waiting... ({attempt}/{self.max_retries}s)")

            time.sleep(1)

        logger.error(f"❌ go2rtc not responding after {self.max_retries} seconds")
        return False

    def cleanup_connection(self):
        """
        Cleanup on shutdown

        Stop stream validator and cleanup resources
        """
        logger.info("🛑 Camera connector shutting down")
        self.stream_validator.stop()

    def get_device_state(self, device_id: str, device_config: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Get camera state from go2rtc API and generate stream URLs

        NEW LOGIC:
        1. Query go2rtc API to check if stream exists
        2. Generate all go2rtc output stream URLs (NOT camera source!)
        3. Get validation status from background validator
        4. Return comprehensive state with all streams

        Args:
            device_id: Camera device ID
            device_config: Camera configuration from instance config

        Returns: State dictionary with go2rtc stream URLs
        """
        try:
            # Query go2rtc for active streams
            response = requests.get(f"{self.go2rtc_api}/streams", timeout=5)

            if not response.ok:
                logger.error(f"go2rtc API error: {response.status_code}")
                return {"online": False, "error": "go2rtc API unavailable"}

            streams_data = response.json()

            # Check if this device exists in go2rtc
            if device_id not in streams_data:
                logger.warning(f"Device {device_id} not found in go2rtc streams")
                return {
                    "online": False,
                    "device_id": device_id,
                    "name": device_config.get('name', device_id),
                    "error": "Stream not configured in go2rtc"
                }

            # Device exists in go2rtc
            stream_info = streams_data[device_id]

            # Generate all go2rtc output stream URLs
            stream_urls = self._generate_stream_urls(device_id)

            # Queue all streams for validation
            for stream_type, stream_url in stream_urls.items():
                if stream_type not in ['rtsp', 'ws']:  # HTTP streams only for now
                    self.stream_validator.add_stream(device_id, stream_url, stream_type)

            # Get validation status
            validation_status = self.stream_validator.get_status(device_id)

            # Build comprehensive state
            state = {
                "online": True,
                "device_id": device_id,
                "name": device_config.get('name', device_id),
                "brand": device_config.get('brand', 'Unknown'),
                "model": device_config.get('model', 'Unknown'),
                "ip": device_config.get('ip'),  # For display only, not for streaming
                "stream_type": device_config.get('stream_type', 'FFMPEG'),
                "stream_urls": stream_urls,
                "stream_validation": validation_status,
                "producers": len(stream_info.get('producers', [])),  # Number of sources
                "consumers": len(stream_info.get('consumers', [])) if stream_info.get('consumers') else 0,  # Active viewers
                "last_update": datetime.utcnow().isoformat() + 'Z'
            }

            return state

        except requests.exceptions.RequestException as e:
            logger.error(f"Error querying go2rtc API for {device_id}: {e}")
            return {
                "online": False,
                "device_id": device_id,
                "name": device_config.get('name', device_id),
                "error": f"go2rtc API error: {str(e)}"
            }
        except Exception as e:
            logger.error(f"Error getting state for {device_id}: {e}", exc_info=True)
            return {
                "online": False,
                "device_id": device_id,
                "name": device_config.get('name', device_id),
                "error": str(e)
            }

    def _generate_stream_urls(self, device_id: str) -> Dict[str, str]:
        """
        Generate all go2rtc output stream URLs for a device

        IMPORTANT: These are URLs TO go2rtc, NOT from cameras!
        Never include camera credentials in these URLs.

        Args:
            device_id: Camera device ID

        Returns: Dict with all available stream format URLs
        """
        # Use dynamic ports from config and external host from environment
        api_port = self.go2rtc_api_port
        rtsp_port = self.go2rtc_rtsp_port
        host = self.external_host

        return {
            # Video formats
            "mp4": f"http://{host}:{api_port}/api/stream.mp4?src={device_id}",
            "m3u8": f"http://{host}:{api_port}/api/stream.m3u8?src={device_id}",
            "mjpeg": f"http://{host}:{api_port}/api/stream.mjpeg?src={device_id}",
            "flv": f"http://{host}:{api_port}/api/stream.flv?src={device_id}",
            "ts": f"http://{host}:{api_port}/api/stream.ts?src={device_id}",

            # Audio
            "aac": f"http://{host}:{api_port}/api/stream.aac?src={device_id}",

            # Snapshots
            "jpeg": f"http://{host}:{api_port}/api/frame.jpeg?src={device_id}",

            # Streaming protocols
            "ws": f"ws://{host}:{api_port}/api/ws?src={device_id}",
            "rtsp": f"rtsp://{host}:{rtsp_port}/{device_id}"
        }

    def _publish_ha_discovery(self):
        """
        Override BaseConnector discovery to add stream URLs for cameras

        Cameras need stream_urls in device_config for HA Discovery
        """
        if not self.ha_discovery_enabled or not self.discovery_generator:
            logger.debug("Home Assistant Discovery disabled, skipping")
            return

        logger.info("Publishing Home Assistant Discovery for cameras...")
        total_published = 0

        for device_config in self.config.get('devices', []):
            if not device_config.get('enabled', True):
                continue

            device_id = device_config['device_id']

            try:
                # Generate stream URLs for this camera
                stream_urls = self._generate_stream_urls(device_id)

                # Create enhanced config with stream URLs for discovery
                enhanced_config = device_config.copy()
                enhanced_config['stream_urls'] = stream_urls
                enhanced_config['class'] = 'security.camera'  # Set camera class

                # Generate discovery messages
                discovery_messages = self.discovery_generator.generate_device_discovery(
                    device_id=device_id,
                    device_config=enhanced_config
                )

                if discovery_messages:
                    self.mqtt.publish_ha_discovery(discovery_messages)
                    total_published += len(discovery_messages)
                    logger.info(f"Published HA discovery for camera: {device_id}")

            except Exception as e:
                logger.error(f"Error generating discovery for {device_id}: {e}", exc_info=True)

        logger.info(f"HA Discovery complete: {total_published} message(s) published")

    def set_device_state(self, device_id: str, device_config: Dict[str, Any],
                        command: Dict[str, Any]) -> bool:
        """
        Handle camera commands

        Currently a stub. Future: PTZ control via ONVIF

        Args:
            device_id: Camera device ID
            device_config: Camera configuration
            command: Command dictionary from MQTT

        Returns: True if command handled successfully
        """
        logger.info(f"Command received for {device_id}: {command}")

        # TODO: Implement PTZ commands
        # if 'ptz' in command:
        #     return self._handle_ptz_command(device_id, command['ptz'])

        logger.warning(f"Camera commands not yet implemented")
        return True


if __name__ == '__main__':
    connector = Connector()
    connector.run_forever()
