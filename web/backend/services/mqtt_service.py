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
        self.loop: Optional[asyncio.AbstractEventLoop] = None

    def attach_loop(self, loop: asyncio.AbstractEventLoop):
        """Attach asyncio loop used for coroutine dispatch from MQTT thread"""
        self.loop = loop

    def connect(self) -> bool:
        """Connect to MQTT broker"""
        try:
            # Create MQTT client
            client_id = f"{self.config['client_prefix']}_web"
            self.client = mqtt.Client(client_id=client_id)
            self.client.reconnect_delay_set(min_delay=1, max_delay=30)
            
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
            if self.client:
                try:
                    self.client.reconnect()
                except Exception as exc:
                    logger.error(f"Failed to reconnect to MQTT broker: {exc}")
    
    def _on_message(self, client, userdata, msg):
        """Callback for incoming messages"""
        try:
            topic = msg.topic
            
            # Check if message is empty (topic deletion)
            if len(msg.payload) == 0:
                # Remove from cache
                self.topic_cache.pop(topic, None)
                self._dispatch_to_handlers(topic, None, msg.retain)
                return
            
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
            self._dispatch_to_handlers(topic, payload, msg.retain)
                            
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

    def _dispatch_to_handlers(self, topic: str, payload: Any, retained: bool):
        """Dispatch MQTT updates to registered async handlers"""
        if not self.loop:
            return

        for handler in list(self.websocket_handlers):
            try:
                asyncio.run_coroutine_threadsafe(handler(topic, payload, retained), self.loop)
            except Exception as exc:
                logger.debug(f"Failed to dispatch MQTT message to handler: {exc}")
    
    def clear_instance_topics(self, instance_id: str):
        """
        Completely clear all MQTT topics for an instance.
        Publishes empty retained messages to remove them from broker.
        """
        if not self.connected:
            logger.warning(f"Not connected, cannot clear topics for {instance_id}")
            return False
        
        try:
            base_topic = self.config.get('base_topic', 'IoT2mqtt')
            instance_base = f"{base_topic}/v1/instances/{instance_id}"
            
            # Find all topics for this instance in cache
            topics_to_clear = []
            for topic in self.topic_cache.keys():
                if topic.startswith(instance_base):
                    topics_to_clear.append(topic)
            
            # Clear each topic by publishing empty retained message
            for topic in topics_to_clear:
                self.client.publish(topic, "", retain=True, qos=0)
                # Remove from cache
                self.topic_cache.pop(topic, None)
            
            # Also clear common subtopics that might not be in cache
            common_topics = [
                f"{instance_base}/status",
                f"{instance_base}/discovered",
                f"{instance_base}/meta/info",
                f"{instance_base}/meta/devices_list",
                f"{instance_base}/groups",
            ]
            
            for topic in common_topics:
                self.client.publish(topic, "", retain=True, qos=0)
            
            # Clear all possible device topics (use wildcard pattern)
            # We need to clear each device individually since MQTT doesn't support wildcard deletion
            devices = self.get_instance_devices(instance_id)
            for device_id in devices:
                device_base = f"{instance_base}/devices/{device_id}"
                device_topics = [
                    f"{device_base}/state",
                    f"{device_base}/availability",
                    f"{device_base}/cmd",
                    f"{device_base}/cmd/response",
                    f"{device_base}/events",
                    f"{device_base}/telemetry",
                    f"{device_base}/error"
                ]
                for topic in device_topics:
                    self.client.publish(topic, "", retain=True, qos=0)
                
                # Clear individual state properties
                for topic in self.topic_cache.keys():
                    if topic.startswith(f"{device_base}/state/"):
                        self.client.publish(topic, "", retain=True, qos=0)
            
            logger.info(f"Cleared all MQTT topics for instance {instance_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error clearing topics for {instance_id}: {e}")
            return False
    
    def clear_all_iot2mqtt_topics(self):
        """
        Clear ALL IoT2MQTT topics from the broker.
        USE WITH CAUTION - this removes all data!
        """
        if not self.connected:
            logger.warning("Not connected, cannot clear all topics")
            return False
        
        try:
            base_topic = self.config.get('base_topic', 'IoT2mqtt')
            base_prefix = f"{base_topic}/"
            
            # Find all IoT2MQTT topics in cache
            topics_to_clear = []
            for topic in self.topic_cache.keys():
                if topic.startswith(base_prefix):
                    topics_to_clear.append(topic)
            
            # Clear each topic
            cleared_count = 0
            for topic in topics_to_clear:
                self.client.publish(topic, "", retain=True, qos=0)
                self.topic_cache.pop(topic, None)
                cleared_count += 1
            
            logger.info(f"Cleared {cleared_count} IoT2MQTT topics from broker")
            return True
            
        except Exception as e:
            logger.error(f"Error clearing all topics: {e}")
            return False
