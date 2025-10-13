#!/usr/bin/env python3
"""
MQTT Bridge - IoT2MQTT Contract Implementation

This is the main coordinator that implements the IoT2MQTT MQTT contract.
It is the only service that directly communicates with the MQTT broker.
All other services are internal and communicate via REST APIs.

Responsibilities:
- Subscribe to MQTT command topics
- Publish device states to MQTT
- Route commands to appropriate protocol handlers
- Implement IoT2MQTT status and meta topics
- Handle errors and publish error notifications

Design principle: Keep this service focused on MQTT contract compliance.
Business logic and protocol handling are delegated to other services.
"""

import os
import sys
import time
import requests
import signal
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

# Add shared directory to path for MQTTClient import
sys.path.insert(0, '/app/shared')

try:
    from mqtt_client import MQTTClient
except ImportError as e:
    logging.error(f"Failed to import MQTTClient: {e}")
    logging.error("Make sure /app/shared is mounted and contains mqtt_client.py")
    sys.exit(1)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configuration
INSTANCE_NAME = os.getenv('INSTANCE_NAME')
STATE_AGGREGATOR_URL = os.getenv('STATE_AGGREGATOR_URL', 'http://localhost:5003')
UPDATE_INTERVAL = int(os.getenv('UPDATE_INTERVAL', '10'))  # seconds

if not INSTANCE_NAME:
    logger.error("INSTANCE_NAME environment variable not set")
    sys.exit(1)

# Global state
mqtt_client = None
running = True
devices_cache = []


def fetch_from_aggregator(endpoint: str, timeout: int = 5) -> Optional[Dict[str, Any]]:
    """
    Fetch data from state aggregator with error handling.

    Implements connection error handling and logging.
    Returns None on any error to allow graceful degradation.

    Args:
        endpoint: API endpoint path
        timeout: Request timeout in seconds

    Returns:
        Response data or None on error
    """
    try:
        response = requests.get(
            f"{STATE_AGGREGATOR_URL}{endpoint}",
            timeout=timeout
        )
        response.raise_for_status()
        return response.json()
    except requests.exceptions.Timeout:
        logger.error(f"Timeout fetching {endpoint} from aggregator")
        return None
    except requests.exceptions.ConnectionError:
        logger.error(f"Connection error to aggregator: {STATE_AGGREGATOR_URL}")
        return None
    except requests.exceptions.HTTPError as e:
        logger.error(f"HTTP error from aggregator {endpoint}: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error fetching {endpoint}: {e}")
        return None


def handle_device_command(topic: str, payload: Dict[str, Any]):
    """
    Handle commands sent to devices via MQTT.

    Commands are received on: devices/{device_id}/cmd
    This implementation demonstrates command routing pattern.

    Currently this is a read-only example (sensors don't accept commands),
    but the pattern shows how to route commands to appropriate handlers.

    Args:
        topic: MQTT topic that triggered this handler
        payload: Command payload from MQTT
    """
    # Extract device_id from topic
    # Topic format: iot2mqtt/v1/instances/{instance_id}/devices/{device_id}/cmd
    parts = topic.split('/')
    if len(parts) < 6:
        logger.warning(f"Invalid command topic format: {topic}")
        return

    device_id = parts[-2]
    logger.info(f"Received command for device {device_id}: {payload}")

    # For sensor hub example, devices are read-only
    # In a real connector with controllable devices:
    # 1. Determine device type (from cache or aggregator)
    # 2. Route command to appropriate handler API
    # 3. Handle response and publish confirmation

    # Example of how command routing would work:
    # if device_type == 'actuator':
    #     response = requests.post(
    #         f"{ACTUATOR_HANDLER_URL}/device/{device_id}/command",
    #         json=payload
    #     )
    #     if response.ok:
    #         mqtt_client.publish_state(device_id, response.json())

    logger.warning(f"Device {device_id} does not accept commands (sensors are read-only)")


def handle_device_get(topic: str, payload: Dict[str, Any]):
    """
    Handle get state requests for devices.

    Requests are received on: devices/{device_id}/get
    Responds by publishing current device state.

    Args:
        topic: MQTT topic that triggered this handler
        payload: Request payload (may contain property filter)
    """
    # Extract device_id from topic
    parts = topic.split('/')
    if len(parts) < 6:
        logger.warning(f"Invalid get topic format: {topic}")
        return

    device_id = parts[-2]
    logger.info(f"Received state request for device {device_id}")

    # Fetch current state from aggregator
    state_data = fetch_from_aggregator(f'/device/{device_id}')

    if state_data is None:
        logger.error(f"Failed to fetch state for {device_id}")
        mqtt_client.publish_error(
            device_id,
            "STATE_FETCH_ERROR",
            "Could not retrieve device state",
            severity="error"
        )
        return

    if 'error' in state_data:
        logger.error(f"Device {device_id} returned error: {state_data}")
        mqtt_client.publish_error(
            device_id,
            state_data.get('error', 'UNKNOWN_ERROR'),
            state_data.get('message', 'Unknown error'),
            severity="warning"
        )
        return

    # Filter properties if requested
    if 'properties' in payload and isinstance(payload['properties'], list):
        filtered_state = {k: v for k, v in state_data.items()
                         if k in payload['properties']}
        state_data = filtered_state

    # Publish current state
    mqtt_client.publish_state(device_id, state_data)
    logger.info(f"Published state for {device_id}")


