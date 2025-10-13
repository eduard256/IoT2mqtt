#!/usr/bin/env python3
"""
MQTT Bridge - Main Coordinator for Multi-Process Connector

This bridge implements the IoT2MQTT contract and coordinates internal services.
It translates MQTT commands into HTTP requests to backend services and publishes
their state to MQTT topics.

Architecture:
- Subscribes to MQTT command topics (following IoT2MQTT contract)
- Routes commands to backend services via HTTP REST APIs on localhost
- Polls backend services for status updates
- Publishes state to MQTT following the contract specification
"""

import os
import sys
import time
import logging
import json
import requests
from typing import Dict, Any, Optional
from datetime import datetime

# Add shared directory to path to access MQTTClient
sys.path.insert(0, '/app/shared')

try:
    from mqtt_client import MQTTClient
except ImportError:
    print("ERROR: Could not import MQTTClient from shared/mqtt_client.py")
    print("Ensure /app/shared is mounted correctly")
    sys.exit(1)

# Configure logging
logging.basicConfig(
    level=os.getenv('LOG_LEVEL', 'INFO'),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ============================================================================
# Configuration from Environment Variables
# ============================================================================

# Required by IoT2MQTT contract (injected by docker_service)
INSTANCE_NAME = os.getenv('INSTANCE_NAME')
CONNECTOR_TYPE = os.getenv('CONNECTOR_TYPE', 'unknown')

if not INSTANCE_NAME:
    logger.error("INSTANCE_NAME environment variable not set")
    sys.exit(1)

# Internal service URLs (from supervisord environment)
PYTHON_SERVICE_URL = os.getenv('PYTHON_SERVICE_URL', 'http://localhost:5001')
NODEJS_SERVICE_URL = os.getenv('NODEJS_SERVICE_URL', 'http://localhost:5002')

# Polling interval for status updates (seconds)
UPDATE_INTERVAL = int(os.getenv('UPDATE_INTERVAL', '10'))

logger.info(f"Starting MQTT Bridge for instance: {INSTANCE_NAME}")
logger.info(f"Connector type: {CONNECTOR_TYPE}")
logger.info(f"Python service: {PYTHON_SERVICE_URL}")
logger.info(f"Node.js service: {NODEJS_SERVICE_URL}")


# ============================================================================
# MQTT Bridge Class
# ============================================================================

class MQTTBridge:
    """
    Coordinates between MQTT (IoT2MQTT contract) and internal HTTP services
    """

    def __init__(self):
        """Initialize MQTT bridge with client and service connections"""

        # Initialize MQTT client from shared library
        # The client automatically loads MQTT credentials from mounted .env file
        self.mqtt = MQTTClient(
            instance_id=INSTANCE_NAME,
            qos=1,
            retain_state=True
        )

        # Store last known state to avoid redundant publishes
        self.last_state = {}

        # Track service health
        self.services_healthy = {
            'python': False,
            'nodejs': False
        }

        logger.info("MQTT Bridge initialized")

    def start(self):
        """Start the bridge - connect to MQTT and begin coordination"""

        # Connect to MQTT broker
        logger.info("Connecting to MQTT broker...")
        if not self.mqtt.connect():
            logger.error("Failed to connect to MQTT broker")
            return False

        logger.info("Connected to MQTT broker successfully")

        # Subscribe to command topics following IoT2MQTT contract
        # Pattern: {BASE_TOPIC}/v1/instances/{instance_id}/devices/{device_id}/cmd
        self.mqtt.subscribe("devices/+/cmd", self._handle_device_command)
        self.mqtt.subscribe("devices/+/get", self._handle_device_get)

        # Subscribe to meta requests
        self.mqtt.subscribe("meta/request/+", self._handle_meta_request)

        logger.info("Subscribed to MQTT topics")

        # Wait for backend services to be ready
        self._wait_for_services()

        # Start main coordination loop
        logger.info("Starting main coordination loop")
        self._coordination_loop()

        return True

    def _wait_for_services(self, timeout: int = 30):
        """Wait for backend services to become available"""
        logger.info("Waiting for backend services to start...")

        start_time = time.time()

        while time.time() - start_time < timeout:
            try:
                # Check Python service
                resp = requests.get(f"{PYTHON_SERVICE_URL}/health", timeout=1)
                self.services_healthy['python'] = resp.status_code == 200
            except:
                self.services_healthy['python'] = False

            try:
                # Check Node.js service
                resp = requests.get(f"{NODEJS_SERVICE_URL}/health", timeout=1)
                self.services_healthy['nodejs'] = resp.status_code == 200
            except:
                self.services_healthy['nodejs'] = False

            if all(self.services_healthy.values()):
                logger.info("All backend services are healthy")
                return

            time.sleep(1)

        logger.warning(f"Service health check timeout. Status: {self.services_healthy}")

    def _handle_device_command(self, topic: str, payload: Dict[str, Any]):
        """
        Handle device command from MQTT

        Topic pattern: devices/{device_id}/cmd
        Payload: {
            "id": "command-uuid",
            "timestamp": "ISO8601",
            "values": {"key": "value"},
            "timeout": 5000
        }
        """
        # Extract device_id from topic
        parts = topic.split('/')
        device_id = parts[-2] if len(parts) >= 2 else 'unknown'

        logger.info(f"Received command for device {device_id}: {payload}")

        # Check for command ID (for response correlation)
        cmd_id = payload.get('id')

        # Extract command values
        if 'values' in payload:
            command_values = payload['values']
        else:
            # Support both formats: direct payload or wrapped in 'values'
            command_values = {k: v for k, v in payload.items()
                            if k not in ['id', 'timestamp', 'timeout']}

        try:
            # Route command to appropriate backend service
            # This is where you implement your command routing logic

            if 'python_command' in command_values:
                # Send to Python service
                result = self._call_python_service('command', command_values)
            elif 'nodejs_command' in command_values:
                # Send to Node.js service
                result = self._call_nodejs_service('command', command_values)
            else:
                # Default: broadcast to all services
                result = {
                    'python': self._call_python_service('command', command_values),
                    'nodejs': self._call_nodejs_service('command', command_values)
                }

            # Send success response if command_id present
            if cmd_id:
                self._send_command_response(device_id, cmd_id, True, result)

            # Immediately query and publish new state
            self._update_device_state(device_id)

        except Exception as e:
            logger.error(f"Error handling command for {device_id}: {e}")

            # Send error response
            if cmd_id:
                self._send_command_response(device_id, cmd_id, False, str(e))

    def _handle_device_get(self, topic: str, payload: Dict[str, Any]):
        """
        Handle device state get request

        Immediately query and publish current state
        """
        parts = topic.split('/')
        device_id = parts[-2] if len(parts) >= 2 else 'unknown'

        logger.info(f"Get request for device {device_id}")
        self._update_device_state(device_id)

    def _handle_meta_request(self, topic: str, payload: Dict[str, Any]):
        """Handle meta information requests"""
        request_type = topic.split('/')[-1]

        if request_type == "devices_list":
            # Return list of devices
            # In a real connector, this would query backend services
            devices = [
                {
                    "device_id": "demo_device",
                    "global_id": f"{INSTANCE_NAME}_demo_device",
                    "model": "multi-process-template",
                    "enabled": True,
                    "online": all(self.services_healthy.values())
                }
            ]

            topic_path = f"meta/devices_list"
            self.mqtt.publish(
                f"{self.mqtt.base_topic}/v1/instances/{INSTANCE_NAME}/{topic_path}",
                devices,
                retain=True
            )

        elif request_type == "info":
            # Return instance information
            info = {
                "instance_id": INSTANCE_NAME,
                "connector_type": CONNECTOR_TYPE,
                "services": self.services_healthy,
                "uptime": time.time()  # Should track actual uptime
            }

            topic_path = f"meta/info"
            self.mqtt.publish(
                f"{self.mqtt.base_topic}/v1/instances/{INSTANCE_NAME}/{topic_path}",
                info,
                retain=True
            )

    def _call_python_service(self, endpoint: str, data: Dict[str, Any]) -> Any:
        """Make HTTP request to Python service"""
        try:
            resp = requests.post(
                f"{PYTHON_SERVICE_URL}/{endpoint}",
                json=data,
                timeout=5
            )
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            logger.error(f"Error calling Python service: {e}")
            return None

    def _call_nodejs_service(self, endpoint: str, data: Dict[str, Any]) -> Any:
        """Make HTTP request to Node.js service"""
        try:
            resp = requests.post(
                f"{NODEJS_SERVICE_URL}/{endpoint}",
                json=data,
                timeout=5
            )
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            logger.error(f"Error calling Node.js service: {e}")
            return None

    def _update_device_state(self, device_id: str):
        """Query backend services and publish device state to MQTT"""
        try:
            # Gather state from all backend services
            python_status = self._call_python_service('status', {})
            nodejs_status = self._call_nodejs_service('status', {})

            # Combine into device state
            state = {
                'online': all(self.services_healthy.values()),
                'last_update': datetime.now().isoformat(),
                'python_service': python_status or {},
                'nodejs_service': nodejs_status or {}
            }

            # Only publish if state changed (avoid redundant updates)
            if state != self.last_state.get(device_id):
                self.mqtt.publish_state(device_id, state)
                self.last_state[device_id] = state
                logger.debug(f"Published state for {device_id}")

        except Exception as e:
            logger.error(f"Error updating device state: {e}")

    def _send_command_response(self, device_id: str, cmd_id: str,
                               success: bool, result: Any):
        """Send command response following IoT2MQTT contract"""
        response = {
            "cmd_id": cmd_id,
            "status": "success" if success else "error",
            "timestamp": datetime.now().isoformat()
        }

        if success:
            response["result"] = result
        else:
            response["error"] = str(result)

        response_topic = f"{self.mqtt.base_topic}/v1/instances/{INSTANCE_NAME}/devices/{device_id}/cmd/response"
        self.mqtt.publish(response_topic, response, retain=False)

    def _coordination_loop(self):
        """Main loop: poll services and publish state updates"""
        logger.info(f"Coordination loop started (interval: {UPDATE_INTERVAL}s)")

        while True:
            try:
                # Update device states periodically
                # In a real connector, you would iterate over configured devices
                self._update_device_state('demo_device')

                # Sleep for update interval
                time.sleep(UPDATE_INTERVAL)

            except KeyboardInterrupt:
                logger.info("Received shutdown signal")
                break
            except Exception as e:
                logger.error(f"Error in coordination loop: {e}")
                time.sleep(5)  # Back off on error

        # Cleanup
        logger.info("Stopping MQTT bridge")
        self.mqtt.disconnect()


# ============================================================================
# Main Entry Point
# ============================================================================

def main():
    """Main entry point for MQTT bridge"""
    logger.info("=" * 60)
    logger.info("Multi-Process Connector - MQTT Bridge")
    logger.info("=" * 60)

    # Create and start bridge
    bridge = MQTTBridge()

    try:
        bridge.start()
    except KeyboardInterrupt:
        logger.info("Shutdown requested")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
