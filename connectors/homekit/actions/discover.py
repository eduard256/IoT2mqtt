#!/usr/bin/env python3
"""Discover HomeKit accessories on the local network."""

import json
import sys
import asyncio
from typing import Any, Dict, List

try:
    from aiohomekit import Controller
    from zeroconf.asyncio import AsyncZeroconf
except ImportError:
    print(json.dumps({
        "ok": False,
        "error": {
            "code": "missing_dependency",
            "message": "aiohomekit or zeroconf package is not installed",
            "retriable": False
        }
    }))
    sys.exit(0)


async def discover_homekit_devices(timeout: int = 10) -> List[Dict[str, Any]]:
    """
    Discover HomeKit accessories using Zeroconf/mDNS

    Args:
        timeout: Discovery timeout in seconds

    Returns:
        List of discovered devices
    """
    controller = Controller()
    devices = []

    try:
        async with AsyncZeroconf() as aiozc:
            discoveries = await controller.discover(timeout, aiozc=aiozc)

            for device in discoveries:
                device_info = {
                    "device_id": device.id,  # Pairing ID
                    "pairing_id": device.id,
                    "name": device.name,
                    "model": device.model or "Unknown",
                    "category": device.category_name or "Unknown",
                    "status_flags": device.status_flags,
                    "config_num": device.config_num,
                    "state_num": device.state_num,
                    "ip": device.address,
                    "port": device.port,
                    "feature_flags": device.feature_flags,
                    "protocol_version": device.protocol_version
                }
                devices.append(device_info)

    except Exception as exc:
        raise exc

    return devices


def main() -> None:
    """Main entry point"""
    timeout = int(sys.argv[1]) if len(sys.argv) > 1 else 10

    try:
        # Run async discovery
        devices = asyncio.run(discover_homekit_devices(timeout=timeout))

        print(json.dumps({
            "ok": True,
            "result": {
                "count": len(devices),
                "devices": devices
            }
        }))

    except Exception as exc:
        print(json.dumps({
            "ok": False,
            "error": {
                "code": "discovery_failed",
                "message": str(exc),
                "retriable": True
            }
        }))


if __name__ == '__main__':
    main()
