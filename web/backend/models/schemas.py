"""
Pydantic models for API
"""

from typing import Dict, Any, List, Optional, Literal
from pydantic import BaseModel, Field, validator
from datetime import datetime


class AuthRequest(BaseModel):
    """Authentication request"""
    key: str = Field(..., min_length=1, description="Access key")


class AuthResponse(BaseModel):
    """Authentication response"""
    success: bool
    message: str
    token: Optional[str] = None


class MQTTConfig(BaseModel):
    """MQTT configuration"""
    host: str = Field(..., description="MQTT broker host")
    port: int = Field(1883, ge=1, le=65535, description="MQTT broker port")
    username: Optional[str] = None
    password: Optional[str] = None
    base_topic: str = Field("IoT2mqtt", description="Base MQTT topic")
    client_prefix: str = Field("iot2mqtt", description="Client ID prefix")
    qos: int = Field(1, ge=0, le=2)
    retain: bool = True
    keepalive: int = Field(60, ge=10, le=3600)


class ConnectorInfo(BaseModel):
    """Connector information"""
    name: str
    display_name: str
    description: Optional[str] = None
    icon: Optional[str] = None
    instances: List[str] = []
    has_setup: bool = True
    version: Optional[str] = None


class InstanceConfig(BaseModel):
    """Instance configuration"""
    instance_id: str
    instance_type: Literal["device", "account", "service"]
    connector_type: str
    friendly_name: str
    connection: Dict[str, Any] = {}
    devices: List[Dict[str, Any]] = []
    groups: List[Dict[str, Any]] = []
    enabled: bool = True
    update_interval: int = 10
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class DeviceState(BaseModel):
    """Device state"""
    device_id: str
    instance_id: str
    online: bool
    state: Dict[str, Any]
    capabilities: Optional[Dict[str, Any]] = None
    last_update: datetime


class DeviceCommand(BaseModel):
    """Device command"""
    device_id: str
    instance_id: str
    command: Dict[str, Any]
    timeout: float = 5.0


class SetupField(BaseModel):
    """Setup form field definition"""
    type: Literal["text", "password", "number", "select", "checkbox", "ip", "url", "email", "json"]
    name: str
    label: str
    description: Optional[str] = None
    required: bool = True
    default: Optional[Any] = None
    placeholder: Optional[str] = None
    validation: Optional[Dict[str, Any]] = None
    options: Optional[List[Dict[str, Any]]] = None  # For select type
    min: Optional[float] = None  # For number type
    max: Optional[float] = None  # For number type
    step: Optional[float] = None  # For number type
    depends_on: Optional[Dict[str, Any]] = None  # Conditional fields


class SetupSchema(BaseModel):
    """Connector setup schema"""
    version: str = "1.0.0"
    fields: List[SetupField]
    groups: Optional[List[Dict[str, Any]]] = None  # Field grouping
    wizard_steps: Optional[List[Dict[str, Any]]] = None  # Multi-step wizard


class ContainerInfo(BaseModel):
    """Docker container information"""
    id: str
    name: str
    status: str
    image: str
    created: datetime
    ports: Dict[str, Any] = {}
    labels: Dict[str, str] = {}
    instance_id: Optional[str] = None


class ContainerLogs(BaseModel):
    """Container logs"""
    container_id: str
    logs: List[Dict[str, Any]]  # List of log entries with timestamp and level
    since: Optional[datetime] = None
    until: Optional[datetime] = None


class MQTTTopic(BaseModel):
    """MQTT topic information"""
    topic: str
    value: Optional[Any] = None
    timestamp: Optional[datetime] = None
    retained: bool = False
    qos: int = 0


class MQTTMessage(BaseModel):
    """MQTT message"""
    topic: str
    payload: Any
    retain: bool = False
    qos: int = 1


class SystemStatus(BaseModel):
    """System status"""
    mqtt_connected: bool
    docker_available: bool
    instances_count: int
    devices_count: int
    containers_running: int
    containers_total: int
    version: str = "1.0.0"


class WebSocketMessage(BaseModel):
    """WebSocket message format"""
    type: Literal["state", "event", "error", "command", "response", "log"]
    topic: Optional[str] = None
    device_id: Optional[str] = None
    instance_id: Optional[str] = None
    data: Any
    timestamp: datetime = Field(default_factory=datetime.now)