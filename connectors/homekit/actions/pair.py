#!/usr/bin/env python3
"""
HomeKit Device Pairing
Performs SRP-6a pairing with HomeKit device using PIN code
"""

import json
import sys
import asyncio
import logging
import base64
from typing import Dict, Any

try:
    from aiohomekit import Controller
    from aiohomekit.controller.ip.discovery import IpDiscovery
    from aiohomekit.zeroconf import HomeKitService
    from aiohomekit.model.categories import Categories
    from aiohomekit.model.feature_flags import FeatureFlags
    from aiohomekit.model.status_flags import StatusFlags
    from aiohomekit.exceptions import (
        AccessoryNotFoundError,
        AuthenticationError,
        MaxPeersError,
        MaxTriesError
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


# Insecure PIN codes (from HAP spec - must be rejected)
INSECURE_CODES = [
    "00000000", "11111111", "22222222", "33333333", "44444444",
    "55555555", "66666666", "77777777", "88888888", "99999999",
    "12345678", "87654321"
]


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


def validate_pin_code(pin_code: str) -> tuple[bool, str]:
    """
    Validate HomeKit PIN code

    Args:
        pin_code: PIN code string

    Returns:
        Tuple of (is_valid, error_message)
    """
    # Remove dashes if present
    pin_clean = pin_code.replace('-', '')

    # Check length
    if len(pin_clean) != 8:
        return False, "PIN code must be 8 digits"

    # Check if all digits
    if not pin_clean.isdigit():
        return False, "PIN code must contain only digits"

    # Check if insecure
    if pin_clean in INSECURE_CODES:
        return False, f"PIN code {pin_code} is not secure and cannot be used"

    return True, ""


async def pair_device(ip: str, port: int, pin_code: str, device_id: str = None) -> Dict[str, Any]:
    """
    Pair with HomeKit device

    Args:
        ip: Device IP address
        port: Device port (default 55443)
        pin_code: 8-digit PIN code
        device_id: Optional device identifier

    Returns:
        Pairing result with credentials
    """
    controller = None
    try:
        # Validate PIN code
        is_valid, error_msg = validate_pin_code(pin_code)
        if not is_valid:
            return {
                "ok": False,
                "error": {
                    "code": "invalid_pin",
                    "message": error_msg,
                    "retriable": False
                }
            }

        # Normalize PIN format (remove dashes)
        pin_clean = pin_code.replace('-', '')

        # Initialize controller
        controller = Controller()

        # Create a minimal HomeKitService descriptor for manual IP entry
        # This bypasses the need for zeroconf discovery
        service = HomeKitService(
            name=f"HomeKit Device at {ip}",
            id=device_id or f"manual-{ip.replace('.', '-')}",
            model="Unknown",
            feature_flags=FeatureFlags(),
            status_flags=StatusFlags(),
            config_num=1,
            state_num=1,
            category=Categories.OTHER,
            protocol_version="1.1",
            type="_hap._tcp.local.",
            address=ip,
            addresses=[ip],
            port=port
        )

        # Create IpDiscovery object directly without using async_find
        discovery = IpDiscovery(controller, service)

        # Start pairing process
        # This performs SRP-6a key exchange (part 1)
        finish_pairing = await discovery.async_start_pairing()

        # Complete pairing with PIN code
        # This performs:
        # 1. SRP-6a key exchange (part 2)
        # 2. Ed25519 keypair generation
        # 3. Authentication
        # 4. Exchange of long-term keys
        pairing = await finish_pairing(pin_clean)

        if not pairing:
            return {
                "ok": False,
                "error": {
                    "code": "pairing_failed",
                    "message": "Failed to pair with device",
                    "retriable": True
                }
            }

        # Get pairing data from the pairing object
        # In aiohomekit, pairing data is stored in controller.pairings
        pairing_data = None
        for alias, p in controller.pairings.items():
            if p == pairing:
                pairing_data = p.pairing_data
                break

        if not pairing_data:
            return {
                "ok": False,
                "error": {
                    "code": "missing_pairing_data",
                    "message": "Pairing succeeded but no pairing data available",
                    "retriable": False
                }
            }

        # Extract pairing ID
        pairing_id = pairing_data.get("AccessoryPairingID")
        if not pairing_id:
            return {
                "ok": False,
                "error": {
                    "code": "missing_pairing_id",
                    "message": "Pairing succeeded but no pairing ID received",
                    "retriable": False
                }
            }

        # Build response
        result = {
            "pairing_id": pairing_id,
            "device_id": device_id or pairing_id.replace(':', '_'),
            "pairing_data": {
                "AccessoryPairingID": pairing_id,
                "AccessoryLTPK": pairing_data.get("AccessoryLTPK"),
                "iOSDevicePairingID": pairing_data.get("iOSDevicePairingID"),
                "iOSDeviceLTPK": pairing_data.get("iOSDeviceLTPK"),
                "iOSDeviceLTSK": pairing_data.get("iOSDeviceLTSK"),  # SECRET!
                "AccessoryIP": ip,
                "AccessoryPort": port,
                "Connection": "IP"
            }
        }

        return {
            "ok": True,
            "result": result
        }

    except AccessoryNotFoundError as e:
        return {
            "ok": False,
            "error": {
                "code": "device_not_found",
                "message": f"HomeKit device not found at {ip}:{port}. "
                          f"Please check IP address and ensure device is powered on.",
                "retriable": True
            }
        }

    except AuthenticationError as e:
        return {
            "ok": False,
            "error": {
                "code": "authentication_failed",
                "message": f"Authentication failed. Please check PIN code. "
                          f"Error: {str(e)}",
                "retriable": True
            }
        }

    except MaxPeersError as e:
        return {
            "ok": False,
            "error": {
                "code": "max_peers",
                "message": "Device has reached maximum number of paired controllers. "
                          "Please unpair from another controller first (e.g., Apple Home app).",
                "retriable": False
            }
        }

    except MaxTriesError as e:
        return {
            "ok": False,
            "error": {
                "code": "max_tries",
                "message": "Too many pairing attempts. Please wait a few minutes and try again.",
                "retriable": True
            }
        }

    except ConnectionError as e:
        return {
            "ok": False,
            "error": {
                "code": "connection_error",
                "message": f"Cannot connect to device at {ip}:{port}. "
                          f"Please check network connectivity.",
                "retriable": True
            }
        }

    except TimeoutError as e:
        return {
            "ok": False,
            "error": {
                "code": "timeout",
                "message": f"Connection timeout. Device may be offline or unreachable.",
                "retriable": True
            }
        }

    except Exception as e:
        return {
            "ok": False,
            "error": {
                "code": "pairing_error",
                "message": f"Pairing error: {str(e)}",
                "retriable": True
            }
        }


def main():
    """Main entry point"""
    # Load input from stdin
    payload = load_payload()

    # Extract parameters
    ip = payload.get("ip")
    port = payload.get("port", 55443)
    pin_code = payload.get("pin_code")
    device_id = payload.get("device_id")

    # Validate required parameters
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

    if not pin_code:
        print(json.dumps({
            "ok": False,
            "error": {
                "code": "missing_parameter",
                "message": "pin_code is required",
                "retriable": False
            }
        }))
        return

    # Handle port conversion
    try:
        port = int(port) if port else 55443
    except (ValueError, TypeError):
        port = 55443

    # Run pairing
    result = asyncio.run(pair_device(ip, port, pin_code, device_id))

    # Output JSON
    print(json.dumps(result))


if __name__ == "__main__":
    main()
