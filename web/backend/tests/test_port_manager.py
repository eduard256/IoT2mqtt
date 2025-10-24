"""
Comprehensive tests for PortManager service

Tests cover:
1. PortManager initialization
2. Port availability checking (TCP socket binding)
3. Scanning instance files for allocated ports
4. Unique port generation (not bound, not allocated)
5. Batch port allocation for connectors
6. Error handling (max attempts, invalid files)
7. Edge cases (empty instances, malformed JSON)
"""

import pytest
import json
import socket
import tempfile
import time
from pathlib import Path
from unittest.mock import patch, MagicMock
import sys

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from services.port_manager import PortManager


# ============================================================================
# TIER 1 - CRITICAL TESTS: Initialization
# ============================================================================

class TestPortManagerInitialization:
    """Test PortManager initialization"""

    def test_initialization_with_path(self):
        """Should initialize with instances path"""
        instances_path = Path("/tmp/instances")
        manager = PortManager(instances_path)

        assert manager.instances_path == instances_path

    def test_port_range_constants(self):
        """Should have correct port range constants"""
        assert PortManager.MIN_PORT == 10000
        assert PortManager.MAX_PORT == 65535


# ============================================================================
# TIER 1 - CRITICAL TESTS: Port Availability Checking
# ============================================================================

class TestPortAvailability:
    """Test port availability checking"""

    def test_is_port_available_free_port(self):
        """Should return True for available port"""
        manager = PortManager(Path("/tmp/instances"))

        # Find a definitely free port by binding first
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as temp_sock:
            temp_sock.bind(('127.0.0.1', 0))
            free_port = temp_sock.getsockname()[1]

        # Port should be free now
        time.sleep(0.01)  # Small delay to ensure port is released
        assert manager.is_port_available(free_port) is True

    def test_is_port_available_occupied_port(self):
        """Should return False for occupied port"""
        manager = PortManager(Path("/tmp/instances"))

        # Bind to a port to occupy it
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.bind(('127.0.0.1', 0))
            occupied_port = sock.getsockname()[1]

            # While still bound, should not be available
            assert manager.is_port_available(occupied_port) is False

    def test_is_port_available_privileged_port(self):
        """Should handle privileged ports (< 1024) correctly"""
        manager = PortManager(Path("/tmp/instances"))

        # Port 80 should not be available (privileged)
        # Even if not bound, we can't bind to it without root
        result = manager.is_port_available(80)

        # Result depends on permissions, but should not crash
        assert isinstance(result, bool)


# ============================================================================
# TIER 1 - CRITICAL TESTS: Scanning Allocated Ports
# ============================================================================

