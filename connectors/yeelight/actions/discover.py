#!/usr/bin/env python3
"""Discover Yeelight devices on the local network."""

import json
import sys
from typing import Any, Dict, List

try:
    from yeelight import discover_bulbs
except ImportError:  # pragma: no cover
    print(json.dumps({
        "ok": False,
        "error": {
            "code": "missing_dependency",
            "message": "yeelight package is not installed",
            "retriable": False
        }
    }))
    sys.exit(0)


def normalize_device(raw: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize raw yeelight discovery payload."""
    return {
        "device_id": raw.get("capabilities", {}).get("id") or raw.get("id") or raw.get("ip"),
        "ip": raw.get("ip"),
        "model": raw.get("capabilities", {}).get("model") or raw.get("model"),
        "friendly_name": raw.get("capabilities", {}).get("name") or raw.get("name") or raw.get("ip"),
        "port": raw.get("port", 55443),
        "ssid": raw.get("capabilities", {}).get("ssid"),
        "properties": raw.get("capabilities", {})
    }


def main() -> None:
    timeout = int(sys.argv[1]) if len(sys.argv) > 1 else 5
    try:
        bulbs: List[Dict[str, Any]] = discover_bulbs(timeout=timeout)
    except Exception as exc:  # pragma: no cover
        print(json.dumps({
            "ok": False,
            "error": {
                "code": "discovery_failed",
                "message": str(exc),
                "retriable": True
            }
        }))
        return

    devices = [normalize_device(device) for device in bulbs]
    print(json.dumps({
        "ok": True,
        "result": {
            "count": len(devices),
            "devices": devices
        }
    }))


if __name__ == '__main__':
    main()
