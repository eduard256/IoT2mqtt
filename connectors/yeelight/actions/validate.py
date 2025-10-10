#!/usr/bin/env python3
"""Validate connectivity to a Yeelight device."""

import json
import sys
from typing import Any, Dict

try:
    from yeelight import Bulb
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


def load_payload() -> Dict[str, Any]:
    raw = sys.stdin.read().strip() or "{}"
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    if "input" in payload and isinstance(payload["input"], dict):
        return payload["input"]
    return payload


def main() -> None:
    payload = load_payload()
    host = payload.get("host")

    # Handle empty string or missing port gracefully
    port_value = payload.get("port", 55443)
    if port_value == "" or port_value is None:
        port = 55443
    else:
        try:
            port = int(port_value)
        except (ValueError, TypeError):
            port = 55443

    if not host:
        print(json.dumps({
            "ok": False,
            "error": {
                "code": "missing_parameter",
                "message": "host is required",
                "retriable": False
            }
        }))
        return

    try:
        bulb = Bulb(host, port=port)
        properties = bulb.get_properties()
    except Exception as exc:  # pragma: no cover
        print(json.dumps({
            "ok": False,
            "error": {
                "code": "validation_failed",
                "message": str(exc),
                "retriable": True
            }
        }))
        return

    print(json.dumps({
        "ok": True,
        "result": {
            "host": host,
            "port": port,
            "properties": properties
        }
    }))


if __name__ == '__main__':
    main()
