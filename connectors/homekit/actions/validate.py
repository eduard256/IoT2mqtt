#!/usr/bin/env python3
"""
HomeKit Pairing Validation
Validates pairing by connecting and retrieving accessories structure
"""

import json
import sys
import asyncio
import logging
from typing import Dict, Any, List

try:
    from aiohomekit import Controller
    from aiohomekit.model import Accessory
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


def serialize_accessories(accessories: List[Accessory]) -> List[Dict[str, Any]]:
    """
    Serialize accessories to JSON-compatible format

    Args:
        accessories: List of Accessory objects from aiohomekit

    Returns:
        List of serialized accessory dictionaries
    """
    result = []

    for accessory in accessories:
        acc_data = {
            "aid": accessory.aid,
            "services": []
        }

        for service in accessory.services:
            svc_data = {
                "iid": service.iid,
                "type": service.type,
                "characteristics": []
            }

            for characteristic in service.characteristics:
                char_data = {
                    "iid": characteristic.iid,
                    "type": characteristic.type,
                    "description": characteristic.description,
                    "format": characteristic.format,
                    "perms": characteristic.perms
                }

                # Add value if readable
                if 'pr' in characteristic.perms:
                    char_data["value"] = characteristic.value

                # Add optional metadata
                if hasattr(characteristic, 'minValue') and characteristic.minValue is not None:
                    char_data["minValue"] = characteristic.minValue
                if hasattr(characteristic, 'maxValue') and characteristic.maxValue is not None:
                    char_data["maxValue"] = characteristic.maxValue
                if hasattr(characteristic, 'minStep') and characteristic.minStep is not None:
                    char_data["minStep"] = characteristic.minStep
                if hasattr(characteristic, 'unit') and characteristic.unit is not None:
                    char_data["unit"] = characteristic.unit
                if hasattr(characteristic, 'valid_values') and characteristic.valid_values:
                    char_data["valid_values"] = characteristic.valid_values
                if hasattr(characteristic, 'valid_values_range') and characteristic.valid_values_range:
                    char_data["valid_values_range"] = characteristic.valid_values_range

                svc_data["characteristics"].append(char_data)

            acc_data["services"].append(svc_data)

        result.append(acc_data)

    return result


def extract_device_info(accessories: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Extract device information from accessories

    Args:
        accessories: Serialized accessories list

    Returns:
        Device metadata
    """
    info = {
        "model": "Unknown",
        "manufacturer": "Unknown",
        "serial_number": "Unknown",
        "firmware_version": "Unknown",
        "category": "Other"
    }

    # Look for ACCESSORY_INFORMATION service
    # Service type: "0000003E-0000-1000-8000-0026BB765291"
    for accessory in accessories:
        for service in accessory.get("services", []):
            service_type = service.get("type", "")

            # Check if this is ACCESSORY_INFORMATION service
            if "0000003e" in service_type.lower():
                for char in service.get("characteristics", []):
                    char_type = char.get("type", "").lower()

                    # Model: 00000021
                    if "00000021" in char_type:
                        info["model"] = char.get("value", "Unknown")

                    # Manufacturer: 00000020
                    elif "00000020" in char_type:
                        info["manufacturer"] = char.get("value", "Unknown")

                    # Serial Number: 00000030
                    elif "00000030" in char_type:
                        info["serial_number"] = char.get("value", "Unknown")

                    # Firmware Revision: 00000052
                    elif "00000052" in char_type:
                        info["firmware_version"] = char.get("value", "Unknown")

                break

    return info


async def validate_pairing(pairing_data: Dict[str, Any], ip: str, port: int) -> Dict[str, Any]:
    """
    Validate pairing by connecting and retrieving accessories

    Args:
        pairing_data: Pairing credentials from pair.py
        ip: Device IP address
        port: Device port

    Returns:
        Validation result with accessories structure
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

        # Get accessories and characteristics
        accessories = await pairing.list_accessories_and_characteristics()

        if not accessories:
            return {
                "ok": False,
                "error": {
                    "code": "no_accessories",
                    "message": "No accessories found on device",
                    "retriable": True
                }
            }

        # Serialize accessories
        accessories_serialized = serialize_accessories(accessories)

        # Extract device info
        device_info = extract_device_info(accessories_serialized)

        # Close connection
        await pairing.close()

        # Build result
        result = {
            "accessories": accessories_serialized,
            "accessories_count": len(accessories_serialized),
            "model": device_info["model"],
            "manufacturer": device_info["manufacturer"],
            "serial_number": device_info["serial_number"],
            "firmware_version": device_info["firmware_version"],
            "category": device_info["category"]
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
                          f"Device may be offline or IP changed.",
                "retriable": True
            }
        }

    except AuthenticationError as e:
        return {
            "ok": False,
            "error": {
                "code": "authentication_failed",
                "message": f"Authentication failed. Pairing data may be invalid or expired. "
                          f"Please re-pair the device.",
                "retriable": False
            }
        }

    except AccessoryDisconnectedError as e:
        return {
            "ok": False,
            "error": {
                "code": "connection_lost",
                "message": f"Connection to device lost during validation. "
                          f"Please check network and try again.",
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
                "code": "validation_error",
                "message": f"Validation error: {str(e)}",
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

    # Run validation
    result = asyncio.run(validate_pairing(pairing_data, ip, port))

    # Output JSON
    print(json.dumps(result))


if __name__ == "__main__":
    main()
