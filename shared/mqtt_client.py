"""
MQTT Client with advanced features for IoT2MQTT
Supports LWT, timestamp ordering, response TTL
"""

import json
import time
import threading
import os
from typing import Dict, Callable, Any, Optional
from datetime import datetime, timedelta
import logging
import paho.mqtt.client as mqtt
from dataclasses import dataclass
from queue import Queue, Empty

# Try to load dotenv for .env file support
try:
    from dotenv import load_dotenv
    # Load .env file if it exists
    if os.path.exists('/app/.env'):
        load_dotenv('/app/.env')
except ImportError:
    # dotenv not installed, will use environment variables only
    pass

logger = logging.getLogger(__name__)

@dataclass
class CommandInfo:
    """Information about a command"""
    id: str
    timestamp: datetime
    timeout: float
    callback: Optional[Callable] = None

class MQTTClient:
    """Advanced MQTT client for IoT2MQTT connectors"""
    
    def __init__(self, 
                 instance_id: str,
                 base_topic: str = None,
                 host: str = None,
                 port: int = None,
                 username: str = None,
                 password: str = None,
                 qos: int = 1,
                 retain_state: bool = True,
                 response_ttl: int = 300):  # 5 minutes TTL for responses
        """
        Initialize MQTT client
        
        Args:
            instance_id: Unique instance identifier
            base_topic: Base MQTT topic (from env if not provided)
            host: MQTT broker host (from env if not provided)
            port: MQTT broker port (from env if not provided)
            username: MQTT username (from env if not provided)
            password: MQTT password (from env if not provided)
            qos: Quality of Service level
            retain_state: Whether to retain state messages
            response_ttl: TTL for response messages in seconds
        """
        self.instance_id = instance_id
        
        # Load from environment if not provided
        self.base_topic = base_topic or os.getenv('MQTT_BASE_TOPIC', 'IoT2mqtt')
        self.host = host or os.getenv('MQTT_HOST', 'localhost')
        self.port = port or int(os.getenv('MQTT_PORT', '1883'))
        self.username = username or os.getenv('MQTT_USERNAME')
        self.password = password or os.getenv('MQTT_PASSWORD')
        
        # Load instance-specific credentials if available
        instance_secret_file = f"/run/secrets/{instance_id}_mqtt"
        if os.path.exists(instance_secret_file):
            with open(instance_secret_file) as f:
                lines = f.readlines()
                for line in lines:
                    if line.startswith('username='):
                        self.username = line.split('=', 1)[1].strip()
                    elif line.startswith('password='):
                        self.password = line.split('=', 1)[1].strip()
        
        self.qos = qos
        self.retain_state = retain_state
        self.response_ttl = response_ttl
        
        # MQTT client setup
        client_id = f"{os.getenv('MQTT_CLIENT_PREFIX', 'iot2mqtt')}_{instance_id}"
        self.client = mqtt.Client(client_id=client_id)
        
        # Set callbacks
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self.client.on_message = self._on_message
        
        # Authentication
        if self.username and self.password:
            self.client.username_pw_set(self.username, self.password)
        
        # Last Will and Testament
        status_topic = f"{self.base_topic}/v1/instances/{instance_id}/status"
        self.client.will_set(status_topic, "offline", qos=1, retain=True)
        
        # Internal state
        self.connected = False
        self.subscriptions: Dict[str, Callable] = {}
        self.pending_commands: Dict[str, CommandInfo] = {}
        self.response_cleaner_thread = None
        self.stop_cleaner = threading.Event()
        
        # Start response cleaner thread
        self._start_response_cleaner()
    
    def _start_response_cleaner(self):
        """Start thread to clean old responses"""
        def cleaner():
            while not self.stop_cleaner.is_set():
                now = datetime.now()
                expired = []
                
                for cmd_id, info in self.pending_commands.items():
                    if now - info.timestamp > timedelta(seconds=self.response_ttl):
                        expired.append(cmd_id)
                
                for cmd_id in expired:
                    del self.pending_commands[cmd_id]
                    logger.debug(f"Cleaned expired command: {cmd_id}")
                
                self.stop_cleaner.wait(60)  # Check every minute
        
        self.response_cleaner_thread = threading.Thread(target=cleaner, daemon=True)
        self.response_cleaner_thread.start()
    
    def connect(self, retry_interval: int = 5, max_retries: int = None):
        """
        Connect to MQTT broker with retry logic
        
        Args:
            retry_interval: Seconds between retry attempts
            max_retries: Maximum number of retries (None for infinite)
        """
        retries = 0
        while not self.connected and (max_retries is None or retries < max_retries):
            try:
                logger.info(f"Connecting to MQTT broker {self.host}:{self.port}")
                self.client.connect(self.host, self.port, keepalive=60)
                self.client.loop_start()
                
                # Wait for connection
                timeout = time.time() + 10
                while not self.connected and time.time() < timeout:
                    time.sleep(0.1)
                
                if self.connected:
                    # Publish online status
                    status_topic = f"{self.base_topic}/v1/instances/{self.instance_id}/status"
                    self.client.publish(status_topic, "online", qos=1, retain=True)
                    logger.info("Successfully connected to MQTT broker")
                    return True
                    
            except Exception as e:
                logger.error(f"Failed to connect: {e}")
                retries += 1
                if max_retries and retries >= max_retries:
                    raise
                time.sleep(retry_interval)
        
        return False
    
    def disconnect(self):
        """Disconnect from MQTT broker"""
        logger.info("Disconnecting from MQTT broker")
        
        # Publish offline status
        status_topic = f"{self.base_topic}/v1/instances/{self.instance_id}/status"
        self.client.publish(status_topic, "offline", qos=1, retain=True)
        
        # Stop cleaner thread
        self.stop_cleaner.set()
        
        # Disconnect
        self.client.loop_stop()
        self.client.disconnect()
        self.connected = False
    
    def _on_connect(self, client, userdata, flags, rc):
        """Callback for connection"""
        if rc == 0:
            self.connected = True
            logger.info("Connected to MQTT broker")
            
            # Resubscribe to all topics
            for topic in self.subscriptions:
                client.subscribe(topic, qos=self.qos)
                logger.debug(f"Resubscribed to {topic}")
        else:
            logger.error(f"Connection failed with code {rc}")
    
    def _on_disconnect(self, client, userdata, rc):
        """Callback for disconnection"""
        self.connected = False
        if rc != 0:
            logger.warning(f"Unexpected disconnection (code {rc}), will retry")
    
    def _on_message(self, client, userdata, msg):
        """Callback for incoming messages"""
        try:
            topic = msg.topic
            
            # Try to parse as JSON
            try:
                payload = json.loads(msg.payload.decode())
            except:
                payload = msg.payload.decode()
            
            # Check if it's a response to a pending command
            if "/cmd/response" in topic:
                cmd_id = payload.get('cmd_id') if isinstance(payload, dict) else None
                if cmd_id and cmd_id in self.pending_commands:
                    cmd_info = self.pending_commands[cmd_id]
                    if cmd_info.callback:
                        cmd_info.callback(payload)
                    del self.pending_commands[cmd_id]
            
            # Call registered handler
            for pattern, handler in self.subscriptions.items():
                if mqtt.topic_matches_sub(pattern, topic):
                    try:
                        handler(topic, payload)
                    except Exception as e:
                        logger.error(f"Error in message handler: {e}")
                        
        except Exception as e:
            logger.error(f"Error processing message: {e}")
    
    def subscribe(self, topic_pattern: str, handler: Callable):
        """
        Subscribe to MQTT topic with handler
        
        Args:
            topic_pattern: MQTT topic pattern (can include wildcards)
            handler: Callback function(topic, payload)
        """
        full_topic = f"{self.base_topic}/v1/instances/{self.instance_id}/{topic_pattern}"
        self.subscriptions[full_topic] = handler
        
        if self.connected:
            self.client.subscribe(full_topic, qos=self.qos)
            logger.debug(f"Subscribed to {full_topic}")
    
    def publish_state(self, device_id: str, state: Dict[str, Any], retain: bool = None):
        """
        Publish device state with timestamp
        
        Args:
            device_id: Device identifier
            state: State dictionary
            retain: Override default retain setting
        """
        if retain is None:
            retain = self.retain_state
        
        payload = {
            "timestamp": datetime.now().isoformat(),
            "device_id": device_id,
            "state": state
        }
        
        topic = f"{self.base_topic}/v1/instances/{self.instance_id}/devices/{device_id}/state"
        self.publish(topic, payload, retain=retain)
        
        # Also publish individual properties for selective subscription
        for key, value in state.items():
            prop_topic = f"{self.base_topic}/v1/instances/{self.instance_id}/devices/{device_id}/state/{key}"
            self.publish(prop_topic, value, retain=retain)
    
    def publish_event(self, device_id: str, event: str, data: Any = None):
        """
        Publish device event
        
        Args:
            device_id: Device identifier
            event: Event name
            data: Event data
        """
        payload = {
            "timestamp": datetime.now().isoformat(),
            "event": event,
            "data": data
        }
        
        topic = f"{self.base_topic}/v1/instances/{self.instance_id}/devices/{device_id}/events"
        self.publish(topic, payload, retain=False)
        
        # Also publish to global event bus
        global_payload = {
            "source": f"{self.instance_id}_{device_id}",
            "event": event,
            "data": data,
            "timestamp": datetime.now().isoformat()
        }
        global_topic = f"{self.base_topic}/v1/global/events"
        self.publish(global_topic, global_payload, retain=False)
    
    def publish_error(self, device_id: str, error_code: str, message: str, 
                     severity: str = "error", retry_info: Dict = None):
        """
        Publish device error
        
        Args:
            device_id: Device identifier
            error_code: Error code
            message: Error message
            severity: Error severity (info, warning, error, critical)
            retry_info: Information about retries
        """
        payload = {
            "timestamp": datetime.now().isoformat(),
            "error_code": error_code,
            "message": message,
            "severity": severity
        }
        
        if retry_info:
            payload.update(retry_info)
        
        topic = f"{self.base_topic}/v1/instances/{self.instance_id}/devices/{device_id}/error"
        self.publish(topic, payload, retain=False)
    
    def publish_telemetry(self, device_id: str, metrics: Dict[str, Any]):
        """
        Publish device telemetry
        
        Args:
            device_id: Device identifier
            metrics: Metrics dictionary
        """
        payload = {
            "timestamp": datetime.now().isoformat(),
            "metrics": metrics
        }
        
        topic = f"{self.base_topic}/v1/instances/{self.instance_id}/devices/{device_id}/telemetry"
        self.publish(topic, payload, retain=False)
    
    def publish_discovered(self, devices: list):
        """
        Publish discovered devices
        
        Args:
            devices: List of discovered device information
        """
        payload = {
            "timestamp": datetime.now().isoformat(),
            "devices": devices
        }
        
        topic = f"{self.base_topic}/v1/instances/{self.instance_id}/discovered"
        self.publish(topic, payload, retain=False)
    
    def send_command(self, device_id: str, command: Dict[str, Any], 
                     timeout: float = 5.0, callback: Callable = None) -> str:
        """
        Send command to device with timestamp ordering
        
        Args:
            device_id: Device identifier
            command: Command dictionary
            timeout: Command timeout in seconds
            callback: Optional callback for response
            
        Returns:
            Command ID
        """
        import uuid
        cmd_id = str(uuid.uuid4())
        
        payload = {
            "id": cmd_id,
            "timestamp": datetime.now().isoformat(),
            "values": command,
            "timeout": int(timeout * 1000)  # Convert to milliseconds
        }
        
        # Store command info for response handling
        self.pending_commands[cmd_id] = CommandInfo(
            id=cmd_id,
            timestamp=datetime.now(),
            timeout=timeout,
            callback=callback
        )
        
        topic = f"{self.base_topic}/v1/instances/{self.instance_id}/devices/{device_id}/cmd"
        self.publish(topic, payload, retain=False)
        
        return cmd_id
    
    def publish(self, topic: str, payload: Any, retain: bool = False):
        """
        Publish message to MQTT
        
        Args:
            topic: MQTT topic (full path)
            payload: Message payload (will be JSON encoded if dict)
            retain: Retain message on broker
        """
        if not self.connected:
            logger.warning(f"Not connected, cannot publish to {topic}")
            return
        
        # Convert to JSON if needed
        if isinstance(payload, (dict, list)):
            payload = json.dumps(payload)
        elif not isinstance(payload, (str, bytes)):
            payload = str(payload)
        
        # Publish
        result = self.client.publish(topic, payload, qos=self.qos, retain=retain)
        
        if result.rc != mqtt.MQTT_ERR_SUCCESS:
            logger.error(f"Failed to publish to {topic}: {result.rc}")
        else:
            logger.debug(f"Published to {topic}")
    
    def wait_for_response(self, cmd_id: str, timeout: float = 5.0) -> Optional[Dict]:
        """
        Wait for command response (blocking)
        
        Args:
            cmd_id: Command ID to wait for
            timeout: Maximum wait time in seconds
            
        Returns:
            Response payload or None if timeout
        """
        response_queue = Queue()
        
        def response_callback(payload):
            response_queue.put(payload)
        
        # Update callback for this command
        if cmd_id in self.pending_commands:
            self.pending_commands[cmd_id].callback = response_callback
        
        try:
            return response_queue.get(timeout=timeout)
        except Empty:
            logger.warning(f"Timeout waiting for response to command {cmd_id}")
            return None