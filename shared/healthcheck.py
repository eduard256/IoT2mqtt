#!/usr/bin/env python3
"""
Universal healthcheck script for IoT2MQTT connectors
Reads connector setup.json and instance config to perform dynamic healthchecks
"""

import os
import sys
import json
import subprocess
from pathlib import Path
from typing import Dict, Any, Optional


def load_json_file(file_path: str) -> Optional[Dict[str, Any]]:
    """Load JSON file with error handling"""
    try:
        with open(file_path, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"Error: File not found: {file_path}", file=sys.stderr)
        return None
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON in {file_path}: {e}", file=sys.stderr)
        return None
    except Exception as e:
        print(f"Error loading {file_path}: {e}", file=sys.stderr)
        return None


def check_http(host: str, port: int, path: str = "/", timeout: int = 5) -> bool:
    """Check HTTP endpoint using curl"""
    url = f"http://{host}:{port}{path}"
    try:
        result = subprocess.run(
            ['curl', '-f', '-s', '-m', str(timeout), url],
            capture_output=True,
            timeout=timeout + 1
        )
        return result.returncode == 0
    except subprocess.TimeoutExpired:
        print(f"HTTP check timeout: {url}", file=sys.stderr)
        return False
    except FileNotFoundError:
        print("Error: curl not found", file=sys.stderr)
        return False
    except Exception as e:
        print(f"HTTP check error: {e}", file=sys.stderr)
        return False


def check_tcp(host: str, port: int, timeout: int = 5) -> bool:
    """Check TCP connection"""
    import socket
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        result = sock.connect_ex((host, port))
        sock.close()
        return result == 0
    except Exception as e:
        print(f"TCP check error: {e}", file=sys.stderr)
        return False


def check_python() -> bool:
    """Simple python process check - if we're running, we're healthy"""
    return True


def check_supervisor(process_name: str = None) -> bool:
    """Check supervisord process status"""
    try:
        if process_name:
            # Check specific process
            result = subprocess.run(
                ['supervisorctl', 'status', process_name],
                capture_output=True,
                timeout=5
            )
            return b'RUNNING' in result.stdout
        else:
            # Check all processes
            result = subprocess.run(
                ['supervisorctl', 'status'],
                capture_output=True,
                timeout=5
            )
            # All processes should be RUNNING
            return result.returncode == 0 and b'RUNNING' in result.stdout
    except subprocess.TimeoutExpired:
        print("Supervisor check timeout", file=sys.stderr)
        return False
    except FileNotFoundError:
        print("Error: supervisorctl not found", file=sys.stderr)
        return False
    except Exception as e:
        print(f"Supervisor check error: {e}", file=sys.stderr)
        return False


def check_custom(command: list) -> bool:
    """Execute custom healthcheck command"""
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            timeout=10
        )
        return result.returncode == 0
    except subprocess.TimeoutExpired:
        print(f"Custom command timeout: {command}", file=sys.stderr)
        return False
    except Exception as e:
        print(f"Custom command error: {e}", file=sys.stderr)
        return False


def main():
    """Main healthcheck logic"""

    # Get instance name from environment
    instance_name = os.getenv('INSTANCE_NAME')
    if not instance_name:
        print("Error: INSTANCE_NAME environment variable not set", file=sys.stderr)
        sys.exit(1)

    # Load instance config
    instance_config_path = f"/app/instances/{instance_name}.json"
    instance_config = load_json_file(instance_config_path)
    if not instance_config:
        print(f"Error: Could not load instance config: {instance_config_path}", file=sys.stderr)
        sys.exit(1)

    # Get connector type
    connector_type = instance_config.get('connector_type')
    if not connector_type:
        print("Error: connector_type not found in instance config", file=sys.stderr)
        sys.exit(1)

    # Load connector setup.json
    setup_path = f"/app/connectors/{connector_type}/setup.json"
    setup = load_json_file(setup_path)
    if not setup:
        print(f"Error: Could not load setup.json: {setup_path}", file=sys.stderr)
        sys.exit(1)

    # Get healthcheck configuration
    healthcheck_config = setup.get('healthcheck', {})
    if not healthcheck_config:
        print(f"Warning: No healthcheck configuration in setup.json, using default", file=sys.stderr)
        # Default: simple python check
        healthcheck_config = {"type": "python"}

    # Extract healthcheck type
    check_type = healthcheck_config.get('type', 'python')

    # Perform healthcheck based on type
    try:
        if check_type == 'http':
            # HTTP healthcheck with dynamic port support
            port_variable = healthcheck_config.get('port_variable')
            path = healthcheck_config.get('path', '/')
            host = healthcheck_config.get('host', 'localhost')
            timeout = healthcheck_config.get('timeout', 5)

            if port_variable:
                # Get port from instance config
                ports = instance_config.get('ports', {})
                port = ports.get(port_variable)
                if not port:
                    print(f"Error: Port variable '{port_variable}' not found in instance ports", file=sys.stderr)
                    sys.exit(1)
            else:
                # Use static port
                port = healthcheck_config.get('port')
                if not port:
                    print("Error: Neither port_variable nor port specified in healthcheck config", file=sys.stderr)
                    sys.exit(1)

            result = check_http(host, port, path, timeout)

        elif check_type == 'tcp':
            # TCP port check with dynamic port support
            port_variable = healthcheck_config.get('port_variable')
            host = healthcheck_config.get('host', 'localhost')
            timeout = healthcheck_config.get('timeout', 5)

            if port_variable:
                ports = instance_config.get('ports', {})
                port = ports.get(port_variable)
                if not port:
                    print(f"Error: Port variable '{port_variable}' not found in instance ports", file=sys.stderr)
                    sys.exit(1)
            else:
                port = healthcheck_config.get('port')
                if not port:
                    print("Error: Neither port_variable nor port specified in healthcheck config", file=sys.stderr)
                    sys.exit(1)

            result = check_tcp(host, port, timeout)

        elif check_type == 'python':
            # Simple Python process check
            result = check_python()

        elif check_type == 'supervisor':
            # Supervisord process check
            process_name = healthcheck_config.get('process_name')
            result = check_supervisor(process_name)

        elif check_type == 'custom':
            # Custom command
            command = healthcheck_config.get('command')
            if not command or not isinstance(command, list):
                print("Error: Invalid or missing 'command' for custom healthcheck", file=sys.stderr)
                sys.exit(1)
            result = check_custom(command)

        else:
            print(f"Error: Unknown healthcheck type: {check_type}", file=sys.stderr)
            sys.exit(1)

        # Exit with appropriate code
        if result:
            sys.exit(0)  # Healthy
        else:
            print(f"Healthcheck failed: {check_type}", file=sys.stderr)
            sys.exit(1)  # Unhealthy

    except Exception as e:
        print(f"Unexpected error during healthcheck: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
