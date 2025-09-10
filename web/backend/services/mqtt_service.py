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
            
            # Subscribe to all IoT2MQTT topics
            base_topic = self.config.get('base_topic', 'IoT2mqtt')
            client.subscribe(f"{base_topic}/#", qos=1)
            
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
            
            # Notify WebSocket clients (simplified for sync context)
            message = {
                "type": "mqtt_update",
                "topic": topic,
                "payload": payload,
                "timestamp": datetime.now().isoformat(),
                "retained": msg.retain
            }
            # Store message for async processing later
            # WebSocket handlers will poll this cache
            
            # Call topic-specific handlers (sync only)
            for pattern, handlers in self.subscriptions.items():
                if self._topic_matches(pattern, topic):
                    for handler in handlers:
                        try:
                            handler(topic, payload)
                        except Exception as e:
                            logger.error(f"Error in MQTT handler: {e}")
                            
        except Exception as e:
            logger.error(f"Error processing MQTT message: {e}")
    
    def _topic_matches(self, pattern: str, topic: str) -> bool:
        """Check if topic matches pattern (with wildcards)"""
        # Convert MQTT wildcards to regex
        pattern = pattern.replace('+', '[^/]+').replace('#', '.*')
        pattern = f"^{pattern}$"
        return bool(re.match(pattern, topic))
    
    async def _notify_websocket_clients(self, message: Dict[str, Any]):
        """Notify all WebSocket clients"""
        for handler in self.websocket_handlers:
            try:
                await handler(message)
            except Exception as e:
                logger.error(f"Error notifying WebSocket client: {e}")
    
    def subscribe(self, pattern: str, handler: Callable):
        """Subscribe to MQTT topic pattern"""
        self.subscriptions[pattern].add(handler)
    
    def unsubscribe(self, pattern: str, handler: Callable):
        """Unsubscribe from MQTT topic pattern"""
        if pattern in self.subscriptions:
            self.subscriptions[pattern].discard(handler)
    
    def publish(self, topic: str, payload: Any, retain: bool = False, qos: int = 1):
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
    
    def get_topics_tree(self) -> Dict[str, Any]:
        """Get MQTT topics as tree structure"""
        tree = {}
        
        for topic in self.topic_cache:
            parts = topic.split('/')
            current = tree
            
            for i, part in enumerate(parts):
                if part not in current:
                    current[part] = {}
                
                # If last part, store value
                if i == len(parts) - 1:
                    current[part]["_value"] = self.topic_cache[topic]
                else:
                    if "_children" not in current[part]:
                        current[part]["_children"] = {}
                    current = current[part]["_children"]
        
        return tree
    
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


class MQTTExplorer:
    """MQTT topic explorer with search and filtering"""
    
    def __init__(self, mqtt_service: MQTTService):
        self.mqtt = mqtt_service
    
    def get_tree(self, filter_pattern: Optional[str] = None) -> Dict[str, Any]:
        """Get filtered topic tree"""
        all_topics = self.mqtt.topic_cache
        
        if filter_pattern:
            # Filter topics by pattern
            filtered = {}
            for topic, value in all_topics.items():
                if filter_pattern.lower() in topic.lower():
                    filtered[topic] = value
        else:
            filtered = all_topics
        
        return self._build_tree(filtered)
    
    def _build_tree(self, topics: Dict[str, Any]) -> Dict[str, Any]:
        """Build tree structure from flat topics"""
        tree = {
            "name": "MQTT",
            "children": [],
            "expanded": True
        }
        
        nodes = {}
        
        for topic, data in topics.items():
            parts = topic.split('/')
            parent = tree
            path = []
            
            for i, part in enumerate(parts):
                path.append(part)
                node_path = '/'.join(path)
                
                if node_path not in nodes:
                    node = {
                        "name": part,
                        "path": node_path,
                        "children": [],
                        "expanded": False
                    }
                    
                    # If last part, add value
                    if i == len(parts) - 1:
                        node["value"] = data["value"]
                        node["timestamp"] = data["timestamp"]
                        node["retained"] = data.get("retained", False)
                        node["qos"] = data.get("qos", 0)
                    
                    nodes[node_path] = node
                    parent["children"].append(node)
                    parent = node
                else:
                    parent = nodes[node_path]
        
        return tree
    
    def search_topics(self, query: str) -> List[Dict[str, Any]]:
        """Search topics by query"""
        results = []
        query_lower = query.lower()
        
        for topic, data in self.mqtt.topic_cache.items():
            # Search in topic name
            if query_lower in topic.lower():
                results.append({
                    "topic": topic,
                    "value": data["value"],
                    "timestamp": data["timestamp"],
                    "match": "topic"
                })
            # Search in value (if string)
            elif isinstance(data["value"], str) and query_lower in data["value"].lower():
                results.append({
                    "topic": topic,
                    "value": data["value"],
                    "timestamp": data["timestamp"],
                    "match": "value"
                })
        
        return results