class TestAllocatedPortsScanning:
    """Test scanning instance files for allocated ports"""

    def test_get_allocated_ports_from_instances(self):
        """Should extract ports from instance JSON files"""
        with tempfile.TemporaryDirectory() as tmpdir:
            instances_path = Path(tmpdir)

            # Create connector directory
            cameras_dir = instances_path / "cameras"
            cameras_dir.mkdir()

            # Create instance file with ports
            instance1 = cameras_dir / "camera1.json"
            instance1.write_text(json.dumps({
                "instance_id": "camera1",
                "ports": {
                    "go2rtc_api": 12345,
                    "go2rtc_rtsp": 12346,
                    "go2rtc_webrtc": 12347
                }
            }))

            manager = PortManager(instances_path)
            allocated = manager.get_all_allocated_ports()

            assert 12345 in allocated
            assert 12346 in allocated
            assert 12347 in allocated
            assert len(allocated) == 3

    def test_get_allocated_ports_multiple_instances(self):
        """Should scan ports from multiple instances"""
        with tempfile.TemporaryDirectory() as tmpdir:
            instances_path = Path(tmpdir)

            # Create multiple connector directories
            cameras_dir = instances_path / "cameras"
            cameras_dir.mkdir()
            yeelight_dir = instances_path / "yeelight"
            yeelight_dir.mkdir()

            # Create instance files
            (cameras_dir / "cam1.json").write_text(json.dumps({
                "ports": {"api": 10001, "rtsp": 10002}
            }))
            (yeelight_dir / "light1.json").write_text(json.dumps({
                "ports": {"control": 20001}
            }))

            manager = PortManager(instances_path)
            allocated = manager.get_all_allocated_ports()

            assert allocated == {10001, 10002, 20001}

    def test_get_allocated_ports_no_instances_dir(self):
        """Should return empty set if instances dir doesn't exist"""
        manager = PortManager(Path("/nonexistent/path"))
        allocated = manager.get_all_allocated_ports()

        assert allocated == set()

    def test_get_allocated_ports_empty_instances_dir(self):
        """Should return empty set for empty instances dir"""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = PortManager(Path(tmpdir))
            allocated = manager.get_all_allocated_ports()

            assert allocated == set()

    def test_get_allocated_ports_ignores_malformed_json(self):
        """Should skip files with malformed JSON"""
        with tempfile.TemporaryDirectory() as tmpdir:
            instances_path = Path(tmpdir)
            cameras_dir = instances_path / "cameras"
            cameras_dir.mkdir()

            # Valid instance
            (cameras_dir / "valid.json").write_text(json.dumps({
                "ports": {"api": 10001}
            }))

            # Malformed JSON
            (cameras_dir / "broken.json").write_text("{ invalid json")

            manager = PortManager(instances_path)
            allocated = manager.get_all_allocated_ports()

            # Should only get port from valid file
            assert allocated == {10001}

    def test_get_allocated_ports_missing_ports_field(self):
        """Should handle instances without ports field"""
        with tempfile.TemporaryDirectory() as tmpdir:
            instances_path = Path(tmpdir)
            cameras_dir = instances_path / "cameras"
            cameras_dir.mkdir()

            # Instance without ports
            (cameras_dir / "no_ports.json").write_text(json.dumps({
                "instance_id": "test",
                "connector_type": "cameras"
            }))

            manager = PortManager(instances_path)
            allocated = manager.get_all_allocated_ports()

            assert allocated == set()

    def test_get_allocated_ports_non_dict_ports(self):
        """Should handle ports field that is not a dict"""
        with tempfile.TemporaryDirectory() as tmpdir:
            instances_path = Path(tmpdir)
            cameras_dir = instances_path / "cameras"
            cameras_dir.mkdir()

            # Ports is not a dict
            (cameras_dir / "invalid_ports.json").write_text(json.dumps({
                "ports": [1234, 5678]  # List instead of dict
            }))

            manager = PortManager(instances_path)
            allocated = manager.get_all_allocated_ports()

            # Should not crash, should return empty
            assert allocated == set()

    def test_get_allocated_ports_mixed_port_types(self):
        """Should only extract integer port values"""
        with tempfile.TemporaryDirectory() as tmpdir:
            instances_path = Path(tmpdir)
            cameras_dir = instances_path / "cameras"
            cameras_dir.mkdir()

            (cameras_dir / "mixed.json").write_text(json.dumps({
                "ports": {
                    "valid_port": 10001,
                    "string_port": "12345",  # String, not int
                    "null_port": None,
                    "another_valid": 10002
                }
            }))

            manager = PortManager(instances_path)
            allocated = manager.get_all_allocated_ports()

            # Should only get integer ports
            assert allocated == {10001, 10002}

    def test_get_allocated_ports_ignores_non_json_files(self):
        """Should ignore non-JSON files in connector directories"""
        with tempfile.TemporaryDirectory() as tmpdir:
            instances_path = Path(tmpdir)
            cameras_dir = instances_path / "cameras"
            cameras_dir.mkdir()

            # Valid JSON file
            (cameras_dir / "instance.json").write_text(json.dumps({
                "ports": {"api": 10001}
            }))

            # Non-JSON files
            (cameras_dir / "readme.txt").write_text("Some text")
            (cameras_dir / "config.yaml").write_text("key: value")

            manager = PortManager(instances_path)
            allocated = manager.get_all_allocated_ports()

            # Should only scan .json files
            assert allocated == {10001}


