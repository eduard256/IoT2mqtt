"""
Comprehensive tests for shared/utils.py

Tests cover:
1. Environment file loading (.env parsing)
2. Password encryption/decryption (XOR-based)
3. Instance name validation
4. MQTT topic validation (wildcards, invalid chars)
5. Device class detection from model names
6. MAC address formatting
7. IP address validation (IPv4/IPv6)
8. Exponential backoff calculation
9. Rate limiting decorator
10. List chunking
11. Deep dictionary merging
12. Filename sanitization
13. Timestamp operations (get, parse, outdated check)
14. CircularBuffer data structure
"""

import pytest
import os
import tempfile
import time
from datetime import datetime, timedelta
from pathlib import Path
import sys

# Add shared to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'shared'))

from utils import (
    load_env_file,
    encrypt_password, decrypt_password,
    validate_instance_name,
    validate_mqtt_topic,
    parse_device_class,
    format_mac_address,
    parse_ip_address,
    exponential_backoff,
    rate_limit,
    chunk_list,
    merge_dicts,
    sanitize_filename,
    get_timestamp,
    parse_timestamp,
    is_timestamp_outdated,
    CircularBuffer
)


# ============================================================================
# TIER 1 - CRITICAL TESTS: Environment Loading
# ============================================================================

class TestEnvFileLoading:
    """Test .env file loading"""

    def test_load_env_file_success(self):
        """Should load environment variables from .env file"""
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.env') as f:
            f.write("KEY1=value1\n")
            f.write("KEY2=value2\n")
            f.write("KEY3=value with spaces\n")
            env_path = f.name

        try:
            env_vars = load_env_file(env_path)

            assert env_vars['KEY1'] == 'value1'
            assert env_vars['KEY2'] == 'value2'
            assert env_vars['KEY3'] == 'value with spaces'
        finally:
            os.unlink(env_path)

    def test_load_env_file_with_comments(self):
        """Should ignore comment lines"""
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.env') as f:
            f.write("# This is a comment\n")
            f.write("KEY1=value1\n")
            f.write("# Another comment\n")
            f.write("KEY2=value2\n")
            env_path = f.name

        try:
            env_vars = load_env_file(env_path)

            assert len(env_vars) == 2
            assert env_vars['KEY1'] == 'value1'
            assert env_vars['KEY2'] == 'value2'
        finally:
            os.unlink(env_path)

    def test_load_env_file_with_empty_lines(self):
        """Should ignore empty lines"""
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.env') as f:
            f.write("KEY1=value1\n")
            f.write("\n")
            f.write("KEY2=value2\n")
            f.write("  \n")
            env_path = f.name

        try:
            env_vars = load_env_file(env_path)

            assert len(env_vars) == 2
        finally:
            os.unlink(env_path)

    def test_load_env_file_nonexistent(self):
        """Should return empty dict for nonexistent file"""
        env_vars = load_env_file("/nonexistent/path/.env")

        assert env_vars == {}

    def test_load_env_file_with_equals_in_value(self):
        """Should handle values with equals sign"""
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.env') as f:
            f.write("CONNECTION_STRING=server=localhost;port=5432\n")
            env_path = f.name

        try:
            env_vars = load_env_file(env_path)

            assert env_vars['CONNECTION_STRING'] == 'server=localhost;port=5432'
        finally:
            os.unlink(env_path)


# ============================================================================
# TIER 1 - CRITICAL TESTS: Password Encryption
# ============================================================================

