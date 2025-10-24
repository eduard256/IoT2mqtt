#!/usr/bin/env python3
"""Pair with a HomeKit accessory."""

import json
import sys
import asyncio
from typing import Any, Dict, Optional

try:
    from aiohomekit import Controller
    from aiohomekit.exceptions import AuthenticationError, AccessoryNotFoundError
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


async def pair_homekit_device(
    device_id: str,
    pairing_id: str,
    pin: str,
    ip: str,
    port: Optional[int] = None
) -> Dict[str, Any]:
    """
    Pair with a HomeKit accessory

    Args:
        device_id: Internal device identifier
        pairing_id: HomeKit pairing ID
        pin: PIN code (format: xxx-xx-xxx)
        ip: Device IP address
        port: Device port (optional)

    Returns:
        Pairing data dictionary

    Raises:
        AuthenticationError: Invalid PIN or pairing rejected
        AccessoryNotFoundError: Device not reachable
        Exception: Other pairing errors
    """
    controller = Controller()

    try:
        # Start pairing
        pairing = await controller.start_pairing(pairing_id, ip, port)

        # Finish pairing with PIN
        pairing_data = await pairing.finish_pairing(device_id, pin)

        return pairing_data

    except AuthenticationError as e:
        raise AuthenticationError(f"Authentication failed. Please check PIN code: {e}")
    except AccessoryNotFoundError as e:
        raise AccessoryNotFoundError(f"Accessory not found at {ip}:{port}. Check IP address and network: {e}")
    except Exception as e:
        raise Exception(f"Pairing failed: {e}")


def main() -> None:
    """Main entry point"""
    if len(sys.argv) < 5:
        print(json.dumps({
            "ok": False,
            "error": {
                "code": "invalid_arguments",
                "message": "Usage: pair.py <device_id> <pairing_id> <pin> <ip> [port]",
                "retriable": False
            }
        }))
        sys.exit(1)

    device_id = sys.argv[1]
    pairing_id = sys.argv[2]
    pin = sys.argv[3]
    ip = sys.argv[4]
    port = int(sys.argv[5]) if len(sys.argv) > 5 else None

    try:
        # Run async pairing
        pairing_data = asyncio.run(pair_homekit_device(
            device_id=device_id,
            pairing_id=pairing_id,
            pin=pin,
            ip=ip,
            port=port
        ))

        print(json.dumps({
            "ok": True,
            "result": {
                "pairing_data": pairing_data,
                "device_id": device_id,
                "pairing_id": pairing_id
            }
        }))

    except AuthenticationError as exc:
        print(json.dumps({
            "ok": False,
            "error": {
                "code": "authentication_failed",
                "message": str(exc),
                "retriable": True
            }
        }))
    except AccessoryNotFoundError as exc:
        print(json.dumps({
            "ok": False,
            "error": {
                "code": "accessory_not_found",
                "message": str(exc),
                "retriable": True
            }
        }))
    except Exception as exc:
        print(json.dumps({
            "ok": False,
            "error": {
                "code": "pairing_failed",
                "message": str(exc),
                "retriable": True
            }
        }))


if __name__ == '__main__':
    main()