# ============================================================================
# TIER 1 - CRITICAL TESTS: Unique Port Generation
# ============================================================================

class TestUniquePortGeneration:
    """Test unique port generation"""

    def test_generate_unique_port_success(self):
        """Should generate a unique available port"""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = PortManager(Path(tmpdir))

            port = manager.generate_unique_port()

            # Should be in valid range
            assert PortManager.MIN_PORT <= port <= PortManager.MAX_PORT

            # Should be available
            assert manager.is_port_available(port) is True

    def test_generate_unique_port_not_in_allocated(self):
        """Should avoid ports already allocated to instances"""
        with tempfile.TemporaryDirectory() as tmpdir:
            instances_path = Path(tmpdir)
            cameras_dir = instances_path / "cameras"
            cameras_dir.mkdir()

            # Pre-allocate some ports
            allocated_ports = {45000, 45001, 45002}
            (cameras_dir / "instance.json").write_text(json.dumps({
                "ports": {f"port{i}": port for i, port in enumerate(allocated_ports)}
            }))

            manager = PortManager(instances_path)

            # Generate new port
            port = manager.generate_unique_port()

            # Should not be in already allocated ports
            assert port not in allocated_ports

    def test_generate_unique_port_retry_on_allocated(self):
        """Should retry if generated port is already allocated"""
        with tempfile.TemporaryDirectory() as tmpdir:
            instances_path = Path(tmpdir)
            cameras_dir = instances_path / "cameras"
            cameras_dir.mkdir()

            # Allocate many ports to force retries
            allocated_ports = set(range(40000, 40100))
            (cameras_dir / "instance.json").write_text(json.dumps({
                "ports": {f"port{i}": port for i, port in enumerate(allocated_ports)}
            }))

            manager = PortManager(instances_path)

            with patch('random.randint') as mock_random:
                # First few attempts return allocated ports
                mock_random.side_effect = [40050, 40051, 40052, 50000]

                port = manager.generate_unique_port()

                # Should have retried and got 50000
                assert port == 50000

    def test_generate_unique_port_max_attempts_exceeded(self):
        """Should raise RuntimeError after max attempts"""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = PortManager(Path(tmpdir))

            with patch.object(manager, 'is_port_available', return_value=False):
                # All ports unavailable
                with pytest.raises(RuntimeError, match="Failed to generate unique port"):
                    manager.generate_unique_port(max_attempts=5)

    def test_generate_unique_port_different_each_time(self):
        """Should generate different ports on consecutive calls"""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = PortManager(Path(tmpdir))

            ports = [manager.generate_unique_port() for _ in range(10)]

            # All ports should be unique (very high probability)
            assert len(set(ports)) >= 8  # Allow small chance of collision


# ============================================================================
# TIER 1 - CRITICAL TESTS: Batch Port Allocation
# ============================================================================

