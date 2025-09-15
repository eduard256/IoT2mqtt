#!/usr/bin/env python3
"""
Fetch token and details for a specific device DID via Xiaomi Cloud.
Input (stdin JSON): {"username","password","country","did"}
Output: {"ok": true, "result": {"token","model","name","localip","mac"}}
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

        username = data.get("username")
        password = data.get("password")
        country = data.get("country", "cn")
        did = data.get("did")

        if not (username and password and did):
            return _print({"ok": False, "error": {"code": "invalid_input", "message": "username/password/did required", "retriable": False}})

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
            all_devices = cloud.get_devices(country)
        except Exception as e:
            return _print({"ok": False, "error": {"code": "cloud_devices_error", "message": str(e), "retriable": True}})

        target = None
        for d in all_devices or []:
            if d.get("did") == did:
                target = d
                break

        if not target:
            return _print({"ok": False, "error": {"code": "device_not_found", "message": f"DID {did} not found", "retriable": False}})

        result = {
            "token": target.get("token"),
            "model": target.get("model"),
            "name": target.get("name"),
            "localip": target.get("localip"),
            "mac": target.get("mac"),
            "did": target.get("did")
        }

        if not result.get("token"):
            return _print({"ok": False, "error": {"code": "token_unavailable", "message": "Token not available from cloud for this device", "retriable": False}})

        return _print({"ok": True, "result": result})

    except Exception as e:
        return _print({"ok": False, "error": {"code": "unexpected_error", "message": str(e), "retriable": False}})

if __name__ == "__main__":
    main()

