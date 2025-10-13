#!/usr/bin/env python3
"""
Configuration Validation Action

This action script validates the sensor hub configuration for internal consistency.
It runs during the setup flow before deployment to catch configuration errors early.

Validation checks:
- Sensor IDs are unique
- Sensor types are valid
- Required fields are present
- Configuration is internally consistent
"""

import json
import sys
from typing import Dict, Any, List


def load_payload() -> Dict[str, Any]:
    """Load input payload from stdin"""
    try:
        raw = sys.stdin.read().strip()
        if not raw:
            return {}
        payload = json.loads(raw)
        # Extract input from wrapper if present
        if "input" in payload and isinstance(payload["input"], dict):
            return payload["input"]
        return payload
    except json.JSONDecodeError as e:
        return {"error": f"Invalid JSON: {e}"}


def validate_sensor_ids(sensors: List[Dict[str, Any]]) -> List[str]:
    """
    Check that all sensor IDs are unique.

    Returns:
        List of error messages (empty if valid)
    """
    errors = []
    sensor_ids = [s.get('sensor_id', '') for s in sensors]

    # Check for duplicates
    seen = set()
    for sensor_id in sensor_ids:
        if not sensor_id:
            errors.append("Sensor ID cannot be empty")
            continue

        if sensor_id in seen:
            errors.append(f"Duplicate sensor ID: {sensor_id}")
        seen.add(sensor_id)

    return errors


def validate_sensor_types(sensors: List[Dict[str, Any]]) -> List[str]:
    """
    Check that sensor types are valid.

    Returns:
        List of error messages (empty if valid)
    """
    errors = []
    valid_types = ['temperature', 'humidity', 'motion']

    for sensor in sensors:
        sensor_type = sensor.get('sensor_type', '')
        if sensor_type not in valid_types:
            sensor_id = sensor.get('sensor_id', 'unknown')
            errors.append(
                f"Invalid sensor type '{sensor_type}' for sensor {sensor_id}. "
                f"Valid types: {', '.join(valid_types)}"
            )

    return errors


def validate_required_fields(sensors: List[Dict[str, Any]]) -> List[str]:
    """
    Check that required fields are present.

    Returns:
        List of error messages (empty if valid)
    """
    errors = []
    required_fields = ['sensor_id', 'sensor_type', 'friendly_name']

    for idx, sensor in enumerate(sensors):
        for field in required_fields:
            if field not in sensor or not sensor[field]:
                errors.append(f"Sensor {idx + 1}: Missing required field '{field}'")

    return errors


def validate_configuration(config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate complete configuration.

    Args:
        config: Configuration payload with global_config and sensors

    Returns:
        Validation result in IoT2MQTT action format
    """
    errors = []

    # Extract configuration parts
    global_config = config.get('global_config', {})
    sensors = config.get('sensors', [])

    # If sensors is a single dict instead of list, wrap it
    if isinstance(sensors, dict):
        sensors = [sensors]

    # Validate global configuration
    if not global_config.get('instance_id'):
        errors.append("Instance ID is required")

    update_interval = global_config.get('update_interval')
    if update_interval is not None:
        try:
            interval = int(update_interval)
            if interval < 5 or interval > 300:
                errors.append("Update interval must be between 5 and 300 seconds")
        except (ValueError, TypeError):
            errors.append("Update interval must be a number")

    # Validate sensors
    if not sensors:
        errors.append("At least one sensor must be configured")
    else:
        errors.extend(validate_required_fields(sensors))
        errors.extend(validate_sensor_ids(sensors))
        errors.extend(validate_sensor_types(sensors))

    # Check sensor distribution (warning if unbalanced)
    if sensors:
        sensor_types = [s.get('sensor_type', '') for s in sensors]
        type_counts = {}
        for sensor_type in sensor_types:
            type_counts[sensor_type] = type_counts.get(sensor_type, 0) + 1

        # Just log info, not an error
        distribution_info = ', '.join([f"{t}: {c}" for t, c in type_counts.items()])

    # Return result
    if errors:
        return {
            "ok": False,
            "error": {
                "code": "validation_failed",
                "message": f"Configuration validation failed: {'; '.join(errors)}",
                "retriable": False,
                "details": errors
            }
        }
    else:
        return {
            "ok": True,
            "result": {
                "message": "Configuration is valid",
                "sensors_count": len(sensors),
                "instance_id": global_config.get('instance_id'),
                "validation_timestamp": "2025-01-01T00:00:00Z"
            }
        }


def main():
    """Main entry point"""
    # Load configuration from stdin
    config = load_payload()

    if "error" in config:
        # JSON parsing error
        result = {
            "ok": False,
            "error": {
                "code": "invalid_input",
                "message": config["error"],
                "retriable": False
            }
        }
    else:
        # Validate configuration
        result = validate_configuration(config)

    # Output result as JSON
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