class TestPasswordEncryption:
    """Test password encryption/decryption"""

    def test_encrypt_decrypt_roundtrip(self):
        """Should encrypt and decrypt password correctly"""
        password = "my_secret_password123"
        key = "test_encryption_key"

        encrypted = encrypt_password(password, key)
        decrypted = decrypt_password(encrypted, key)

        assert decrypted == password

    def test_encrypted_different_from_original(self):
        """Encrypted password should differ from original"""
        password = "password123"
        key = "test_key"

        encrypted = encrypt_password(password, key)

        assert encrypted != password

    def test_different_keys_produce_different_results(self):
        """Different encryption keys should produce different results"""
        password = "password123"
        key1 = "key1"
        key2 = "key2"

        encrypted1 = encrypt_password(password, key1)
        encrypted2 = encrypt_password(password, key2)

        assert encrypted1 != encrypted2

    def test_decrypt_with_wrong_key_fails(self):
        """Decrypting with wrong key should produce garbage"""
        password = "password123"
        key1 = "correct_key"
        key2 = "wrong_key"

        encrypted = encrypt_password(password, key1)
        decrypted = decrypt_password(encrypted, key2)

        assert decrypted != password

    def test_encrypt_empty_string(self):
        """Should handle empty password"""
        password = ""
        key = "test_key"

        encrypted = encrypt_password(password, key)
        decrypted = decrypt_password(encrypted, key)

        assert decrypted == password

    def test_encrypt_with_default_key(self):
        """Should use default key from environment"""
        password = "password123"

        # Test with default key (no key parameter)
        encrypted = encrypt_password(password)
        decrypted = decrypt_password(encrypted)

        assert decrypted == password


# ============================================================================
# TIER 1 - CRITICAL TESTS: Instance Name Validation
# ============================================================================

class TestInstanceNameValidation:
    """Test instance name validation"""

    def test_valid_instance_names(self):
        """Should accept valid instance names"""
        valid_names = [
            "cameras_main",
            "yeelight_living_room",
            "sensor-bedroom",
            "my_device_123",
            "test123"
        ]

        for name in valid_names:
            assert validate_instance_name(name) is True, f"Failed for: {name}"

    def test_invalid_empty_name(self):
        """Should reject empty name"""
        assert validate_instance_name("") is False
        assert validate_instance_name(None) is False

    def test_invalid_too_short(self):
        """Should reject names shorter than 3 characters"""
        assert validate_instance_name("ab") is False

    def test_invalid_too_long(self):
        """Should reject names longer than 50 characters"""
        long_name = "a" * 51
        assert validate_instance_name(long_name) is False

    def test_invalid_starts_with_number(self):
        """Should reject names starting with number"""
        assert validate_instance_name("123camera") is False

    def test_invalid_special_characters(self):
        """Should reject names with special characters"""
        invalid_names = [
            "camera space",
            "camera@device",
            "camera#1",
            "camera.test",
            "camera/test"
        ]

        for name in invalid_names:
            assert validate_instance_name(name) is False, f"Should fail for: {name}"

    def test_valid_with_underscores_and_hyphens(self):
        """Should accept names with underscores and hyphens"""
        assert validate_instance_name("my_device-123") is True


# ============================================================================
# TIER 1 - CRITICAL TESTS: MQTT Topic Validation
# ============================================================================

class TestMQTTTopicValidation:
    """Test MQTT topic validation"""

    def test_valid_mqtt_topics(self):
        """Should accept valid MQTT topics"""
        valid_topics = [
            "home/living_room/light",
            "sensors/temperature/bedroom",
            "iot2mqtt/camera/state",
            "a/b/c/d/e"
        ]

        for topic in valid_topics:
            assert validate_mqtt_topic(topic) is True, f"Failed for: {topic}"

    def test_invalid_empty_topic(self):
        """Should reject empty topic"""
        assert validate_mqtt_topic("") is False
        assert validate_mqtt_topic(None) is False

    def test_invalid_starts_with_slash(self):
        """Should reject topic starting with /"""
        assert validate_mqtt_topic("/home/light") is False

    def test_invalid_ends_with_slash(self):
        """Should reject topic ending with /"""
        assert validate_mqtt_topic("home/light/") is False

    def test_invalid_double_slash(self):
        """Should reject topic with double slashes"""
        assert validate_mqtt_topic("home//light") is False

    def test_invalid_null_character(self):
        """Should reject topic with null character"""
        assert validate_mqtt_topic("home\0light") is False

    def test_invalid_wildcard_usage(self):
        """Should reject incorrect wildcard usage"""
        # Wildcards mixed with other characters in same level
        assert validate_mqtt_topic("home/+light/state") is False
        assert validate_mqtt_topic("home/#multi/state") is False


