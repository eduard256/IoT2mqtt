#!/usr/bin/env python3
"""
List Xiaomi cloud devices for an account.
Reads JSON from stdin: {"username":..., "password":..., "country":...}
Writes JSON to stdout: {"ok": true, "result": {"devices": [...]}} or {"ok": false, "error": {...}}
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
        # Support envelope {input: {...}}
        data = payload.get("input", payload)

        username = data.get("username")
        password = data.get("password")
        country = data.get("country", "cn")

        if not username or not password:
            return _print({"ok": False, "error": {"code": "invalid_input", "message": "username/password required", "retriable": False}})

        try:
            from micloud import MiCloud
        except Exception as e:
            return _print({"ok": False, "error": {"code": "missing_dependency", "message": f"micloud not available: {e}", "retriable": False}})

        cloud = MiCloud(username, password)
        try:
            if not cloud.login():
                return _print({"ok": False, "error": {"code": "cloud_login_error", "message": "Invalid credentials or 2FA required", "retriable": True}})
        except Exception as e:
            return _print({"ok": False, "error": {"code": "cloud_login_exception", "message": str(e), "retriable": True}})

        try:
            raw_devices = cloud.get_devices(country)
        except Exception as e:
            return _print({"ok": False, "error": {"code": "cloud_devices_error", "message": str(e), "retriable": True}})

        devices = []
        for d in raw_devices or []:
            # Skip subdevices
            if d.get("parent_id"):
                continue
            devices.append({
                "did": d.get("did"),
                "name": d.get("name"),
                "model": d.get("model"),
                "localip": d.get("localip"),
                "token": d.get("token"),
                "mac": d.get("mac")
            })

        if not devices:
            return _print({"ok": False, "error": {"code": "cloud_no_devices", "message": "No devices found for this account/region", "retriable": False}})

        return _print({"ok": True, "result": {"devices": devices}})

    except Exception as e:
        return _print({"ok": False, "error": {"code": "unexpected_error", "message": str(e), "retriable": False}})

if __name__ == "__main__":
    main()

