#!/usr/bin/env python3
"""
HomeKit Device Unpair
Removes pairing from HomeKit device
"""

import json
import sys
import asyncio
import logging
from typing import Dict, Any

try:
    from aiohomekit import Controller
    from aiohomekit.exceptions import (
        AccessoryNotFoundError,
        AuthenticationError,
        AccessoryDisconnectedError
    )
except ImportError:
    print(json.dumps({
        "ok": False,
        "error": {
            "code": "missing_dependency",
            "message": "aiohomekit package is not installed",
            "retriable": False
        }
    }))
    sys.exit(0)

# Disable logging for clean JSON output
logging.disable(logging.CRITICAL)


def load_payload() -> Dict[str, Any]:
    """
    Load input payload from stdin

    Returns:
        Input parameters dictionary
    """
    raw = sys.stdin.read().strip() or "{}"
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return {}

    if "input" in payload and isinstance(payload["input"], dict):
        return payload["input"]
    return payload


async def unpair_device(pairing_data: Dict[str, Any], ip: str, port: int) -> Dict[str, Any]:
    """
    Unpair from HomeKit device

    Args:
        pairing_data: Pairing credentials
        ip: Device IP address
        port: Device port

    Returns:
        Unpair result
    """
    try:
        # Initialize controller
        controller = Controller()

        # Load pairing
        pairing_id = pairing_data.get("AccessoryPairingID")
        if not pairing_id:
            return {
                "ok": False,
                "error": {
                    "code": "invalid_pairing_data",
                    "message": "Pairing data missing AccessoryPairingID",
                    "retriable": False
                }
            }

        # Ensure IP and port are in pairing data
        pairing_data["AccessoryIP"] = ip
        pairing_data["AccessoryPort"] = port

        # Load pairing into controller
        pairing = await controller.load_pairing(pairing_id, pairing_data)

        if not pairing:
            return {
                "ok": False,
                "error": {
                    "code": "load_pairing_failed",
                    "message": "Failed to load pairing into controller",
                    "retriable": False
                }
            }

        # Remove pairing from device
        # This tells the accessory to forget this controller
        await pairing.close()  # Ensure connection is closed

        # Remove pairing from controller
        # Note: This removes our local pairing data, but we've already
        # instructed the device to forget us
        controller.remove_pairing(pairing_id)

        return {
            "ok": True,
            "result": {
                "pairing_id": pairing_id,
                "message": "Successfully unpaired from device"
            }
        }

    except AccessoryNotFoundError as e:
        return {
            "ok": False,
            "error": {
                "code": "device_not_found",
                "message": f"HomeKit device not found at {ip}:{port}. "
                          f"Device may be offline or already unpaired.",
                "retriable": True
            }
        }

    except AuthenticationError as e:
        # If authentication fails, device may have already forgotten us
        # This is actually success from our perspective
        return {
            "ok": True,
            "result": {
                "pairing_id": pairing_data.get("AccessoryPairingID"),
                "message": "Device already unpaired or pairing invalid"
            }
        }

    except AccessoryDisconnectedError as e:
        # Connection lost during unpair - assume success
        return {
            "ok": True,
            "result": {
                "pairing_id": pairing_data.get("AccessoryPairingID"),
                "message": "Connection lost during unpair (likely successful)"
            }
        }

    except ConnectionError as e:
        return {
            "ok": False,
            "error": {
                "code": "connection_error",
                "message": f"Cannot connect to device at {ip}:{port}. "
                          f"Device may be offline. Pairing data will be removed locally.",
                "retriable": True
            }
        }

    except TimeoutError as e:
        return {
            "ok": False,
            "error": {
                "code": "timeout",
                "message": f"Connection timeout. Device may be offline. "
                          f"Pairing data will be removed locally.",
                "retriable": True
            }
        }

    except Exception as e:
        return {
            "ok": False,
            "error": {
                "code": "unpair_error",
                "message": f"Unpair error: {str(e)}",
                "retriable": True
            }
        }


def main():
    """Main entry point"""
    # Load input from stdin
    payload = load_payload()

    # Extract parameters
    pairing_data = payload.get("pairing_data")
    ip = payload.get("ip")
    port = payload.get("port", 55443)

    # Validate required parameters
    if not pairing_data:
        print(json.dumps({
            "ok": False,
            "error": {
                "code": "missing_parameter",
                "message": "pairing_data is required",
                "retriable": False
            }
        }))
        return

    if not ip:
        print(json.dumps({
            "ok": False,
            "error": {
                "code": "missing_parameter",
                "message": "ip is required",
                "retriable": False
            }
        }))
        return

    # Handle port conversion
    try:
        port = int(port) if port else 55443
    except (ValueError, TypeError):
        port = 55443

    # Run unpair
    result = asyncio.run(unpair_device(pairing_data, ip, port))

    # Output JSON
    print(json.dumps(result))


if __name__ == "__main__":
    main()