# ============================================================================
# TIER 1 - CRITICAL TESTS: Device Class Detection
# ============================================================================

class TestDeviceClassDetection:
    """Test device class detection from model names"""

    def test_detect_rgb_light(self):
        """Should detect RGB light"""
        assert parse_device_class("RGB Color Bulb") == "light.rgb"
        assert parse_device_class("Smart Color Light") == "light.rgb"

    def test_detect_color_temp_light(self):
        """Should detect color temperature light"""
        assert parse_device_class("Warm White Bulb") == "light.color_temp"
        assert parse_device_class("Temperature Adjustable Light") == "light.color_temp"

    def test_detect_dimmable_light(self):
        """Should detect dimmable light"""
        assert parse_device_class("Dimmable Bulb") == "light.dimmable"

    def test_detect_switch_light(self):
        """Should detect switch-only light"""
        assert parse_device_class("Simple Bulb") == "light.switch"
        assert parse_device_class("LED Light") == "light.switch"

    def test_detect_climate_devices(self):
        """Should detect climate devices"""
        assert parse_device_class("Smart Thermostat") == "climate.thermostat"
        assert parse_device_class("Air Conditioner") == "climate.ac"
        assert parse_device_class("Room Heater") == "climate.heater"
        assert parse_device_class("Humidifier Device") == "climate.humidifier"
        assert parse_device_class("Air Purifier") == "climate.air_purifier"

    def test_detect_sensors(self):
        """Should detect sensor types"""
        assert parse_device_class("Motion Sensor") == "sensor.motion"
        assert parse_device_class("Door Contact Sensor") == "sensor.contact"
        assert parse_device_class("Temperature Sensor") == "sensor.temperature"
        assert parse_device_class("Humidity Sensor") == "sensor.humidity"
        assert parse_device_class("Energy Monitor") == "sensor.energy"

    def test_detect_switches(self):
        """Should detect switch types"""
        assert parse_device_class("Smart Plug") == "switch.outlet"
        assert parse_device_class("Wall Outlet") == "switch.outlet"
        assert parse_device_class("Relay Switch") == "switch.relay"

    def test_detect_security_devices(self):
        """Should detect security devices"""
        assert parse_device_class("Smart Lock") == "security.lock"
        assert parse_device_class("IP Camera") == "security.camera"
        assert parse_device_class("Alarm System") == "security.alarm"

    def test_detect_media_devices(self):
        """Should detect media devices"""
        assert parse_device_class("Smart Speaker") == "media.speaker"
        assert parse_device_class("Smart TV") == "media.tv"

    def test_detect_appliances(self):
        """Should detect appliances"""
        assert parse_device_class("Robot Vacuum") == "appliance.vacuum"
        assert parse_device_class("Washing Machine") == "appliance.washer"
        assert parse_device_class("Smart Kettle") == "appliance.kettle"

    def test_default_fallback(self):
        """Should use default for unknown devices"""
        assert parse_device_class("Unknown Device XYZ") == "switch.outlet"


# ============================================================================
# TIER 1 - CRITICAL TESTS: MAC Address Formatting
# ============================================================================