def handle_meta_request(topic: str, payload: Dict[str, Any]):
    """
    Handle meta information requests.

    Requests received on: meta/request/{request_type}
    Supports: devices_list, info

    Args:
        topic: MQTT topic that triggered this handler
        payload: Request payload
    """
    # Extract request type from topic
    request_type = topic.split('/')[-1]
    logger.info(f"Received meta request: {request_type}")

    if request_type == "devices_list":
        # Get device list from aggregator
        devices_data = fetch_from_aggregator('/devices')

        if devices_data and 'devices' in devices_data:
            # Format for IoT2MQTT
            devices_list = []
            for device in devices_data['devices']:
                devices_list.append({
                    "device_id": device['device_id'],
                    "global_id": f"{INSTANCE_NAME}_{device['device_id']}",
                    "type": device['type'],
                    "handler": device.get('handler', 'unknown'),
                    "online": device.get('status') == 'online'
                })

            # Publish to meta topic
            response_topic = f"meta/devices_list"
            mqtt_client.publish(
                f"{mqtt_client.base_topic}/v1/instances/{INSTANCE_NAME}/{response_topic}",
                {"devices": devices_list, "count": len(devices_list)},
                retain=True
            )
            logger.info(f"Published devices list: {len(devices_list)} devices")
        else:
            logger.error("Failed to fetch device list from aggregator")

    elif request_type == "info":
        # Get health info from aggregator
        health_data = fetch_from_aggregator('/health')

        info = {
            "instance_id": INSTANCE_NAME,
            "connector_type": os.getenv('CONNECTOR_TYPE', 'sensor-hub'),
            "status": health_data.get('status', 'unknown') if health_data else 'unavailable',
            "devices_count": len(devices_cache),
            "update_interval": UPDATE_INTERVAL,
            "timestamp": datetime.now().isoformat()
        }

        # Publish to meta topic
        response_topic = f"meta/info"
        mqtt_client.publish(
            f"{mqtt_client.base_topic}/v1/instances/{INSTANCE_NAME}/{response_topic}",
            info,
            retain=True
        )
        logger.info("Published instance info")


def update_devices_state():
    """
    Periodic state update loop.

    Fetches current state for all devices and publishes to MQTT.
    Called at regular intervals defined by UPDATE_INTERVAL.
    """
    global devices_cache

    # Get list of all devices
    devices_data = fetch_from_aggregator('/devices')

    if devices_data is None or 'devices' not in devices_data:
        logger.warning("Could not fetch device list from aggregator")
        return

    devices = devices_data['devices']
    devices_cache = devices

    logger.info(f"Updating state for {len(devices)} devices")

    # Update state for each device
    for device in devices:
        device_id = device['device_id']

        # Fetch current state
        state_data = fetch_from_aggregator(f'/device/{device_id}')

        if state_data is None:
            logger.warning(f"Failed to fetch state for {device_id}")
            continue

        if 'error' in state_data:
            # Device returned error, publish error notification
            mqtt_client.publish_error(
                device_id,
                state_data.get('error', 'UNKNOWN_ERROR'),
                state_data.get('message', 'Unknown error'),
                severity="warning"
            )
            continue

        # Publish device state
        # Remove internal fields before publishing
        clean_state = {k: v for k, v in state_data.items()
                      if k not in ['cached', 'cache_age']}

        mqtt_client.publish_state(device_id, clean_state)

    logger.info("State update complete")


def signal_handler(signum, frame):
    """
    Handle shutdown signals gracefully.

    Ensures proper cleanup of MQTT connection and services.
    """
    global running
    logger.info(f"Received signal {signum}, shutting down...")
    running = False


def main():
    """
    Main entry point for MQTT bridge service.

    Sets up MQTT connection, subscriptions, and update loop.
    """
    global mqtt_client, running

    # Register signal handlers for graceful shutdown
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)

    logger.info(f"Starting MQTT Bridge for instance: {INSTANCE_NAME}")
    logger.info(f"State Aggregator: {STATE_AGGREGATOR_URL}")
    logger.info(f"Update interval: {UPDATE_INTERVAL} seconds")

    # Wait for state aggregator to be ready
    logger.info("Waiting for state aggregator to be available...")
    max_retries = 30
    retry_count = 0

    while retry_count < max_retries:
        health = fetch_from_aggregator('/health', timeout=2)
        if health is not None:
            logger.info("State aggregator is ready")
            break
        retry_count += 1
        logger.info(f"Waiting for aggregator... (attempt {retry_count}/{max_retries})")
        time.sleep(2)

    if retry_count >= max_retries:
        logger.error("State aggregator did not become available")
        sys.exit(1)

    # Initialize MQTT client
    try:
        mqtt_client = MQTTClient(instance_id=INSTANCE_NAME)
        logger.info("MQTTClient initialized")
    except Exception as e:
        logger.error(f"Failed to initialize MQTTClient: {e}")
        sys.exit(1)

    # Connect to MQTT broker
    if not mqtt_client.connect():
        logger.error("Failed to connect to MQTT broker")
        sys.exit(1)

    logger.info("Connected to MQTT broker")

    # Setup subscriptions
    mqtt_client.subscribe("devices/+/cmd", handle_device_command)
    mqtt_client.subscribe("devices/+/get", handle_device_get)
    mqtt_client.subscribe("meta/request/+", handle_meta_request)

    logger.info("MQTT subscriptions configured")

    # Publish initial devices list
    handle_meta_request("meta/request/devices_list", {})

    # Main loop - periodic state updates
    last_update = 0

    try:
        while running:
            current_time = time.time()

            # Time for scheduled update?
            if current_time - last_update >= UPDATE_INTERVAL:
                try:
                    update_devices_state()
                    last_update = current_time
                except Exception as e:
                    logger.error(f"Error updating device states: {e}")

            # Sleep briefly to avoid CPU spinning
            time.sleep(1)

    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    finally:
        # Cleanup
        logger.info("Disconnecting from MQTT broker")
        if mqtt_client:
            mqtt_client.disconnect()

        logger.info("MQTT Bridge stopped")


if __name__ == "__main__":
    main()
