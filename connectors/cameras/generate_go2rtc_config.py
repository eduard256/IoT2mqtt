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


class Go2RTCConfigGenerator:
    """Generate go2rtc YAML config from IoT2mqtt cameras instance"""

    def __init__(self, instance_name: str):
        self.instance_name = instance_name
        self.config_path = f"/app/instances/{instance_name}.json"

        # Read ports from env (with defaults)
        self.api_port = os.getenv('GO2RTC_API_PORT', '1984')
        self.rtsp_port = os.getenv('GO2RTC_RTSP_PORT', '8554')
        self.webrtc_port = os.getenv('GO2RTC_WEBRTC_PORT', '8555')

    def load_instance_config(self) -> Dict[str, Any]:
        """Load IoT2mqtt instance configuration"""
        if not os.path.exists(self.config_path):
            raise FileNotFoundError(f"Instance config not found: {self.config_path}")

        with open(self.config_path, 'r') as f:
            return json.load(f)

    def build_go2rtc_source(self, device: Dict[str, Any]) -> Optional[str]:
        """
        Build go2rtc source URL from device config

        Supports: FFMPEG (RTSP), JPEG, MJPEG, ONVIF, HTTP

        Returns: Source URL string or None if invalid
        """
        stream_type = device.get('stream_type', 'FFMPEG')
        stream_url = device.get('stream_url', '')
        device_id = device.get('device_id', 'unknown')

        if stream_type == 'FFMPEG':
            # Direct RTSP URL
            if not stream_url:
                print(f"  ⚠️  {device_id}: Missing stream_url for FFMPEG type", file=sys.stderr)
                return None
            return stream_url

        elif stream_type in ['JPEG', 'MJPEG', 'HTTP']:
            # HTTP sources (go2rtc handles them natively)
            if not stream_url:
                print(f"  ⚠️  {device_id}: Missing stream_url for {stream_type} type", file=sys.stderr)
                return None
            return stream_url

        elif stream_type == 'ONVIF':
            # Build ONVIF URL: onvif://user:pass@ip:port
            ip = device.get('ip')
            if not ip:
                print(f"  ⚠️  {device_id}: Missing IP address for ONVIF type", file=sys.stderr)
                return None

            port = device.get('port', 80)
            username = device.get('username', 'admin')
            password = device.get('password', '')

            return f"onvif://{username}:{password}@{ip}:{port}"

        else:
            print(f"  ⚠️  {device_id}: Unknown stream_type '{stream_type}', using stream_url as-is", file=sys.stderr)
            return stream_url if stream_url else None

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

        Examples:
          rtsp://admin:pass@ip → rtsp://***:***@ip
          onvif://user:pass@ip → onvif://***:***@ip
        """
        return re.sub(r'://([^:]+):([^@]+)@', r'://***:***@', url)

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