class TestMACAddressFormatting:
    """Test MAC address formatting"""

    def test_format_mac_with_colons(self):
        """Should format MAC address with colons"""
        mac = "AA:BB:CC:DD:EE:FF"
        formatted = format_mac_address(mac)

        assert formatted == "AA:BB:CC:DD:EE:FF"

    def test_format_mac_with_hyphens(self):
        """Should convert hyphens to colons"""
        mac = "AA-BB-CC-DD-EE-FF"
        formatted = format_mac_address(mac)

        assert formatted == "AA:BB:CC:DD:EE:FF"

    def test_format_mac_with_dots(self):
        """Should convert dots to colons"""
        mac = "AABB.CCDD.EEFF"
        formatted = format_mac_address(mac)

        assert formatted == "AA:BB:CC:DD:EE:FF"

    def test_format_mac_no_separators(self):
        """Should add separators to MAC without them"""
        mac = "AABBCCDDEEFF"
        formatted = format_mac_address(mac)

        assert formatted == "AA:BB:CC:DD:EE:FF"

    def test_format_mac_lowercase_to_uppercase(self):
        """Should convert to uppercase"""
        mac = "aa:bb:cc:dd:ee:ff"
        formatted = format_mac_address(mac)

        assert formatted == "AA:BB:CC:DD:EE:FF"

    def test_invalid_mac_length(self):
        """Should raise error for invalid length"""
        with pytest.raises(ValueError, match="Invalid MAC address length"):
            format_mac_address("AA:BB:CC:DD:EE")

    def test_invalid_mac_characters(self):
        """Should raise error for invalid characters"""
        with pytest.raises(ValueError, match="Invalid MAC address format"):
            format_mac_address("ZZ:BB:CC:DD:EE:FF")


# ============================================================================
# TIER 1 - CRITICAL TESTS: IP Address Validation
# ============================================================================

class TestIPAddressValidation:
    """Test IP address validation"""

    def test_valid_ipv4_addresses(self):
        """Should validate correct IPv4 addresses"""
        valid_ips = [
            "192.168.1.1",
            "10.0.0.1",
            "172.16.0.1",
            "8.8.8.8",
            "127.0.0.1"
        ]

        for ip in valid_ips:
            result = parse_ip_address(ip)
            assert result == ip, f"Failed for: {ip}"

    def test_valid_ipv6_addresses(self):
        """Should validate correct IPv6 addresses"""
        valid_ips = [
            "2001:0db8:85a3:0000:0000:8a2e:0370:7334",
            "::1",
            "fe80::1"
        ]

        for ip in valid_ips:
            result = parse_ip_address(ip)
            assert result == ip, f"Failed for: {ip}"

    def test_invalid_ip_addresses(self):
        """Should reject invalid IP addresses"""
        invalid_ips = [
            "256.1.1.1",  # Out of range
            "192.168.1",  # Missing octet
            "192.168.1.1.1",  # Too many octets
            "not.an.ip.address",
            "hostname",
            ""
        ]

        for ip in invalid_ips:
            result = parse_ip_address(ip)
            assert result is None, f"Should fail for: {ip}"


# ============================================================================
# TIER 1 - CRITICAL TESTS: Exponential Backoff
# ============================================================================

class TestExponentialBackoff:
    """Test exponential backoff calculation"""

    def test_backoff_progression(self):
        """Should increase exponentially"""
        delays = [exponential_backoff(i) for i in range(5)]

        # Should be: 1, 2, 4, 8, 16
        assert delays == [1.0, 2.0, 4.0, 8.0, 16.0]

    def test_backoff_respects_max_delay(self):
        """Should cap at max_delay"""
        delay = exponential_backoff(10, base_delay=1.0, max_delay=60.0)

        # 2^10 = 1024, but should be capped at 60
        assert delay == 60.0

    def test_backoff_custom_base_delay(self):
        """Should use custom base delay"""
        delay = exponential_backoff(2, base_delay=5.0)

        # 5 * 2^2 = 20
        assert delay == 20.0

    def test_backoff_zero_attempt(self):
        """First attempt should return base_delay"""
        delay = exponential_backoff(0, base_delay=3.0)

        assert delay == 3.0


# ============================================================================
# TIER 1 - CRITICAL TESTS: Rate Limiting
# ============================================================================

