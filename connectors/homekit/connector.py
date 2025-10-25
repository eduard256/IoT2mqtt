#!/usr/bin/env python3
"""
HomeKit Connector - MQTT Bridge
Inherits from BaseConnector to handle MQTT communication
Communicates with HAP service via HTTP for HomeKit operations
"""

import os
import sys
import logging
import json
import threading
import time
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime

# Add shared to path
sys.path.insert(0, '/app/shared')
sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'shared'))

from base_connector import BaseConnector
from entity_mapper import EntityMapper
from characteristics import CharacteristicCommandMapper

try:
    import httpx
    from sseclient import SSEClient
except ImportError:
    # Will be installed by requirements.txt
    pass

logger = logging.getLogger(__name__)


class HomeKitConnector(BaseConnector):
    """
    HomeKit MQTT Connector

    Architecture:
    - This process handles MQTT communication using BaseConnector
    - HAP service (separate process) handles HomeKit protocol via aiohomekit
    - Communication via HTTP localhost:8765
    """

    def __init__(self, instance_name: str = None):
        """Initialize HomeKit connector"""
        super().__init__(instance_name=instance_name)

        # HAP service connection
        self.hap_service_port = self.config.get('config', {}).get('hap_service_port', 8765)
        self.hap_service_url = f"http://localhost:{self.hap_service_port}"
        self.hap_client = None

        # SSE event listener thread
        self.sse_thread = None
        self.sse_running = False

        # Device state cache (enhanced with HAP metadata)
        self.device_accessories = {}  # device_id -> accessories structure

        # Entity mappers
        self.entity_mapper = EntityMapper()
        self.command_mapper = CharacteristicCommandMapper()

        logger.info(f"HomeKit connector initialized, HAP service at {self.hap_service_url}")

    def initialize_connection(self):
        """
        Initialize connection to HAP service and devices

        This method is called by BaseConnector after MQTT connection is established
        """
        logger.info("Initializing connection to HAP service...")

        # Create HTTP client
        self.hap_client = httpx.Client(base_url=self.hap_service_url, timeout=30.0)

        # Wait for HAP service to be ready
        max_retries = 30
        for i in range(max_retries):
            try:
                response = self.hap_client.get("/health")
                if response.status_code == 200:
                    logger.info("HAP service is ready")
                    break
            except Exception as e:
                if i == max_retries - 1:
                    raise RuntimeError(f"HAP service not available after {max_retries} attempts: {e}")
                logger.debug(f"Waiting for HAP service... ({i+1}/{max_retries})")
                time.sleep(1)

        # Connect to all paired devices
        for device_config in self.config.get('devices', []):
            if not device_config.get('enabled', True):
                logger.info(f"Skipping disabled device: {device_config['device_id']}")
                continue

            device_id = device_config['device_id']
            pairing_id = device_config.get('pairing_id')

            if not pairing_id:
                logger.error(f"Device {device_id} missing pairing_id, skipping")
                continue

            try:
                logger.info(f"Connecting to device {device_id} (pairing_id: {pairing_id})...")

                # Load pairing data from secrets
                pairing_data = self._load_pairing_data(pairing_id)

                # Connect via HAP service
                connect_response = self.hap_client.post(
                    "/connect",
                    json={
                        "pairing_id": pairing_id,
                        "pairing_data": pairing_data,
                        "connection_type": device_config.get('connection', 'IP'),
                        "ip": device_config.get('ip'),
                        "port": device_config.get('port', 55443)
                    }
                )

                if connect_response.status_code == 200:
                    result = connect_response.json()
                    logger.info(f"Successfully connected to device {device_id}")

                    # Store accessories structure
                    self.device_accessories[device_id] = device_config.get('accessories', {})
                else:
                    logger.error(f"Failed to connect to device {device_id}: {connect_response.text}")

            except Exception as e:
                logger.error(f"Error connecting to device {device_id}: {e}", exc_info=True)

        # Start SSE event listener for push updates
        self._start_sse_listener()

        logger.info("HAP connection initialization complete")

    def cleanup_connection(self):
        """
        Clean up connection to HAP service

        This method is called by BaseConnector during shutdown
        """
        logger.info("Cleaning up HAP service connection...")

        # Stop SSE listener
        self.sse_running = False
        if self.sse_thread:
            self.sse_thread.join(timeout=5)

        # Disconnect all devices
        if self.hap_client:
            try:
                self.hap_client.post("/disconnect")
                logger.info("Disconnected from all HomeKit devices")
            except Exception as e:
                logger.error(f"Error disconnecting from HAP service: {e}")
            finally:
                self.hap_client.close()

        logger.info("HAP cleanup complete")

    def get_device_state(self, device_id: str, device_config: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Get current state of a HomeKit device

        Args:
            device_id: Device identifier
            device_config: Device configuration from instance JSON

        Returns:
            State dictionary or None if device unavailable
        """
        try:
            pairing_id = device_config.get('pairing_id')
            if not pairing_id:
                logger.error(f"Device {device_id} missing pairing_id")
                return None

            # Get accessories structure
            accessories = self.device_accessories.get(device_id)
            if not accessories:
                logger.warning(f"No accessories structure for device {device_id}")
                return {"online": False}

            # Extract all characteristic IIDs to read
            characteristics_to_read = []
            for accessory in accessories.get('accessories', []):
                aid = accessory.get('aid')
                for service in accessory.get('services', []):
                    for characteristic in service.get('characteristics', []):
                        iid = characteristic.get('iid')
                        perms = characteristic.get('perms', [])

                        # Only read characteristics with 'pr' (paired read) permission
                        if 'pr' in perms:
                            characteristics_to_read.append({"aid": aid, "iid": iid})

            if not characteristics_to_read:
                logger.debug(f"No readable characteristics for device {device_id}")
                return {"online": True}

            # Get characteristics from HAP service (batch request)
            response = self.hap_client.post(
                "/characteristics/get",
                json={
                    "pairing_id": pairing_id,
                    "characteristics": characteristics_to_read
                }
            )

            if response.status_code != 200:
                logger.error(f"Failed to get characteristics for {device_id}: {response.text}")
                return {"online": False}

            char_values = response.json()

            # Map characteristics to IoT2mqtt state using entity_mapper
            state = self.entity_mapper.map_characteristics_to_state(
                characteristics=char_values,
                accessories=accessories
            )

            return state

        except Exception as e:
            logger.error(f"Error getting state for device {device_id}: {e}", exc_info=True)
            return {"online": False}

    def set_device_state(self, device_id: str, device_config: Dict[str, Any],
                        state: Dict[str, Any]) -> bool:
        """
        Set HomeKit device state

        Args:
            device_id: Device identifier
            device_config: Device configuration from instance JSON
            state: New state to set (IoT2mqtt format)

        Returns:
            True if successful, False otherwise
        """
        try:
            pairing_id = device_config.get('pairing_id')
            if not pairing_id:
                logger.error(f"Device {device_id} missing pairing_id")
                return False

            # Get accessories structure
            accessories = self.device_accessories.get(device_id)
            if not accessories:
                logger.error(f"No accessories structure for device {device_id}")
                return False

            # Map IoT2mqtt commands to HAP characteristics using command_mapper
            characteristics_to_set = self.command_mapper.map_command_to_characteristics(
                command=state,
                accessories=accessories.get('accessories', [])
            )

            if not characteristics_to_set:
                logger.warning(f"No characteristics mapped from command for {device_id}")
                return False

            # Set characteristics via HAP service
            response = self.hap_client.post(
                "/characteristics/set",
                json={
                    "pairing_id": pairing_id,
                    "characteristics": characteristics_to_set
                }
            )

            if response.status_code == 200:
                logger.info(f"Successfully set state for device {device_id}")
                return True
            else:
                logger.error(f"Failed to set state for {device_id}: {response.text}")
                return False

        except Exception as e:
            logger.error(f"Error setting state for device {device_id}: {e}", exc_info=True)
            return False

    def _load_pairing_data(self, pairing_id: str) -> Dict[str, Any]:
        """
        Load pairing data from Docker secrets

        Args:
            pairing_id: Pairing identifier (MAC address format)

        Returns:
            Pairing data dictionary
        """
        # Try to load from Docker secrets
        secrets_file = f"/run/secrets/{self.instance_name}_homekit_pairing"

        if os.path.exists(secrets_file):
            logger.debug(f"Loading pairing data from secrets: {secrets_file}")
            try:
                pairing_data = {}
                with open(secrets_file) as f:
                    for line in f:
                        if '=' in line:
                            key, value = line.strip().split('=', 1)
                            pairing_data[key] = value
                return pairing_data
            except Exception as e:
                logger.error(f"Error loading pairing data from secrets: {e}")

        # Fallback: load from device config (not recommended for secrets)
        logger.warning("Pairing data not found in secrets, trying device config")
        for device in self.config.get('devices', []):
            if device.get('pairing_id') == pairing_id:
                return device.get('pairing_data', {})

        raise ValueError(f"Pairing data not found for pairing_id: {pairing_id}")

    def _start_sse_listener(self):
        """
        Start SSE (Server-Sent Events) listener thread for push updates

        HAP service streams characteristic changes via /events endpoint
        This allows immediate MQTT publishing without polling
        """
        def sse_listener():
            logger.info("Starting SSE listener for HomeKit events...")
            self.sse_running = True

            while self.sse_running:
                try:
                    # Connect to SSE endpoint
                    response = self.hap_client.get("/events", stream=True, timeout=None)

                    # Process events
                    for line in response.iter_lines():
                        if not self.sse_running:
                            break

                        if line:
                            try:
                                # Parse SSE event
                                if line.startswith(b'data: '):
                                    data = json.loads(line[6:])
                                    self._handle_sse_event(data)
                            except Exception as e:
                                logger.error(f"Error parsing SSE event: {e}")

                except Exception as e:
                    if self.sse_running:
                        logger.error(f"SSE connection error: {e}, reconnecting in 5s...")
                        time.sleep(5)
                    else:
                        break

            logger.info("SSE listener stopped")

        self.sse_thread = threading.Thread(target=sse_listener, daemon=True)
        self.sse_thread.start()

    def _handle_sse_event(self, event: Dict[str, Any]):
        """
        Handle SSE event from HAP service

        Args:
            event: Event data with format:
                   {"pairing_id": "XX:XX:XX:XX:XX:XX",
                    "aid": 1, "iid": 11, "value": true}
        """
        try:
            pairing_id = event.get('pairing_id')
            aid = event.get('aid')
            iid = event.get('iid')
            value = event.get('value')

            # Find device_id for this pairing_id
            device_id = None
            for dev in self.config.get('devices', []):
                if dev.get('pairing_id') == pairing_id:
                    device_id = dev['device_id']
                    break

            if not device_id:
                logger.warning(f"Received SSE event for unknown pairing_id: {pairing_id}")
                return

            logger.debug(f"SSE event for {device_id}: aid={aid}, iid={iid}, value={value}")

            # Get accessories for this device
            accessories = self.device_accessories.get(device_id)
            if not accessories:
                logger.warning(f"No accessories structure for SSE event device {device_id}")
                return

            # Map single characteristic change to state update
            char_key = f"{aid}.{iid}"
            char_values = {char_key: value}

            # Use entity_mapper to convert to state
            state_update = self.entity_mapper.map_characteristics_to_state(
                characteristics=char_values,
                accessories=accessories.get('accessories', [])
            )

            # Publish state update to MQTT
            if state_update and len(state_update) > 1:  # More than just "online"
                self.mqtt.publish_state(device_id, state_update)

        except Exception as e:
            logger.error(f"Error handling SSE event: {e}", exc_info=True)


def main():
    """Main entry point for connector process"""
    log_level = os.getenv('LOG_LEVEL', 'INFO')
    logging.basicConfig(
        level=getattr(logging, log_level),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    instance_name = os.getenv('INSTANCE_NAME')
    if not instance_name:
        logger.error("INSTANCE_NAME environment variable not set")
        sys.exit(1)

    logger.info(f"Starting HomeKit Connector (MQTT Bridge) for {instance_name}")

    try:
        connector = HomeKitConnector(instance_name=instance_name)
        connector.run_forever()
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
