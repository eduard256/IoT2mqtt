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
            config_path: Path to configuration file
            instance_name: Instance name (from environment if not provided)
        """
        # Get instance name
        self.instance_name = instance_name or os.getenv('INSTANCE_NAME')
        if not self.instance_name:
            raise ValueError("Instance name not provided")
        
        # Load configuration
        self.config = self._load_config(config_path)
        self.instance_id = self.config.get('instance_id', self.instance_name)
        
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
        """Load configuration from file"""
        if not config_path:
            # Try to find config in instances directory
            config_path = f"/app/instances/{self.instance_name}.json"
            if not os.path.exists(config_path):
                # Fallback to local instances directory
                config_path = f"instances/{self.instance_name}.json"
        
        if not os.path.exists(config_path):
            raise FileNotFoundError(f"Configuration file not found: {config_path}")
        
        with open(config_path) as f:
            config = json.load(f)
        
        # Load secrets if available
        self._load_secrets(config)
        
        return config
    
    def _load_secrets(self, config: Dict[str, Any]):
        """Load secrets from Docker secrets"""
        # Use instance_name for secrets since instance_id is not yet loaded
        instance_secret = f"/run/secrets/{self.instance_name}_creds"
        
        if os.path.exists(instance_secret):
            with open(instance_secret) as f:
                for line in f:
                    if '=' in line:
                        key, value = line.strip().split('=', 1)
                        # Update config with secret values
                        if 'connection' not in config:
                            config['connection'] = {}
                        config['connection'][key] = value
    
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
        if not self.mqtt.connect():
            logger.error("Failed to connect to MQTT broker")
            return False
        
        # Subscribe to command topics
        self._setup_subscriptions()
        
        # Initialize connection to devices
        try:
            self.initialize_connection()
        except Exception as e:
            logger.error(f"Failed to initialize connection: {e}")
            return False
        
        # Start main loop
        self.running = True
        self.main_thread = threading.Thread(target=self._main_loop, daemon=True)
        self.main_thread.start()
        
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
        """Setup MQTT subscriptions"""
        # Subscribe to device commands
        self.mqtt.subscribe("devices/+/cmd", self._handle_command)
        self.mqtt.subscribe("devices/+/get", self._handle_get)
        
        # Subscribe to group commands
        self.mqtt.subscribe("groups/+/cmd", self._handle_group_command)
        
        # Subscribe to bridge requests
        self.mqtt.subscribe("meta/request/+", self._handle_meta_request)
    
    def _main_loop(self):
        """Main loop for polling devices"""
        error_count = 0
        max_errors = 5
        
        while self.running:
            try:
                # Update all devices
                for device_config in self.config.get('devices', []):
                    if not device_config.get('enabled', True):
                        continue
                    
                    device_id = device_config['device_id']
                    
                    try:
                        # Get device state
                        state = self.get_device_state(device_id, device_config)
                        
                        if state is not None:
                            # Publish state
                            self.mqtt.publish_state(device_id, state)
                            
                            # Store in cache
                            self.devices[device_id] = {
                                'state': state,
                                'last_update': datetime.now(),
                                'config': device_config
                            }
                            
                            # Reset error count on success
                            error_count = 0
                            
                    except Exception as e:
                        logger.error(f"Error updating device {device_id}: {e}")
                        self.mqtt.publish_error(
                            device_id,
                            "UPDATE_ERROR",
                            str(e),
                            severity="warning"
                        )
                        error_count += 1
                        
                        if error_count >= max_errors:
                            logger.critical(f"Too many errors, stopping connector")
                            self.running = False
                            break
                
                # Sleep for update interval
                time.sleep(self.update_interval)
                
            except Exception as e:
                logger.error(f"Error in main loop: {e}")
                error_count += 1
                
                if error_count >= max_errors:
                    logger.critical("Too many errors, stopping connector")
                    break
                
                time.sleep(5)  # Wait before retry
    
    def _handle_command(self, topic: str, payload: Dict[str, Any]):
        """Handle device command"""
        # Extract device ID from topic
        parts = topic.split('/')
        device_id = parts[-2] if len(parts) > 2 else None
        
        if not device_id:
            logger.warning(f"Invalid command topic: {topic}")
            return
        
        # Check timestamp for ordering
        cmd_timestamp = payload.get('timestamp')
        if cmd_timestamp:
            try:
                # Parse timestamp and make it timezone-aware if needed
                cmd_time = datetime.fromisoformat(cmd_timestamp.replace('Z', '+00:00'))
                # Convert to naive datetime for comparison
                if cmd_time.tzinfo:
                    cmd_time = cmd_time.replace(tzinfo=None)
                if (datetime.now() - cmd_time).total_seconds() > 30:
                    logger.warning(f"Ignoring outdated command for {device_id}")
                    return
            except Exception as e:
                logger.debug(f"Error parsing timestamp: {e}")
        
        # Find device configuration
        device_config = None
        for dev in self.config.get('devices', []):
            if dev['device_id'] == device_id:
                device_config = dev
                break
        
        if not device_config:
            logger.warning(f"Device {device_id} not found")
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
            
            result = self.set_device_state(device_id, device_config, command_values)
            
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
            logger.error(f"Error handling command for {device_id}: {e}")
            
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
        """Handle get request"""
        # Extract device ID
        parts = topic.split('/')
        device_id = parts[-2] if len(parts) > 2 else None
        
        if not device_id:
            return
        
        # Get current state from cache or device
        if device_id in self.devices:
            state = self.devices[device_id]['state']
        else:
            # Try to get fresh state
            device_config = None
            for dev in self.config.get('devices', []):
                if dev['device_id'] == device_id:
                    device_config = dev
                    break
            
            if device_config:
                try:
                    state = self.get_device_state(device_id, device_config)
                except Exception as e:
                    logger.error(f"Error getting state for {device_id}: {e}")
                    state = None
            else:
                state = None
        
        if state:
            # Filter properties if requested
            if 'properties' in payload:
                filtered_state = {k: v for k, v in state.items() 
                                if k in payload['properties']}
                state = filtered_state
            
            # Publish current state
            self.mqtt.publish_state(device_id, state)
    
    def _handle_group_command(self, topic: str, payload: Dict[str, Any]):
        """Handle group command"""
        # Extract group name
        parts = topic.split('/')
        group_name = parts[-2] if len(parts) > 2 else None
        
        if not group_name:
            return
        
        # Find group configuration
        group_config = None
        for group in self.config.get('groups', []):
            if group['group_id'] == group_name:
                group_config = group
                break
        
        if not group_config:
            logger.warning(f"Group {group_name} not found")
            return
        
        # Apply command to all devices in group
        for device_id in group_config.get('devices', []):
            # Find device config
            device_config = None
            for dev in self.config.get('devices', []):
                if dev['device_id'] == device_id:
                    device_config = dev
                    break
            
            if device_config and device_config.get('enabled', True):
                try:
                    self.set_device_state(device_id, device_config, payload.get('values', {}))
                except Exception as e:
                    logger.error(f"Error setting state for {device_id} in group {group_name}: {e}")
    
    def _handle_meta_request(self, topic: str, payload: Dict[str, Any]):
        """Handle meta requests"""
        request_type = topic.split('/')[-1]
        
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
            
        elif request_type == "info":
            # Return instance information
            info = {
                "instance_id": self.instance_id,
                "connector_type": self.config.get('connector_type', 'unknown'),
                "devices_count": len(self.config.get('devices', [])),
                "groups_count": len(self.config.get('groups', [])),
                "uptime": time.time()  # Should track actual uptime
            }
            
            response_topic = f"{self.mqtt.base_topic}/v1/instances/{self.instance_id}/meta/info"
            self.mqtt.publish(response_topic, info, retain=True)
    
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