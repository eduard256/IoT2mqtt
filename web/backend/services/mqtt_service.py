"""
MQTT service with WebSocket bridge for real-time updates
"""

import asyncio
import time
import json
import logging
from typing import Dict, Any, List, Optional, Callable, Set
from datetime import datetime
import paho.mqtt.client as mqtt
from collections import defaultdict
import re

logger = logging.getLogger(__name__)


class MQTTService:
    """MQTT service with WebSocket integration"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.client = None
        self.connected = False
        self.subscriptions: Dict[str, Set[Callable]] = defaultdict(set)
        self.topic_cache: Dict[str, Any] = {}  # Cache latest values
        self.websocket_handlers: Set[Callable] = set()
        self.loop = None
        
    def connect(self) -> bool:
        """Connect to MQTT broker"""
        try:
            # Create MQTT client
            client_id = f"{self.config['client_prefix']}_web"
            self.client = mqtt.Client(client_id=client_id)
            
            # Set callbacks
            self.client.on_connect = self._on_connect
            self.client.on_disconnect = self._on_disconnect
            self.client.on_message = self._on_message
            
            # Authentication
            if self.config.get('username') and self.config.get('password'):
                self.client.username_pw_set(
                    self.config['username'],
                    self.config['password']
                )
            
            # Connect
            self.client.connect(
                self.config['host'],
                self.config['port'],
                keepalive=self.config.get('keepalive', 60)
            )
            
            # Start loop
            self.client.loop_start()
            
            # Wait for connection
            timeout = 10
            while not self.connected and timeout > 0:
                time.sleep(0.1)
                timeout -= 0.1
            
            return self.connected
            
        except Exception as e:
            logger.error(f"Failed to connect to MQTT: {e}")
            return False
    
    def disconnect(self):
        """Disconnect from MQTT broker"""
        if self.client:
            self.client.loop_stop()
            self.client.disconnect()
            self.connected = False
    
    def _on_connect(self, client, userdata, flags, rc):
        """Callback for connection"""
        if rc == 0:
            self.connected = True
            logger.info("Connected to MQTT broker")
            
            # Subscribe to all topics for explorer
            client.subscribe("#", qos=1)
            
        else:
            logger.error(f"MQTT connection failed with code {rc}")
    
    def _on_disconnect(self, client, userdata, rc):
        """Callback for disconnection"""
        self.connected = False
        if rc != 0:
            logger.warning(f"Unexpected MQTT disconnection (code {rc})")
    
    def _on_message(self, client, userdata, msg):
        """Callback for incoming messages"""
        try:
            topic = msg.topic
            
            # Parse payload
            try:
                payload = json.loads(msg.payload.decode())
            except:
                payload = msg.payload.decode()
            
            # Cache the value
            self.topic_cache[topic] = {
                "value": payload,
                "timestamp": datetime.now().isoformat(),
                "retained": msg.retain,
                "qos": msg.qos
            }
            
            # Notify WebSocket clients
            for handler in self.websocket_handlers:
                try:
                    # Call handler with update
                    asyncio.create_task(handler(topic, payload, msg.retain))
                except:
                    # If not in async context, skip
                    pass
                            
        except Exception as e:
            logger.error(f"Error processing MQTT message: {e}")
    
    def subscribe(self, pattern: str):
        """Subscribe to MQTT topic pattern"""
        if self.client and self.connected:
            self.client.subscribe(pattern)
    
    def unsubscribe(self, pattern: str):
        """Unsubscribe from MQTT topic pattern"""
        if self.client and self.connected:
            self.client.unsubscribe(pattern)
    
    def publish(self, topic: str, payload: Any, qos: int = 1, retain: bool = False):
        """Publish message to MQTT"""
        if not self.connected:
            logger.warning(f"Not connected, cannot publish to {topic}")
            return False
        
        try:
            # Convert to JSON if needed
            if isinstance(payload, (dict, list)):
                payload = json.dumps(payload)
            
            # Publish
            result = self.client.publish(topic, payload, qos=qos, retain=retain)
            return result.rc == mqtt.MQTT_ERR_SUCCESS
            
        except Exception as e:
            logger.error(f"Error publishing to {topic}: {e}")
            return False
    
    def get_topics_list(self) -> List[Dict[str, Any]]:
        """Get flat list of all topics with their values"""
        topics = []
        for topic, data in self.topic_cache.items():
            topics.append({
                "topic": topic,
                "value": data["value"],
                "timestamp": data["timestamp"],
                "retained": data.get("retained", False),
                "qos": data.get("qos", 0)
            })
        return topics
    
    def get_topic_value(self, topic: str) -> Optional[Any]:
        """Get cached value for topic"""
        if topic in self.topic_cache:
            return self.topic_cache[topic]
        return None
    
    def send_command(self, instance_id: str, device_id: str, 
                     command: Dict[str, Any]) -> str:
        """Send command to device"""
        import uuid
        
        cmd_id = str(uuid.uuid4())
        base_topic = self.config.get('base_topic', 'IoT2mqtt')
        
        payload = {
            "id": cmd_id,
            "timestamp": datetime.now().isoformat(),
            "values": command,
            "timeout": 5000
        }
        
        topic = f"{base_topic}/v1/instances/{instance_id}/devices/{device_id}/cmd"
        self.publish(topic, payload)
        
        return cmd_id
    
    def get_device_state(self, instance_id: str, device_id: str) -> Optional[Dict[str, Any]]:
        """Get device state from cache"""
        base_topic = self.config.get('base_topic', 'IoT2mqtt')
        state_topic = f"{base_topic}/v1/instances/{instance_id}/devices/{device_id}/state"
        
        if state_topic in self.topic_cache:
            return self.topic_cache[state_topic].get("value")
        return None
    
    def get_instance_devices(self, instance_id: str) -> List[str]:
        """Get list of devices for instance"""
        base_topic = self.config.get('base_topic', 'IoT2mqtt')
        pattern = f"{base_topic}/v1/instances/{instance_id}/devices/([^/]+)/state"
        
        devices = set()
        for topic in self.topic_cache:
            match = re.match(pattern, topic)
            if match:
                devices.add(match.group(1))
        
        return list(devices)
    
    def add_websocket_handler(self, handler: Callable):
        """Add WebSocket handler for updates"""
        self.websocket_handlers.add(handler)
    
    def remove_websocket_handler(self, handler: Callable):
        """Remove WebSocket handler"""
        self.websocket_handlers.discard(handler)