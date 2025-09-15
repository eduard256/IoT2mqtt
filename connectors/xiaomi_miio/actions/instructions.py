#!/usr/bin/env python3
"""
Return human-readable token retrieval instructions.
Input: {"method": "cloud"|"mi_home_backup"|"sniffing"}
"""
import json
import sys

INSTRUCTIONS = {
    "cloud": [
        "Enter Xiaomi account email and password, select region, and list devices.",
        "Pick your device, then fetch token automatically.",
        "If token is missing in cloud, try another method."
    ],
    "mi_home_backup": [
        "Android: adb backup -noapk com.xiaomi.smarthome",
        "Extract backup and find token in the database (search for 'token').",
        "Paste the 32-hex token into manual setup."
    ],
    "sniffing": [
        "Reset device to AP mode and use a packet sniffer during pairing.",
        "Capture MiIO handshake and extract token from payload.",
        "Use the token in manual setup."
    ]
}

def _print(obj):
    sys.stdout.write(json.dumps(obj))
    sys.stdout.flush()

def main():
    try:
        raw = sys.stdin.read().strip() or "{}"
        payload = json.loads(raw)
        data = payload.get("input", payload)
        method = (data.get("method") or "cloud").lower()
        steps = INSTRUCTIONS.get(method, INSTRUCTIONS["cloud"])
        _print({"ok": True, "result": {"method": method, "steps": steps}})
    except Exception as e:
        _print({"ok": False, "error": {"code": "unexpected_error", "message": str(e), "retriable": False}})

if __name__ == "__main__":
    main()

