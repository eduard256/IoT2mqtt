#!/usr/bin/env python3
"""Test that port parsing logic works correctly."""

def test_port_parsing(port_value):
    """Test the exact logic from validate.py."""
    # This is our fixed logic
    if port_value == "" or port_value is None:
        port = 55443
    else:
        try:
            port = int(port_value)
        except (ValueError, TypeError):
            port = 55443
    return port

# Test cases
test_cases = [
    ("", 55443, "Empty string should use default"),
    (None, 55443, "None should use default"),
    (55443, 55443, "Integer should work"),
    ("55443", 55443, "String number should work"),
    ("12345", 12345, "Different port should work"),
    ("invalid", 55443, "Invalid string should use default"),
    (0, 0, "Zero should work"),
]

print("Testing port parsing logic:")
print("-" * 40)

all_passed = True
for input_val, expected, description in test_cases:
    result = test_port_parsing(input_val)
    if result == expected:
        print(f"✅ {description}")
        print(f"   Input: {repr(input_val)} → Output: {result}")
    else:
        print(f"❌ {description}")
        print(f"   Input: {repr(input_val)} → Expected: {expected}, Got: {result}")
        all_passed = False

print("-" * 40)
if all_passed:
    print("✨ All tests passed! Port parsing is working correctly.")
else:
    print("❌ Some tests failed.")