class TestRateLimiting:
    """Test rate limiting decorator"""

    def test_rate_limit_allows_within_limit(self):
        """Should allow calls within rate limit"""
        call_count = [0]

        @rate_limit(calls=3, period=timedelta(seconds=1))
        def test_func():
            call_count[0] += 1
            return call_count[0]

        # Should allow 3 calls
        assert test_func() == 1
        assert test_func() == 2
        assert test_func() == 3

    def test_rate_limit_blocks_excess_calls(self):
        """Should block calls exceeding rate limit"""
        @rate_limit(calls=2, period=timedelta(seconds=1))
        def test_func():
            return "ok"

        # First 2 calls should succeed
        test_func()
        test_func()

        # Third call should raise exception
        with pytest.raises(Exception, match="Rate limit exceeded"):
            test_func()

    def test_rate_limit_resets_after_period(self):
        """Should reset after time period"""
        @rate_limit(calls=2, period=timedelta(milliseconds=100))
        def test_func():
            return "ok"

        # Use up the limit
        test_func()
        test_func()

        # Wait for period to pass
        time.sleep(0.15)

        # Should work again
        assert test_func() == "ok"


# ============================================================================
# TIER 1 - CRITICAL TESTS: List Operations
# ============================================================================

class TestListOperations:
    """Test list utility functions"""

    def test_chunk_list_even_division(self):
        """Should chunk list evenly"""
        lst = [1, 2, 3, 4, 5, 6]
        chunks = chunk_list(lst, 2)

        assert chunks == [[1, 2], [3, 4], [5, 6]]

    def test_chunk_list_uneven_division(self):
        """Should handle uneven division"""
        lst = [1, 2, 3, 4, 5]
        chunks = chunk_list(lst, 2)

        assert chunks == [[1, 2], [3, 4], [5]]

    def test_chunk_list_single_chunk(self):
        """Should handle chunk size larger than list"""
        lst = [1, 2, 3]
        chunks = chunk_list(lst, 10)

        assert chunks == [[1, 2, 3]]

    def test_chunk_list_empty(self):
        """Should handle empty list"""
        chunks = chunk_list([], 2)

        assert chunks == []


# ============================================================================
# TIER 1 - CRITICAL TESTS: Dictionary Merging
# ============================================================================

class TestDictionaryMerging:
    """Test deep dictionary merging"""

    def test_merge_simple_dicts(self):
        """Should merge simple dictionaries"""
        dict1 = {"a": 1, "b": 2}
        dict2 = {"c": 3, "d": 4}

        result = merge_dicts(dict1, dict2)

        assert result == {"a": 1, "b": 2, "c": 3, "d": 4}

    def test_merge_overwrite_values(self):
        """Should overwrite values from dict2"""
        dict1 = {"a": 1, "b": 2}
        dict2 = {"b": 3, "c": 4}

        result = merge_dicts(dict1, dict2)

        assert result == {"a": 1, "b": 3, "c": 4}

    def test_merge_nested_dicts(self):
        """Should deep merge nested dictionaries"""
        dict1 = {"a": {"b": 1, "c": 2}}
        dict2 = {"a": {"c": 3, "d": 4}}

        result = merge_dicts(dict1, dict2)

        assert result == {"a": {"b": 1, "c": 3, "d": 4}}

    def test_merge_preserves_original(self):
        """Should not modify original dictionaries"""
        dict1 = {"a": 1}
        dict2 = {"b": 2}

        result = merge_dicts(dict1, dict2)

        assert dict1 == {"a": 1}
        assert dict2 == {"b": 2}


# ============================================================================
# TIER 1 - CRITICAL TESTS: Filename Sanitization
# ============================================================================

class TestFilenameSanitization:
    """Test filename sanitization"""

    def test_sanitize_removes_invalid_chars(self):
        """Should remove invalid filesystem characters"""
        filename = 'test<file>name:with"invalid|chars?.txt'
        sanitized = sanitize_filename(filename)

        assert '<' not in sanitized
        assert '>' not in sanitized
        assert ':' not in sanitized
        assert '"' not in sanitized
        assert '|' not in sanitized
        assert '?' not in sanitized

    def test_sanitize_removes_control_chars(self):
        """Should remove control characters"""
        filename = "test\x00\x01\x1ffile.txt"
        sanitized = sanitize_filename(filename)

        assert '\x00' not in sanitized
        assert '\x01' not in sanitized
        assert '\x1f' not in sanitized

    def test_sanitize_limits_length(self):
        """Should limit filename length to 255"""
        long_name = "a" * 300 + ".txt"
        sanitized = sanitize_filename(long_name)

        assert len(sanitized) <= 255
        assert sanitized.endswith('.txt')

    def test_sanitize_preserves_valid_chars(self):
        """Should preserve valid characters"""
        filename = "valid_file-name_123.txt"
        sanitized = sanitize_filename(filename)

        assert sanitized == filename


