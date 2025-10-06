"""
Pydantic models for API
"""

from typing import Dict, Any, List, Optional, Literal, Union
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


class FlowAction(BaseModel):
    """Action rendered as a button inside a step"""
    type: Literal["goto_flow", "open_url", "reset_flow", "rerun_step", "submit", "close", "custom"]
    label: Optional[str] = None
    flow: Optional[str] = Field(default=None, description="Target flow id for goto_flow")
    url: Optional[str] = Field(default=None, description="URL to open for open_url")
    payload: Optional[Dict[str, Any]] = None
    confirm: Optional[Dict[str, Any]] = Field(default=None, description="Optional confirmation dialog settings")


class FormFieldOption(BaseModel):
    """Selectable option used by select fields"""
    value: Any
    label: str


class FormField(BaseModel):
    """Single form field definition"""
    type: Literal[
        "text",
        "password",
        "number",
        "select",
        "checkbox",
        "ip",
        "url",
        "email",
        "textarea"
    ]
    name: str
    label: Optional[str] = None
    description: Optional[str] = None
    required: bool = False
    default: Optional[Any] = None
    placeholder: Optional[str] = None
    options: Optional[List[FormFieldOption]] = None
    pattern: Optional[str] = None
    min: Optional[float] = None
    max: Optional[float] = None
    step: Optional[float] = None
    multiline: bool = False
    secret: bool = False
    conditions: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Optional map describing when the field should be shown"
    )


class FormSchema(BaseModel):
    """Schema used by form steps"""
    fields: List[FormField]


class FlowStep(BaseModel):
    """Generic flow step description"""
    id: str
    type: Literal[
        "form",
        "tool",
        "select",
        "summary",
        "discovery",
        "message",
        "instance",
        "oauth"
    ]
    title: Optional[str] = None
    description: Optional[str] = None
    schema: Optional[FormSchema] = None
    tool: Optional[str] = None
    input: Optional[Dict[str, Any]] = None
    output_key: Optional[str] = None
    items: Optional[str] = Field(default=None, description="Template describing items source for select steps")
    item_label: Optional[str] = None
    item_value: Optional[Union[str, Dict[str, Any]]] = None
    multi_select: bool = False
    sections: Optional[List[Dict[str, Any]]] = None
    actions: Optional[List[FlowAction]] = None
    auto_advance: bool = False
    optional: bool = False
    conditions: Optional[Dict[str, Any]] = None
    instance: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Configuration payload for instance steps"
    )
    oauth: Optional[Dict[str, Any]] = Field(
        default=None,
        description="OAuth provider configuration for oauth steps"
    )


class FlowDefinition(BaseModel):
    """Single setup flow"""
    id: str
    name: str
    description: Optional[str] = None
    default: bool = False
    prerequisites: Optional[List[str]] = None
    steps: List[FlowStep]


class ToolDefinition(BaseModel):
    """Definition of an executable tool used by setup flows"""
    entry: str
    timeout: int = 30
    network: Literal["none", "local", "internet"] = "none"
    secrets: Optional[List[str]] = None
    environment: Optional[Dict[str, str]] = None


class FlowSetupSchema(BaseModel):
    """Complete connector setup description"""
    version: str = "1.0.0"
    display_name: str
    description: Optional[str] = None
    author: Optional[str] = None
    branding: Optional[Dict[str, Any]] = None
    requirements: Optional[Dict[str, Any]] = None
    flows: List[FlowDefinition]
    tools: Dict[str, ToolDefinition] = {}
    discovery: Optional[Dict[str, Any]] = None
    secrets: Optional[List[str]] = None


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
