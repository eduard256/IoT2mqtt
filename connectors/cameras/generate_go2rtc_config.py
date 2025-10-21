#!/usr/bin/env python3
"""
Generate go2rtc configuration from IoT2mqtt instance config
Runs BEFORE go2rtc starts (Docker ENTRYPOINT)
"""

import json
import yaml
import os
import sys
import re
from pathlib import Path
from typing import Dict, Any, List, Optional
from urllib.parse import urlparse


class Go2RTCConfigGenerator:
    """Generate go2rtc YAML config from IoT2mqtt cameras instance"""

    def __init__(self, instance_name: str):
        self.instance_name = instance_name
        self.config_path = f"/app/instances/{instance_name}.json"

        # Read ports from instance config, fallback to env, then defaults
        instance_config = self.load_instance_config()
        instance_ports = instance_config.get('ports', {})

        self.api_port = instance_ports.get('go2rtc_api') or os.getenv('GO2RTC_API_PORT', '1984')
        self.rtsp_port = instance_ports.get('go2rtc_rtsp') or os.getenv('GO2RTC_RTSP_PORT', '8554')
        self.webrtc_port = instance_ports.get('go2rtc_webrtc') or os.getenv('GO2RTC_WEBRTC_PORT', '8555')
        self.homekit_port = instance_ports.get('go2rtc_homekit') or os.getenv('GO2RTC_HOMEKIT_PORT', '8443')

    def load_instance_config(self) -> Dict[str, Any]:
        """Load IoT2mqtt instance configuration"""
        if not os.path.exists(self.config_path):
            raise FileNotFoundError(f"Instance config not found: {self.config_path}")

        with open(self.config_path, 'r') as f:
            return json.load(f)

    def _inject_credentials(self, url: str, username: str, password: str) -> str:
        """
        Inject credentials into URL if not already present

        Args:
            url: Original URL (http://, https://, rtsp://, rtmp://)
            username: Username from device config
            password: Password from device config

        Returns:
            URL with credentials injected if missing

        Example:
            Input: http://10.0.20.112/snapshot.jpg
            Output: http://admin:pass@10.0.20.112/snapshot.jpg
        """
        if not url or not username:
            return url

        # Check if credentials are already in the URL (contains '@' after protocol)
        if '://' in url and '@' in url.split('://', 1)[1].split('/')[0]:
            # URL already has credentials: http://user:pass@host/path
            return url

        # Parse URL and inject credentials
        if '://' in url:
            protocol, rest = url.split('://', 1)
            # Insert credentials: protocol://username:password@rest
            return f"{protocol}://{username}:{password}@{rest}"

        # URL without protocol - return as-is
        return url

    def build_go2rtc_source(self, device: Dict[str, Any]) -> Optional[str]:
        """
        Build go2rtc source URL from device config with proper handling for all types

        Supported stream types:
        - FFMPEG/RTSP: Direct RTSP streams (rtsp://...)
        - JPEG: Static snapshots → converted to exec:ffmpeg for rate limiting
        - MJPEG: MJPEG video streams over HTTP (native support)
        - HTTP: HTTP-FLV, MPEG-TS and other HTTP sources (native support)
        - ONVIF: Auto-discovery via ONVIF protocol

        Returns: Source URL string or None if invalid
        """
        stream_type = device.get('stream_type', 'FFMPEG')
        stream_url = device.get('stream_url', '')
        device_id = device.get('device_id', 'unknown')

        # 1. RTSP/FFMPEG sources - direct passthrough
        if stream_type == 'FFMPEG':
            if not stream_url:
                print(f"  ⚠️  {device_id}: Missing stream_url for FFMPEG type", file=sys.stderr)
                return None

            # Validate RTSP URL
            if not stream_url.startswith('rtsp://') and not stream_url.startswith('rtmp://'):
                print(f"  ⚠️  {device_id}: FFMPEG stream_url should start with rtsp:// or rtmp://", file=sys.stderr)

            # Inject credentials if missing
            username = device.get('username', '')
            password = device.get('password', '')
            return self._inject_credentials(stream_url, username, password)

        # 2. JPEG snapshots - use exec:ffmpeg to avoid camera protection
        elif stream_type == 'JPEG':
            if not stream_url:
                print(f"  ⚠️  {device_id}: Missing stream_url for JPEG type", file=sys.stderr)
                return None

            return self._build_jpeg_ffmpeg_source(device, stream_url)

        # 3. MJPEG streams - native go2rtc support
        elif stream_type == 'MJPEG':
            if not stream_url:
                print(f"  ⚠️  {device_id}: Missing stream_url for MJPEG type", file=sys.stderr)
                return None

            # Validate HTTP URL
            if not stream_url.startswith('http://') and not stream_url.startswith('https://'):
                print(f"  ⚠️  {device_id}: MJPEG stream_url should start with http:// or https://", file=sys.stderr)

            # Inject credentials if missing
            username = device.get('username', '')
            password = device.get('password', '')
            return self._inject_credentials(stream_url, username, password)

        # 4. HTTP sources (FLV, MPEG-TS, etc) - native go2rtc support
        elif stream_type == 'HTTP':
            if not stream_url:
                print(f"  ⚠️  {device_id}: Missing stream_url for HTTP type", file=sys.stderr)
                return None

            # Validate HTTP URL
            if not stream_url.startswith('http://') and not stream_url.startswith('https://'):
                print(f"  ⚠️  {device_id}: HTTP stream_url should start with http:// or https://", file=sys.stderr)

            # Inject credentials if missing
            username = device.get('username', '')
            password = device.get('password', '')
            return self._inject_credentials(stream_url, username, password)

        # 5. ONVIF - prefer concrete stream_url if available, otherwise use ONVIF auto-discovery
        elif stream_type == 'ONVIF':
            # If scanner found a concrete stream_url - use it as RTSP (faster, more reliable)
            if stream_url:
                # stream_url should already contain full rtsp:// URL
                # Add credentials if they're not in the URL
                if '://' in stream_url and '@' not in stream_url:
                    # URL without credentials: rtsp://10.0.20.111:554/live/main
                    parsed = urlparse(stream_url)
                    username = device.get('username', 'admin')
                    password = device.get('password', '')

                    if username and password:
                        # Insert credentials: rtsp://admin:pass@10.0.20.111:554/live/main
                        netloc_with_creds = f"{username}:{password}@{parsed.netloc}"
                        stream_url = stream_url.replace(f"://{parsed.netloc}", f"://{netloc_with_creds}")

                return stream_url

            # No stream_url - use ONVIF auto-discovery
            ip = device.get('ip')
            if not ip:
                print(f"  ⚠️  {device_id}: Missing IP address for ONVIF type", file=sys.stderr)
                return None

            port = device.get('port', 80)  # ONVIF service port (usually 80), NOT RTSP port (554)
            username = device.get('username', 'admin')
            password = device.get('password', '')

            return f"onvif://{username}:{password}@{ip}:{port}"

        # Unknown type - try to use stream_url as-is with warning
        else:
            print(f"  ⚠️  {device_id}: Unknown stream_type '{stream_type}', using stream_url as-is", file=sys.stderr)
            return stream_url if stream_url else None

    def _build_jpeg_ffmpeg_source(self, device: Dict[str, Any], stream_url: str) -> str:
        """
        Build exec:ffmpeg source for JPEG snapshots

        This method uses FFmpeg to convert static JPEG snapshots into MJPEG stream
        with controlled framerate to avoid triggering camera's DoS protection.

        Args:
            device: Device configuration dict
            stream_url: JPEG snapshot URL (can be relative or absolute)

        Returns:
            exec:ffmpeg source string

        Example:
            Input: http://10.0.20.112/snapshot.jpg?user=admin&pwd=pass&strm=0
            Output: exec:ffmpeg -loglevel quiet -f image2 -loop 1 -framerate 5 -i http://... -c copy -f mjpeg -
        """
        # Get framerate (default: 5 FPS to avoid overwhelming the camera)
        framerate = device.get('framerate', 5)
        username = device.get('username', '')
        password = device.get('password', '')

        # Ensure stream_url is absolute (contains full http:// path)
        # If it's already absolute, use as-is and inject credentials
        if stream_url.startswith('http://') or stream_url.startswith('https://'):
            full_url = self._inject_credentials(stream_url, username, password)
        else:
            # Build absolute URL from device params
            ip = device.get('ip', '')
            port = device.get('port', 80)

            # Build base URL with credentials
            if username and password:
                full_url = f"http://{username}:{password}@{ip}:{port}{stream_url}"
            else:
                full_url = f"http://{ip}:{port}{stream_url}"

        # Build exec:ffmpeg command
        # -loglevel quiet: suppress FFmpeg output
        # -f image2: treat input as image sequence
        # -loop 1: loop the image (re-fetch periodically)
        # -framerate N: fetch N times per second
        # -i URL: input URL
        # -c copy: copy codec (no transcoding)
        # -f mjpeg: output format MJPEG
        # -: output to stdout (pipe to go2rtc)
        return f"exec:ffmpeg -loglevel quiet -f image2 -loop 1 -framerate {framerate} -i {full_url} -c copy -f mjpeg -"

    def generate_go2rtc_config(self, instance_config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate complete go2rtc YAML configuration

        Returns: Configuration dictionary
        """
        config = {
            'log': {
                'level': os.getenv('LOG_LEVEL', 'info').lower(),
                'format': 'json'
            },
            'api': {
                'listen': f":{self.api_port}"
            },
            'rtsp': {
                'listen': f":{self.rtsp_port}",
                'default_query': 'video&audio'
            },
            'webrtc': {
                'listen': f":{self.webrtc_port}"
            },
            'srtp': {
                'listen': f":{self.homekit_port}"
            },
            'streams': {}
        }

        # Process devices
        devices = instance_config.get('devices', [])
        enabled_devices = [d for d in devices if d.get('enabled', True)]

        print(f"📹 Processing {len(enabled_devices)} enabled cameras (of {len(devices)} total)")

        added_count = 0
        skipped_count = 0

        for device in enabled_devices:
            device_id = device.get('device_id', 'unknown')
            device_name = device.get('name', device_id)

            try:
                # Build source URL
                source_url = self.build_go2rtc_source(device)

                if not source_url:
                    print(f"  ❌ {device_id} ({device_name}): Could not build source URL", file=sys.stderr)
                    skipped_count += 1
                    continue

                # Add to streams config
                config['streams'][device_id] = [source_url]

                # Log with sanitized URL (hide credentials)
                safe_url = self._sanitize_url(source_url)
                print(f"  ✅ {device_id} ({device_name}): {safe_url}")
                added_count += 1

            except Exception as e:
                print(f"  ❌ {device_id} ({device_name}): Exception - {e}", file=sys.stderr)
                skipped_count += 1

        print(f"\n📊 Summary: {added_count} added, {skipped_count} skipped")

        return config

    def write_config(self, config: Dict[str, Any], output_path: str = '/app/go2rtc.yaml'):
        """Write go2rtc YAML configuration to file"""
        with open(output_path, 'w') as f:
            yaml.dump(config, f, default_flow_style=False, sort_keys=False)

        print(f"✅ Configuration written to {output_path}")

    @staticmethod
    def _sanitize_url(url: str) -> str:
        """
        Remove credentials from URL for safe logging

        Handles multiple URL formats:
        - rtsp://admin:pass@ip → rtsp://***:***@ip
        - onvif://user:pass@ip → onvif://***:***@ip
        - exec:ffmpeg ... -i http://user:pass@ip/... → exec:ffmpeg ... -i http://***:***@ip/...
        - http://user:pass@ip → http://***:***@ip

        Args:
            url: Source URL (can be rtsp://, http://, onvif://, or exec:ffmpeg command)

        Returns:
            Sanitized URL with credentials replaced by ***
        """
        # For exec commands, sanitize URLs within the command
        if url.startswith('exec:'):
            # Replace credentials in any http:// or https:// URLs within the command
            url = re.sub(r'(https?://)([^:]+):([^@]+)@', r'\1***:***@', url)

        # For standard protocol URLs (rtsp://, onvif://, http://, https://)
        url = re.sub(r'://([^:]+):([^@]+)@', r'://***:***@', url)

        return url

    def run(self) -> int:
        """
        Main execution

        Returns: Exit code (0 = success, 1 = error)
        """
        print(f"🔧 Generating go2rtc configuration for instance: {self.instance_name}")
        print(f"📂 Config path: {self.config_path}")

        try:
            # Load instance config
            instance_config = self.load_instance_config()
            instance_id = instance_config.get('instance_id', self.instance_name)
            connector_type = instance_config.get('connector_type', 'unknown')

            print(f"🎯 Instance ID: {instance_id}")
            print(f"🔌 Connector type: {connector_type}")

            if connector_type != 'cameras':
                print(f"⚠️  Warning: Expected connector_type='cameras', got '{connector_type}'", file=sys.stderr)

            # Generate go2rtc config
            go2rtc_config = self.generate_go2rtc_config(instance_config)

            # Check if any streams were added
            stream_count = len(go2rtc_config.get('streams', {}))
            if stream_count == 0:
                print("⚠️  Warning: No streams configured. go2rtc will start but won't have any cameras.", file=sys.stderr)

            # Write config
            self.write_config(go2rtc_config)

            print(f"\n🚀 Ready to start go2rtc with {stream_count} stream(s)")
            return 0

        except FileNotFoundError as e:
            print(f"❌ Config file error: {e}", file=sys.stderr)
            return 1

        except json.JSONDecodeError as e:
            print(f"❌ Invalid JSON in config file: {e}", file=sys.stderr)
            return 1

        except Exception as e:
            print(f"❌ Unexpected error: {e}", file=sys.stderr)
            import traceback
            traceback.print_exc()
            return 1


def main():
    """Entry point"""
    instance_name = os.getenv('INSTANCE_NAME')

    if not instance_name:
        print("❌ INSTANCE_NAME environment variable not set", file=sys.stderr)
        return 1

    generator = Go2RTCConfigGenerator(instance_name)
    return generator.run()


if __name__ == '__main__':
    sys.exit(main())
