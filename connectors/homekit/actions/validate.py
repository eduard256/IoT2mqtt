#!/usr/bin/env python3
"""Validate HomeKit pairing."""

import json
import sys
import asyncio
from typing import Any, Dict

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


async def validate_pairing(pairing_data: Dict[str, Any]) -> bool:
    """
    Validate that pairing data is valid and device is reachable

    Args:
        pairing_data: Pairing data dictionary

    Returns:
        True if pairing is valid, False otherwise
    """
    controller = Controller()

    try:
        # Load pairing
        device_id = pairing_data.get('iOSDevicePairingID', 'validate_test')
        pairing = await controller.load_pairing(device_id, pairing_data)

        # Try to get accessories (tests connection and authentication)
        accessories = await pairing.list_accessories_and_characteristics()

        # If we got here, pairing is valid
        return len(accessories) > 0

    except AuthenticationError:
        # Pairing data is invalid or expired
        return False
    except AccessoryNotFoundError:
        # Device not reachable (might be offline, but pairing data could be valid)
        # We'll consider this as invalid for now
        return False
    except Exception:
        # Any other error means pairing is not working
        return False


def main() -> None:
    """Main entry point"""
    if len(sys.argv) < 2:
        print(json.dumps({
            "ok": False,
            "error": {
                "code": "invalid_arguments",
                "message": "Usage: validate.py <pairing_data_json>",
                "retriable": False
            }
        }))
        sys.exit(1)

    try:
        # Parse pairing data from argument
        pairing_data = json.loads(sys.argv[1])

        # Run async validation
        is_valid = asyncio.run(validate_pairing(pairing_data))

        print(json.dumps({
            "ok": True,
            "result": {
                "valid": is_valid
            }
        }))

    except json.JSONDecodeError as exc:
        print(json.dumps({
            "ok": False,
            "error": {
                "code": "invalid_json",
                "message": f"Invalid JSON: {exc}",
                "retriable": False
            }
        }))
    except Exception as exc:
        print(json.dumps({
            "ok": False,
            "error": {
                "code": "validation_failed",
                "message": str(exc),
                "retriable": True
            }
        }))


if __name__ == '__main__':
    main()
