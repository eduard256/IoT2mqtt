#!/usr/bin/env python3
"""
Example Validation Action for Multi-Process Connector

This script runs during setup flow (before container creation) to validate
configuration and test connectivity. It executes in the test-runner container.

Actions can:
- Test network connectivity
- Validate configuration parameters
- Discover devices
- Check API credentials
- Perform pre-flight checks

The script receives input via stdin as JSON and outputs results via stdout as JSON.

Input format:
{
  "tool": "example_validate",
  "input": {
    "param1": "value1",
    "param2": "value2"
  }
}

Output format (success):
{
  "ok": true,
  "result": {
    "validated": true,
    "message": "Validation successful"
  }
}

Output format (failure):
{
  "ok": false,
  "error": {
    "code": "validation_failed",
    "message": "Detailed error message",
    "retriable": true
  }
}
"""

import json
import sys


def load_input():
    """Load and parse input from stdin"""
    try:
        raw = sys.stdin.read().strip() or "{}"
        payload = json.loads(raw)

        # Extract input parameters
        if "input" in payload and isinstance(payload["input"], dict):
            return payload["input"]
        return payload

    except json.JSONDecodeError as e:
        return None


def validate_configuration(params):
    """
    Validate configuration parameters

    In a real connector, this would:
    - Check required parameters are present
    - Validate parameter formats (IP addresses, ports, etc.)
    - Test connectivity to external services
    - Verify API credentials
    - Discover available devices/services
    """

    # Example validation: check for required parameters
    required_params = ["example_param"]

    for param in required_params:
        if param not in params:
            return {
                "ok": False,
                "error": {
                    "code": "missing_parameter",
                    "message": f"Required parameter '{param}' is missing",
                    "retriable": False
                }
            }

    # Example validation: test connectivity
    # In real connector, this would use requests, socket, or device-specific libraries
    example_host = params.get("example_param", "localhost")

    try:
        # Simulate connectivity test
        # import socket
        # sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        # sock.settimeout(5)
        # result = sock.connect_ex((example_host, 80))
        # sock.close()

        # For template, just validate it's not empty
        if not example_host:
            return {
                "ok": False,
                "error": {
                    "code": "invalid_parameter",
                    "message": "example_param cannot be empty",
                    "retriable": False
                }
            }

    except Exception as e:
        return {
            "ok": False,
            "error": {
                "code": "validation_error",
                "message": str(e),
                "retriable": True
            }
        }

    # Validation successful
    return {
        "ok": True,
        "result": {
            "validated": True,
            "message": "Configuration validated successfully",
            "example_param": example_host
        }
    }


def main():
    """Main entry point"""

    # Load input
    params = load_input()

    if params is None:
        output = {
            "ok": False,
            "error": {
                "code": "invalid_input",
                "message": "Failed to parse input JSON",
                "retriable": False
            }
        }
    else:
        # Run validation
        output = validate_configuration(params)

    # Output result as JSON
    print(json.dumps(output))


if __name__ == '__main__':
    main()