# ============================================================================
# TIER 1 - CRITICAL TESTS: Timestamp Operations
# ============================================================================

class TestTimestampOperations:
    """Test timestamp utility functions"""

    def test_get_timestamp_format(self):
        """Should return ISO format timestamp"""
        timestamp = get_timestamp()

        # Should be parseable as ISO format
        dt = datetime.fromisoformat(timestamp)
        assert isinstance(dt, datetime)

    def test_parse_valid_timestamp(self):
        """Should parse valid ISO timestamp"""
        timestamp = "2024-01-15T10:30:45.123456"
        dt = parse_timestamp(timestamp)

        assert dt is not None
        assert dt.year == 2024
        assert dt.month == 1
        assert dt.day == 15

    def test_parse_invalid_timestamp(self):
        """Should return None for invalid timestamp"""
        assert parse_timestamp("not a timestamp") is None
        assert parse_timestamp("") is None

    def test_is_timestamp_outdated_fresh(self):
        """Should return False for fresh timestamp"""
        timestamp = get_timestamp()

        assert is_timestamp_outdated(timestamp, max_age_seconds=10) is False

    def test_is_timestamp_outdated_old(self):
        """Should return True for old timestamp"""
        old_time = datetime.now() - timedelta(seconds=60)
        timestamp = old_time.isoformat()

        assert is_timestamp_outdated(timestamp, max_age_seconds=30) is True

    def test_is_timestamp_outdated_invalid(self):
        """Should return True for invalid timestamp"""
        assert is_timestamp_outdated("invalid", max_age_seconds=30) is True


# ============================================================================
# TIER 1 - CRITICAL TESTS: CircularBuffer
# ============================================================================

class TestCircularBuffer:
    """Test CircularBuffer data structure"""

    def test_buffer_initialization(self):
        """Should initialize with given size"""
        buffer = CircularBuffer(5)

        assert buffer.size == 5
        assert buffer.get_all() == []

    def test_buffer_add_within_size(self):
        """Should add items without wrapping"""
        buffer = CircularBuffer(5)

        buffer.add(1)
        buffer.add(2)
        buffer.add(3)

        assert buffer.get_all() == [1, 2, 3]

    def test_buffer_add_wraps_around(self):
        """Should wrap around when full"""
        buffer = CircularBuffer(3)

        buffer.add(1)
        buffer.add(2)
        buffer.add(3)
        buffer.add(4)  # Should overwrite 1
        buffer.add(5)  # Should overwrite 2

        assert buffer.get_all() == [3, 4, 5]

    def test_buffer_get_latest(self):
        """Should get n latest values"""
        buffer = CircularBuffer(5)

        for i in range(1, 6):
            buffer.add(i)

        latest = buffer.get_latest(3)
        assert latest == [3, 4, 5]

    def test_buffer_get_latest_more_than_available(self):
        """Should return all if n > available"""
        buffer = CircularBuffer(10)

        buffer.add(1)
        buffer.add(2)

        latest = buffer.get_latest(5)
        assert latest == [1, 2]

    def test_buffer_clear(self):
        """Should clear all values"""
        buffer = CircularBuffer(5)

        buffer.add(1)
        buffer.add(2)
        buffer.add(3)

        buffer.clear()

        assert buffer.get_all() == []
        assert buffer.index == 0

    def test_buffer_maintains_order_after_wrap(self):
        """Should maintain correct order after wrapping"""
        buffer = CircularBuffer(3)

        # Add 1, 2, 3, 4, 5, 6
        for i in range(1, 7):
            buffer.add(i)

        # Should have [4, 5, 6] in order
        assert buffer.get_all() == [4, 5, 6]


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
