"""
Port Management Service
Handles automatic port allocation for connector instances
"""

import random
import socket
import logging
from typing import Set, Optional
from pathlib import Path
import json

logger = logging.getLogger(__name__)


class PortManager:
    """Manages port allocation for connector instances"""

    # Port range for automatic allocation (user ports)
    MIN_PORT = 10000
    MAX_PORT = 65535

    def __init__(self, instances_path: Path):
        """
        Initialize PortManager

        Args:
            instances_path: Path to instances directory
        """
        self.instances_path = instances_path

    def is_port_available(self, port: int) -> bool:
        """
        Check if port is available on localhost

        Args:
            port: Port number to check

        Returns:
            True if port is available, False otherwise
        """
        try:
            # Try to bind to the port on both TCP and UDP
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                sock.bind(('127.0.0.1', port))
            return True
        except OSError:
            return False

    def get_all_allocated_ports(self) -> Set[int]:
        """
        Scan all instance files to find allocated ports

        Returns:
            Set of all currently allocated port numbers
        """
        allocated_ports = set()

        if not self.instances_path.exists():
            return allocated_ports

        # Scan all connector directories
        for connector_dir in self.instances_path.iterdir():
            if not connector_dir.is_dir():
                continue

            # Scan all instance JSON files
            for instance_file in connector_dir.glob("*.json"):
                try:
                    with open(instance_file, 'r') as f:
                        instance_data = json.load(f)

                    # Extract ports if they exist
                    if "ports" in instance_data and isinstance(instance_data["ports"], dict):
                        for port_value in instance_data["ports"].values():
                            if isinstance(port_value, int):
                                allocated_ports.add(port_value)

                except (json.JSONDecodeError, OSError) as e:
                    logger.warning(f"Failed to read instance file {instance_file}: {e}")
                    continue

        return allocated_ports

    def generate_unique_port(self, max_attempts: int = 100) -> int:
        """
        Generate a unique port number that is:
        1. Not currently bound on localhost
        2. Not allocated to any other instance

        Args:
            max_attempts: Maximum number of generation attempts

        Returns:
            Unique port number

        Raises:
            RuntimeError: If unable to find available port after max_attempts
        """
        allocated_ports = self.get_all_allocated_ports()

        for attempt in range(max_attempts):
            # Generate random port in range
            port = random.randint(self.MIN_PORT, self.MAX_PORT)

            # Check if not already allocated to an instance
            if port in allocated_ports:
                continue

            # Check if available on localhost
            if not self.is_port_available(port):
                continue

            logger.debug(f"Generated unique port: {port} (attempt {attempt + 1})")
            return port

        raise RuntimeError(
            f"Failed to generate unique port after {max_attempts} attempts. "
            f"Currently allocated ports: {len(allocated_ports)}"
        )

    def generate_ports_for_connector(self, port_names: list) -> dict:
        """
        Generate unique ports for all specified port names

        Args:
            port_names: List of port names (e.g., ["go2rtc_api", "go2rtc_rtsp"])

        Returns:
            Dictionary mapping port names to generated port numbers

        Example:
            >>> generate_ports_for_connector(["go2rtc_api", "go2rtc_rtsp"])
            {"go2rtc_api": 45231, "go2rtc_rtsp": 52341}
        """
        if not port_names:
            return {}

        ports = {}
        allocated_in_this_batch = set()

        for port_name in port_names:
            # Keep trying until we get a unique port
            max_attempts = 100
            for attempt in range(max_attempts):
                port = self.generate_unique_port()

                # Make sure we don't reuse a port from this batch
                if port not in allocated_in_this_batch:
                    ports[port_name] = port
                    allocated_in_this_batch.add(port)
                    logger.info(f"Allocated port {port} for {port_name}")
                    break
            else:
                raise RuntimeError(f"Failed to allocate unique port for {port_name}")

        return ports
