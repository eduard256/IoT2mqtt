#!/usr/bin/env python3
"""
Auto-generate instance_id, device_id, friendly_name and device_name
for Xiaomi MiIO manual setup flows.

Input (stdin JSON or {"input":{...}} envelope):
{
  "integration": "xiaomi_miio",
  "display_name": "Xiaomi MiIO",
  "host": "192.168.1.101",
  "model": "zhimi.airpurifier.ma4"
}

Output:
{
  "ok": true,
  "result": {
    "instance_id": "xiaomi_miio_zhimi_airpurifier_ma4_192_168_1_101",
    "device_id": "xiaomi_miio_zhimi_airpurifier_ma4_192_168_1_101",
    "friendly_name": "Xiaomi MiIO",
    "device_name": "Xiaomi MiIO zhimi.airpurifier.ma4",
    "model": "zhimi.airpurifier.ma4"
  }
}
"""

import json
import sys
import re


def _print(obj):
    sys.stdout.write(json.dumps(obj))
    sys.stdout.flush()


def slugify(value: str) -> str:
    if value is None:
        return ""
    s = str(value).lower()
    s = s.replace(" ", "_")
    s = re.sub(r"[^a-z0-9_-]", "", s)
    return s


def main():
    try:
        raw = sys.stdin.read().strip() or "{}"
        payload = json.loads(raw)
        data = payload.get("input", payload)

        integration = data.get("integration") or "xiaomi_miio"
        display_name = data.get("display_name") or "Xiaomi MiIO"
        host = (data.get("host") or "").strip()
        model = (data.get("model") or "unknown").strip()

        host_part = slugify(host.replace(".", "_")) or "device"
        model_part = slugify(model.replace(".", "_")) or "unknown"
        integration_part = slugify(integration) or "integration"

        instance_id = f"{integration_part}_{model_part}_{host_part}" if model_part != "unknown" else f"{integration_part}_{host_part}"
        device_id = instance_id

        friendly_name = display_name or integration
        device_name = f"{friendly_name} {model}" if model and model != "unknown" else friendly_name

        return _print({
            "ok": True,
            "result": {
                "instance_id": instance_id,
                "device_id": device_id,
                "friendly_name": friendly_name,
                "device_name": device_name,
                "model": model or "unknown"
            }
        })

    except Exception as e:
        return _print({"ok": False, "error": {"code": "unexpected_error", "message": str(e), "retriable": False}})


if __name__ == "__main__":
    main()

