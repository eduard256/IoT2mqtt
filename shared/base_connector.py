"""
Base connector class for IoT2MQTT
All connectors should inherit from this class
"""

import threading
import time
import logging
import json
import os
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from datetime import datetime
from pathlib import Path

try:
    from .mqtt_client import MQTTClient
except ImportError:
    from mqtt_client import MQTTClient

logger = logging.getLogger(__name__)

class BaseConnector(ABC):
    """Base class for all IoT2MQTT connectors"""
    
    def __init__(self, config_path: str = None, instance_name: str = None):
        """
        Initialize base connector

        Args:
            config_path: Path to configuration file (optional, auto-detected if not provided)
            instance_name: Instance name (optional, read from INSTANCE_NAME env var if not provided)

        Environment Variables:
            INSTANCE_NAME: Required. Unique identifier for this connector instance.
            CONNECTOR_TYPE: Optional. Type of connector (e.g., 'yeelight', 'cameras').
                           Used for logging and validation purposes.
            MODE: Optional. Operating mode - 'production' or 'development'. Default: 'production'.
            LOG_LEVEL: Optional. Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL). Default: 'INFO'.

            MQTT connection parameters (loaded from .env file):
            MQTT_HOST, MQTT_PORT, MQTT_USERNAME, MQTT_PASSWORD, MQTT_BASE_TOPIC, etc.
            These are automatically loaded by MQTTClient from environment.

        Configuration precedence:
            1. Explicit constructor parameters (highest priority)
            2. Configuration file values
            3. Environment variables (lowest priority)
        """
        # Get instance name
        self.instance_name = instance_name or os.getenv('INSTANCE_NAME')
        if not self.instance_name:
            raise ValueError("Instance name not provided via parameter or INSTANCE_NAME environment variable")

        # Get optional connector type for logging/validation
        self.connector_type = os.getenv('CONNECTOR_TYPE')

        logger.info(f"Initializing BaseConnector for instance: {self.instance_name}")
        if self.connector_type:
            logger.info(f"Connector type: {self.connector_type}")

        # Load configuration
        self.config = self._load_config(config_path)
        self.instance_id = self.config.get('instance_id', self.instance_name)

        logger.info(f"Instance ID resolved to: {self.instance_id}")
        
        # Initialize MQTT client
        self.mqtt = MQTTClient(
            instance_id=self.instance_id,
            qos=self.config.get('mqtt', {}).get('qos', 1),
            retain_state=self.config.get('mqtt', {}).get('retain_state', True)
        )
        
        # Internal state
        self.running = False
        self.main_thread = None
        self.devices = {}
        self.update_interval = self.config.get('update_interval', 10)
        
        # Setup logging
        self._setup_logging()
    
    def _load_config(self, config_path: str = None) -> Dict[str, Any]:
        """
        Load configuration from file

        Path resolution logic:
        - If config_path is explicitly provided, use it directly
        - Otherwise, auto-detect based on environment:
          1. Production: /app/instances/{instance_name}.json
          2. Development: instances/{instance_name}.json (local fallback)

        Note on Docker mounting:
        The docker_service.py mounts connector-specific instance directories to /app/instances/
        For example, host path /opt/iot2mqtt/instances/yeelight/ is mounted to /app/instances/
        This means yeelight_instance1.json appears at /app/instances/yeelight_instance1.json
        The connector type subdirectory is eliminated by the mount point.

        Args:
            config_path: Explicit path to configuration file (optional)

        Returns:
            Configuration dictionary loaded from JSON file

        Raises:
            FileNotFoundError: If configuration file cannot be found at any attempted path
        """
        attempted_paths = []

        if not config_path:
            # Auto-detect configuration path
            # Production path (inside Docker container)
            config_path = f"/app/instances/{self.instance_name}.json"
            attempted_paths.append(config_path)

            logger.debug(f"Attempting to load config from: {config_path}")

            if not os.path.exists(config_path):
                # Development fallback (local file system)
                config_path = f"instances/{self.instance_name}.json"
                attempted_paths.append(config_path)
                logger.debug(f"Production path not found, trying development path: {config_path}")
        else:
            logger.info(f"Using explicitly provided config path: {config_path}")
            attempted_paths.append(config_path)

        if not os.path.exists(config_path):
            error_msg = f"Configuration file not found. Attempted paths: {', '.join(attempted_paths)}"
            logger.error(error_msg)
            raise FileNotFoundError(error_msg)

        logger.info(f"Loading configuration from: {config_path}")

        try:
            with open(config_path) as f:
                config = json.load(f)
            logger.debug(f"Successfully loaded configuration with {len(config)} top-level keys")
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in configuration file {config_path}: {e}")
            raise
        except Exception as e:
            logger.error(f"Error reading configuration file {config_path}: {e}")
            raise

        # Load secrets if available (non-fatal)
        self._load_secrets(config)

        return config
    
    def _load_secrets(self, config: Dict[str, Any]):
        """
        Load secrets from Docker secrets (optional, non-fatal)

        Docker secrets are mounted at /run/secrets/{instance_name}_creds
        Format: KEY=VALUE pairs, one per line
        Secrets are merged into config['connection'] section

        Args:
            config: Configuration dictionary to merge secrets into
        """
        # Use instance_name for secrets since instance_id is not yet loaded
        instance_secret = f"/run/secrets/{self.instance_name}_creds"

        if os.path.exists(instance_secret):
            logger.info(f"Loading secrets from: {instance_secret}")
            try:
                with open(instance_secret) as f:
                    secrets_loaded = 0
                    for line in f:
                        if '=' in line:
                            key, value = line.strip().split('=', 1)
                            # Update config with secret values
                            if 'connection' not in config:
                                config['connection'] = {}
                            config['connection'][key] = value
                            secrets_loaded += 1
                logger.info(f"Loaded {secrets_loaded} secret(s) from Docker secrets")
            except Exception as e:
                logger.warning(f"Error loading secrets from {instance_secret}: {e}")
        else:
            logger.debug(f"No Docker secrets file found at {instance_secret} (this is optional)")
    
    def _setup_logging(self):
        """Setup logging for connector"""
        log_level = os.getenv('LOG_LEVEL', 'INFO')
        logging.basicConfig(
            level=getattr(logging, log_level),
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
    
    def start(self):
        """Start the connector"""
        if self.running:
            logger.warning("Connector already running")
            return

        logger.info(f"Starting connector for instance {self.instance_id}")

        # Connect to MQTT
        mqtt_host = os.getenv('MQTT_HOST', self.mqtt.host)
        mqtt_port = os.getenv('MQTT_PORT', str(self.mqtt.port))
        logger.info(f"Connecting to MQTT broker at {mqtt_host}:{mqtt_port}")

        if not self.mqtt.connect():
            logger.error(f"Failed to connect to MQTT broker at {mqtt_host}:{mqtt_port}")
            return False

        logger.info("MQTT connection established successfully")

        # Subscribe to command topics
        self._setup_subscriptions()

        # Initialize connection to devices
        logger.info("Initializing connector-specific connections...")
        try:
            self.initialize_connection()
            logger.info("Connector-specific initialization completed")
        except Exception as e:
            logger.error(f"Failed to initialize connection: {e}", exc_info=True)
            return False

        # Start main loop
        self.running = True
        self.main_thread = threading.Thread(target=self._main_loop, daemon=True)
        self.main_thread.start()
        logger.info(f"Main polling loop started with interval: {self.update_interval}s")

        logger.info("Connector started successfully")
        return True
    
    def stop(self):
        """Stop the connector"""
        logger.info("Stopping connector")
        self.running = False
        
        # Wait for main thread to finish
        if self.main_thread:
            self.main_thread.join(timeout=10)
        
        # Clean up connection
        try:
            self.cleanup_connection()
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")
        
        # Disconnect from MQTT
        self.mqtt.disconnect()
        
        logger.info("Connector stopped")
    
    def _setup_subscriptions(self):
        """Setup MQTT subscriptions for command handling"""
        base = f"{self.mqtt.base_topic}/v1/instances/{self.instance_id}"

        # Subscribe to device commands
        device_cmd_topic = "devices/+/cmd"
        device_get_topic = "devices/+/get"
        logger.info(f"Subscribing to device commands: {base}/{device_cmd_topic}")
        self.mqtt.subscribe(device_cmd_topic, self._handle_command)
        logger.info(f"Subscribing to device state requests: {base}/{device_get_topic}")
        self.mqtt.subscribe(device_get_topic, self._handle_get)

        # Subscribe to group commands
        group_cmd_topic = "groups/+/cmd"
        logger.info(f"Subscribing to group commands: {base}/{group_cmd_topic}")
        self.mqtt.subscribe(group_cmd_topic, self._handle_group_command)

        # Subscribe to bridge requests
        meta_topic = "meta/request/+"
        logger.info(f"Subscribing to meta requests: {base}/{meta_topic}")
        self.mqtt.subscribe(meta_topic, self._handle_meta_request)

        logger.info("All MQTT subscriptions established")
    
    def _main_loop(self):
        """Main loop for polling devices"""
        error_count = 0
        max_errors = 5
        device_count = len([d for d in self.config.get('devices', []) if d.get('enabled', True)])
        logger.info(f"Starting main polling loop for {device_count} enabled device(s)")

        while self.running:
            try:
                # Update all devices
                for device_config in self.config.get('devices', []):
                    if not device_config.get('enabled', True):
                        continue

                    device_id = device_config['device_id']

                    try:
                        # Get device state
                        logger.debug(f"Polling device {device_id}")
                        state = self.get_device_state(device_id, device_config)

                        if state is not None:
                            # Publish state
                            self.mqtt.publish_state(device_id, state)
                            logger.debug(f"Published state for device {device_id}")

                            # Store in cache
                            self.devices[device_id] = {
                                'state': state,
                                'last_update': datetime.now(),
                                'config': device_config
                            }

                            # Reset error count on success
                            error_count = 0

                    except Exception as e:
                        logger.error(f"Error updating device {device_id}: {e}", exc_info=True)
                        self.mqtt.publish_error(
                            device_id,
                            "UPDATE_ERROR",
                            str(e),
                            severity="warning"
                        )
                        error_count += 1

                        if error_count >= max_errors:
                            logger.critical(f"Too many consecutive errors ({max_errors}), stopping connector")
                            self.running = False
                            break

                # Sleep for update interval
                time.sleep(self.update_interval)

            except Exception as e:
                logger.error(f"Error in main loop: {e}", exc_info=True)
                error_count += 1

                if error_count >= max_errors:
                    logger.critical(f"Too many consecutive errors ({max_errors}), stopping connector")
                    break

                time.sleep(5)  # Wait before retry

        logger.info("Main polling loop terminated")
    
    def _handle_command(self, topic: str, payload: Dict[str, Any]):
        """Handle device command"""
        # Extract device ID from topic
        parts = topic.split('/')
        device_id = parts[-2] if len(parts) > 2 else None

        if not device_id:
            logger.warning(f"Invalid command topic format: {topic}")
            return

        logger.info(f"Received command for device {device_id}: {list(payload.keys())}")

        # Check timestamp for ordering
        cmd_timestamp = payload.get('timestamp')
        if cmd_timestamp:
            try:
                # Parse timestamp and make it timezone-aware if needed
                cmd_time = datetime.fromisoformat(cmd_timestamp.replace('Z', '+00:00'))
                # Convert to naive datetime for comparison
                if cmd_time.tzinfo:
                    cmd_time = cmd_time.replace(tzinfo=None)
                age_seconds = (datetime.now() - cmd_time).total_seconds()
                if age_seconds > 30:
                    logger.warning(f"Ignoring outdated command for {device_id} (age: {age_seconds:.1f}s)")
                    return
            except Exception as e:
                logger.debug(f"Error parsing command timestamp: {e}")

        # Find device configuration
        device_config = None
        for dev in self.config.get('devices', []):
            if dev['device_id'] == device_id:
                device_config = dev
                break

        if not device_config:
            logger.warning(f"Command received for unknown device: {device_id}")
            return

        # Apply command
        try:
            # Extract command values - support both direct payload and 'values' wrapper
            if 'values' in payload:
                command_values = payload['values']
            else:
                # Remove metadata fields to get actual command values
                command_values = {k: v for k, v in payload.items()
                                if k not in ['timestamp', 'id', 'timeout']}

            logger.debug(f"Applying command to {device_id}: {command_values}")
            result = self.set_device_state(device_id, device_config, command_values)
            logger.info(f"Command applied to {device_id}: {'success' if result else 'failed'}")

            # Send response if requested
            if payload.get('id'):
                response = {
                    "cmd_id": payload['id'],
                    "status": "success" if result else "error",
                    "timestamp": datetime.now().isoformat()
                }
                response_topic = f"devices/{device_id}/cmd/response"
                self.mqtt.publish(
                    f"{self.mqtt.base_topic}/v1/instances/{self.instance_id}/{response_topic}",
                    response,
                    retain=False
                )

        except Exception as e:
            logger.error(f"Error handling command for {device_id}: {e}", exc_info=True)

            # Send error response
            if payload.get('id'):
                response = {
                    "cmd_id": payload['id'],
                    "status": "error",
                    "error": str(e),
                    "timestamp": datetime.now().isoformat()
                }
                response_topic = f"devices/{device_id}/cmd/response"
                self.mqtt.publish(
                    f"{self.mqtt.base_topic}/v1/instances/{self.instance_id}/{response_topic}",
                    response,
                    retain=False
                )
    
    def _handle_get(self, topic: str, payload: Dict[str, Any]):
        """Handle get request for device state"""
        # Extract device ID
        parts = topic.split('/')
        device_id = parts[-2] if len(parts) > 2 else None

        if not device_id:
            logger.warning(f"Invalid get request topic format: {topic}")
            return

        logger.info(f"Received state request for device {device_id}")

        # Get current state from cache or device
        if device_id in self.devices:
            state = self.devices[device_id]['state']
            logger.debug(f"Serving cached state for {device_id}")
        else:
            # Try to get fresh state
            logger.debug(f"No cached state for {device_id}, querying device")
            device_config = None
            for dev in self.config.get('devices', []):
                if dev['device_id'] == device_id:
                    device_config = dev
                    break

            if device_config:
                try:
                    state = self.get_device_state(device_id, device_config)
                except Exception as e:
                    logger.error(f"Error getting state for {device_id}: {e}", exc_info=True)
                    state = None
            else:
                logger.warning(f"State request for unknown device: {device_id}")
                state = None

        if state:
            # Filter properties if requested
            if 'properties' in payload:
                filtered_state = {k: v for k, v in state.items()
                                if k in payload['properties']}
                state = filtered_state
                logger.debug(f"Filtered state for {device_id}: {list(filtered_state.keys())}")

            # Publish current state
            self.mqtt.publish_state(device_id, state)
            logger.info(f"Published state for {device_id}")
        else:
            logger.warning(f"No state available for {device_id}")
    
    def _handle_group_command(self, topic: str, payload: Dict[str, Any]):
        """Handle group command (apply command to multiple devices)"""
        # Extract group name
        parts = topic.split('/')
        group_name = parts[-2] if len(parts) > 2 else None

        if not group_name:
            logger.warning(f"Invalid group command topic format: {topic}")
            return

        logger.info(f"Received group command for group {group_name}")

        # Find group configuration
        group_config = None
        for group in self.config.get('groups', []):
            if group['group_id'] == group_name:
                group_config = group
                break

        if not group_config:
            logger.warning(f"Group command for unknown group: {group_name}")
            return

        device_list = group_config.get('devices', [])
        logger.info(f"Applying group command to {len(device_list)} device(s) in group {group_name}")

        # Apply command to all devices in group
        success_count = 0
        for device_id in device_list:
            # Find device config
            device_config = None
            for dev in self.config.get('devices', []):
                if dev['device_id'] == device_id:
                    device_config = dev
                    break

            if device_config and device_config.get('enabled', True):
                try:
                    self.set_device_state(device_id, device_config, payload.get('values', {}))
                    success_count += 1
                except Exception as e:
                    logger.error(f"Error setting state for {device_id} in group {group_name}: {e}")
            else:
                logger.debug(f"Skipping disabled or unknown device {device_id} in group {group_name}")

        logger.info(f"Group command applied to {success_count}/{len(device_list)} devices in {group_name}")
    
    def _handle_meta_request(self, topic: str, payload: Dict[str, Any]):
        """Handle meta requests (instance/device information queries)"""
        request_type = topic.split('/')[-1]
        logger.info(f"Received meta request: {request_type}")

        if request_type == "devices_list":
            # Return list of devices
            devices_list = []
            for device in self.config.get('devices', []):
                devices_list.append({
                    "device_id": device['device_id'],
                    "global_id": f"{self.instance_id}_{device['device_id']}",
                    "model": device.get('model', 'unknown'),
                    "enabled": device.get('enabled', True),
                    "online": device['device_id'] in self.devices
                })

            response_topic = f"{self.mqtt.base_topic}/v1/instances/{self.instance_id}/meta/devices_list"
            self.mqtt.publish(response_topic, devices_list, retain=True)
            logger.info(f"Published devices list: {len(devices_list)} device(s)")

        elif request_type == "info":
            # Return instance information
            info = {
                "instance_id": self.instance_id,
                "connector_type": self.config.get('connector_type', self.connector_type or 'unknown'),
                "devices_count": len(self.config.get('devices', [])),
                "groups_count": len(self.config.get('groups', [])),
                "uptime": time.time()  # Should track actual uptime
            }

            response_topic = f"{self.mqtt.base_topic}/v1/instances/{self.instance_id}/meta/info"
            self.mqtt.publish(response_topic, info, retain=True)
            logger.info(f"Published instance info for {self.instance_id}")
        else:
            logger.warning(f"Unknown meta request type: {request_type}")
    
    @abstractmethod
    def initialize_connection(self):
        """
        Initialize connection to devices/service
        This method must be implemented by each connector
        """
        pass
    
    @abstractmethod
    def cleanup_connection(self):
        """
        Clean up connection to devices/service
        This method must be implemented by each connector
        """
        pass
    
    @abstractmethod
    def get_device_state(self, device_id: str, device_config: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Get current state of a device
        
        Args:
            device_id: Device identifier
            device_config: Device configuration
            
        Returns:
            State dictionary or None if device unavailable
        """
        pass
    
    @abstractmethod
    def set_device_state(self, device_id: str, device_config: Dict[str, Any], 
                        state: Dict[str, Any]) -> bool:
        """
        Set device state
        
        Args:
            device_id: Device identifier
            device_config: Device configuration
            state: New state to set
            
        Returns:
            True if successful, False otherwise
        """
        pass
    
    def discover_devices(self) -> List[Dict[str, Any]]:
        """
        Discover new devices (optional, override if supported)
        
        Returns:
            List of discovered devices
        """
        return []
    
    def run_forever(self):
        """Run connector until interrupted"""
        try:
            self.start()
            
            # Keep running until interrupted
            while self.running:
                time.sleep(1)
                
        except KeyboardInterrupt:
            logger.info("Interrupted by user")
        finally:
            self.stop()