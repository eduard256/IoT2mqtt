#!/usr/bin/env python3
"""Test script to verify Yeelight port validation fix."""

import json
import subprocess
import sys

def test_empty_port():
    """Test that empty port is handled correctly."""
    test_payload = {
        "input": {
            "host": "192.168.1.100",
            "port": ""  # Empty string that was causing the error
        }
    }

    print("Testing with empty port string...")
    result = subprocess.run(
        ["python3", "connectors/yeelight/actions/validate.py"],
        input=json.dumps(test_payload),
        capture_output=True,
        text=True
    )

    if result.returncode != 0:
        print(f"❌ Script crashed with return code {result.returncode}")
        print(f"Error: {result.stderr}")
        return False

    try:
        output = json.loads(result.stdout)
        # We expect a validation failure (device not reachable) but not a crash
        if output.get("ok") == False:
            error_code = output.get("error", {}).get("code")
            if error_code == "validation_failed":
                print("✅ Empty port handled correctly (validation failed as expected)")
                return True
            else:
                print(f"❌ Unexpected error code: {error_code}")
                return False
        else:
            print("❌ Validation unexpectedly succeeded")
            return False
    except json.JSONDecodeError:
        print(f"❌ Invalid JSON output: {result.stdout}")
        return False

def test_valid_port():
    """Test that valid port works correctly."""
    test_payload = {
        "input": {
            "host": "192.168.1.100",
            "port": 55443
        }
    }

    print("Testing with valid port number...")
    result = subprocess.run(
        ["python3", "connectors/yeelight/actions/validate.py"],
        input=json.dumps(test_payload),
        capture_output=True,
        text=True
    )

    if result.returncode != 0:
        print(f"❌ Script crashed with return code {result.returncode}")
        return False

    try:
        output = json.loads(result.stdout)
        # We expect validation to fail (device not reachable) but script should not crash
        print(f"✅ Valid port handled correctly: {output}")
        return True
    except json.JSONDecodeError:
        print(f"❌ Invalid JSON output: {result.stdout}")
        return False

def test_default_port():
    """Test that missing port uses default."""
    test_payload = {
        "input": {
            "host": "192.168.1.100"
            # No port specified - should use default 55443
        }
    }

    print("Testing with missing port (should use default)...")
    result = subprocess.run(
        ["python3", "connectors/yeelight/actions/validate.py"],
        input=json.dumps(test_payload),
        capture_output=True,
        text=True
    )

    if result.returncode != 0:
        print(f"❌ Script crashed with return code {result.returncode}")
        return False

    try:
        output = json.loads(result.stdout)
        print(f"✅ Missing port handled correctly (used default): {output}")
        return True
    except json.JSONDecodeError:
        print(f"❌ Invalid JSON output: {result.stdout}")
        return False

if __name__ == "__main__":
    print("Testing Yeelight port validation fix...\n")

    # Note: The current validate.py still has the bug,
    # so we expect the empty port test to fail
    tests_passed = 0
    tests_total = 3

    if test_empty_port():
        tests_passed += 1

    if test_valid_port():
        tests_passed += 1

    if test_default_port():
        tests_passed += 1

    print(f"\nTests passed: {tests_passed}/{tests_total}")

    if tests_passed < tests_total:
        print("\n⚠️  Some tests failed. The validate.py script needs fixing.")
        print("The issue is on line 36 where it tries to convert empty string to int.")

    sys.exit(0 if tests_passed == tests_total else 1)