class TestBatchPortAllocation:
    """Test batch port allocation for connectors"""

    def test_generate_ports_for_connector_success(self):
        """Should generate all requested ports"""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = PortManager(Path(tmpdir))

            port_names = ["go2rtc_api", "go2rtc_rtsp", "go2rtc_webrtc"]
            ports = manager.generate_ports_for_connector(port_names)

            # Should have all ports
            assert len(ports) == 3
            assert "go2rtc_api" in ports
            assert "go2rtc_rtsp" in ports
            assert "go2rtc_webrtc" in ports

            # All ports should be in valid range
            for port in ports.values():
                assert PortManager.MIN_PORT <= port <= PortManager.MAX_PORT

    def test_generate_ports_for_connector_all_unique(self):
        """Should generate unique ports (no duplicates in batch)"""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = PortManager(Path(tmpdir))

            port_names = ["port1", "port2", "port3", "port4", "port5"]
            ports = manager.generate_ports_for_connector(port_names)

            # All ports should be unique
            port_values = list(ports.values())
            assert len(port_values) == len(set(port_values))

    def test_generate_ports_for_connector_empty_list(self):
        """Should return empty dict for empty port names"""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = PortManager(Path(tmpdir))

            ports = manager.generate_ports_for_connector([])

            assert ports == {}

    def test_generate_ports_for_connector_single_port(self):
        """Should handle single port request"""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = PortManager(Path(tmpdir))

            ports = manager.generate_ports_for_connector(["api_port"])

            assert len(ports) == 1
            assert "api_port" in ports

    def test_generate_ports_for_connector_avoids_allocated(self):
        """Should avoid ports already allocated to other instances"""
        with tempfile.TemporaryDirectory() as tmpdir:
            instances_path = Path(tmpdir)
            cameras_dir = instances_path / "cameras"
            cameras_dir.mkdir()

            # Pre-allocate ports
            allocated = {50000, 50001}
            (cameras_dir / "instance.json").write_text(json.dumps({
                "ports": {"port1": 50000, "port2": 50001}
            }))

            manager = PortManager(instances_path)

            # Generate new ports
            ports = manager.generate_ports_for_connector(["new1", "new2"])

            # Should not reuse allocated ports
            for port in ports.values():
                assert port not in allocated

    def test_generate_ports_for_connector_max_attempts_failure(self):
        """Should raise error if can't allocate after max attempts"""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = PortManager(Path(tmpdir))

            # Make generate_unique_port always return the same port
            with patch.object(manager, 'generate_unique_port', return_value=40000):
                # Should fail because it keeps getting duplicate in batch
                with pytest.raises(RuntimeError, match="Failed to allocate unique port"):
                    manager.generate_ports_for_connector(["port1", "port2"])


# ============================================================================
# TIER 1 - CRITICAL TESTS: Edge Cases
# ============================================================================

class TestEdgeCases:
    """Test edge cases and error handling"""

    def test_handles_symlinks_in_instances_dir(self):
        """Should handle symlinks gracefully"""
        with tempfile.TemporaryDirectory() as tmpdir:
            instances_path = Path(tmpdir)
            cameras_dir = instances_path / "cameras"
            cameras_dir.mkdir()

            # Create a valid instance
            (cameras_dir / "instance.json").write_text(json.dumps({
                "ports": {"api": 10001}
            }))

            # Create a symlink (might not work on all platforms)
            try:
                (instances_path / "link").symlink_to(cameras_dir)
            except OSError:
                pytest.skip("Symlinks not supported on this platform")

            manager = PortManager(instances_path)
            allocated = manager.get_all_allocated_ports()

            # Should still work
            assert 10001 in allocated

    def test_handles_permission_errors(self):
        """Should handle permission errors when reading files"""
        with tempfile.TemporaryDirectory() as tmpdir:
            instances_path = Path(tmpdir)
            cameras_dir = instances_path / "cameras"
            cameras_dir.mkdir()

            instance_file = cameras_dir / "instance.json"
            instance_file.write_text(json.dumps({
                "ports": {"api": 10001}
            }))

            # Simulate permission error
            with patch('builtins.open', side_effect=OSError("Permission denied")):
                manager = PortManager(instances_path)
                allocated = manager.get_all_allocated_ports()

                # Should not crash, just return empty or partial
                assert isinstance(allocated, set)

    def test_port_range_boundaries(self):
        """Should respect MIN_PORT and MAX_PORT boundaries"""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = PortManager(Path(tmpdir))

            # Generate many ports
            ports = [manager.generate_unique_port() for _ in range(20)]

            # All should be in range
            for port in ports:
                assert PortManager.MIN_PORT <= port <= PortManager.MAX_PORT

    def test_concurrent_port_generation(self):
        """Should handle concurrent port generation safely"""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = PortManager(Path(tmpdir))

            # Generate ports in quick succession (simulating concurrent requests)
            ports = []
            for _ in range(5):
                port = manager.generate_unique_port()
                ports.append(port)

            # All ports should be unique
            assert len(set(ports)) == len(ports)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
