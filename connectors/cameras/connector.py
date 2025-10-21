"""
Camera Connector for IoT2mqtt
Integrates with go2rtc for stream proxying and publishes stream URLs via MQTT
"""

import sys
import os
import time
import logging
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime

# Add shared libraries to path
sys.path.insert(0, '/app/shared')

from base_connector import BaseConnector
import requests

logger = logging.getLogger(__name__)


class Connector(BaseConnector):
    """
    Camera connector with go2rtc integration

    go2rtc handles stream proxying (RTSP → WebRTC/HLS/MJPEG/etc)
    This connector publishes stream URLs to MQTT for consumers
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Read ports from instance config (via self.config loaded by BaseConnector)
        instance_ports = self.config.get('ports', {})

        # go2rtc API configuration - read from instance ports, fallback to env, then defaults
        self.go2rtc_api_port = str(instance_ports.get('go2rtc_api') or os.getenv('GO2RTC_API_PORT', '1984'))
        self.go2rtc_rtsp_port = str(instance_ports.get('go2rtc_rtsp') or os.getenv('GO2RTC_RTSP_PORT', '8554'))
        self.go2rtc_webrtc_port = str(instance_ports.get('go2rtc_webrtc') or os.getenv('GO2RTC_WEBRTC_PORT', '8555'))
        self.go2rtc_homekit_port = str(instance_ports.get('go2rtc_homekit') or os.getenv('GO2RTC_HOMEKIT_PORT', '8443'))

        self.go2rtc_api = f"http://localhost:{self.go2rtc_api_port}/api"

        # External host for publishing URLs (can be overridden)
        self.external_host = os.getenv('EXTERNAL_HOST', 'localhost')

        # Maximum retries for waiting go2rtc to start
        self.max_retries = 30  # 30 seconds

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

        go2rtc manages its own streams, so nothing special to do here.
        """
        logger.info("🛑 Camera connector shutting down")

    def get_device_state(self, device_id: str, device_config: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Get camera state - returns stream URLs for consumers

        NOTE: We don't check if stream is actually active.
        go2rtc handles on-demand stream activation automatically.

        Args:
            device_id: Camera device ID
            device_config: Camera configuration from instance config

        Returns: State dictionary with stream URLs
        """
        try:
            # Build stream URLs for this camera
            base_url = f"http://{self.external_host}:{self.go2rtc_api_port}"

            state = {
                "online": True,  # Assume online if configured
                "stream_urls": {
                    "webrtc": f"{base_url}/api/webrtc?src={device_id}",
                    "hls": f"{base_url}/{device_id}/stream.m3u8",
                    "mjpeg": f"{base_url}/api/frame.mjpeg?src={device_id}",
                    "snapshot": f"{base_url}/api/frame.jpeg?src={device_id}",
                    "rtsp": f"rtsp://{self.external_host}:{self.go2rtc_rtsp_port}/{device_id}",
                    "mp4": f"{base_url}/api/frame.mp4?src={device_id}"
                },
                "stream_type": device_config.get('stream_type', 'FFMPEG'),
                "name": device_config.get('name', device_id),
                "brand": device_config.get('brand', 'Unknown'),
                "model": device_config.get('model', 'Unknown'),
                "ip": device_config.get('ip'),
                "last_update": datetime.utcnow().isoformat() + 'Z'
            }

            return state

        except Exception as e:
            logger.error(f"Error getting state for {device_id}: {e}")
            return {"online": False}

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
