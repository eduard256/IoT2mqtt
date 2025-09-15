#!/usr/bin/env python3
"""
Validate device connection using python-miio.
Input: {"host","token"}
Output: {"ok": true, "result": {"model","mac","firmware"}} or error.
"""
import json
import sys

def _print(obj):
    sys.stdout.write(json.dumps(obj))
    sys.stdout.flush()

def main():
    try:
        raw = sys.stdin.read().strip() or "{}"
        payload = json.loads(raw)
        data = payload.get("input", payload)

        host = data.get("host")
        token = data.get("token")

        if not host or not token:
            return _print({"ok": False, "error": {"code": "invalid_input", "message": "host/token required", "retriable": False}})

        try:
            from miio import Device
        except Exception as e:
            return _print({"ok": False, "error": {"code": "missing_dependency", "message": f"python-miio not available: {e}", "retriable": False}})

        try:
            dev = Device(host, token)
            info = dev.info()
            result = {
                "model": getattr(info, "model", None),
                "mac": getattr(info, "mac_address", None),
                "firmware": getattr(info, "firmware_version", None)
            }
            return _print({"ok": True, "result": result})
        except Exception as e:
            return _print({"ok": False, "error": {"code": "connection_failed", "message": str(e), "retriable": True}})

    except Exception as e:
        return _print({"ok": False, "error": {"code": "unexpected_error", "message": str(e), "retriable": False}})

if __name__ == "__main__":
    main()

