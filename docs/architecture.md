# IoT2MQTT v2.0 Architecture

**Comprehensive System Architecture Documentation**

---

## Executive Summary

IoT2MQTT is a containerized IoT integration platform that enables seamless connection of diverse IoT devices and protocols to a unified MQTT message bus. The system uses a microservices architecture built entirely on Docker containers, eliminating host system dependencies and enabling consistent deployment across any environment.

### Core Principles

**Container-First Design**: Every component runs in an isolated Docker container. The main web application orchestrates connector containers through Docker-in-Docker architecture, with each connector instance receiving its own dedicated container.

**MQTT as Integration Protocol**: All device communication flows through MQTT topics following a standardized contract. This creates a language-agnostic integration layer where connectors can be implemented in any language while maintaining consistent external interfaces.

**Declarative Configuration**: Setup flows, connector schemas, and instance configurations are declared in JSON files. The web interface dynamically renders these declarations without requiring custom UI code for each connector type.

**Extensibility Through Connectors**: The platform's extensibility mechanism is the connector system. Connectors can range from simple single-process Python scripts to complex multi-process applications combining multiple languages and services within a single container. This document focuses extensively on connector architecture as it represents the primary extension point for the platform.

---

## System-Wide Architecture

### Component Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                         Host System                              │
│                                                                   │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │                    Docker Engine                            │ │
│  │                                                              │ │
│  │  ┌──────────────────────────────────────────────────────┐  │ │
│  │  │            iot2mqtt_web (Orchestrator)               │  │ │
│  │  │                                                        │  │ │
│  │  │  ┌─────────────────┐    ┌──────────────────┐        │  │ │
│  │  │  │  React Frontend │    │  FastAPI Backend │        │  │ │
│  │  │  │  (SPA)          │    │  - ConfigService │        │  │ │
│  │  │  │  - PWA          │◄───┤  - DockerService │        │  │ │
│  │  │  │  - i18n         │    │  - MQTTService   │        │  │ │
│  │  │  └─────────────────┘    └──────────────────┘        │  │ │
│  │  │                                   │                   │  │ │
│  │  │                                   ▼                   │  │ │
│  │  │                          /var/run/docker.sock        │  │ │
│  │  │                          (mounted from host)         │  │ │
│  │  └────────────────────────────────────────────────────┘  │ │
│  │                                                              │ │
│  │  ┌──────────────────────────────────────────────────────┐  │ │
│  │  │          iot2mqtt_test_runner (Executor)             │  │ │
│  │  │                                                        │  │ │
│  │  │  - Executes action scripts during setup               │  │ │
│  │  │  - Isolated subprocess execution                      │  │ │
│  │  │  - Network access for device discovery                │  │ │
│  │  │  - Returns JSON results to web backend                │  │ │
│  │  └──────────────────────────────────────────────────────┘  │ │
│  │                                                              │ │
│  │  ┌──────────────────────────────────────────────────────┐  │ │
│  │  │     Connector Instances (Created Dynamically)         │  │ │
│  │  │                                                        │  │ │
│  │  │  iot2mqtt_yeelight_instance1                          │  │ │
│  │  │  iot2mqtt_zigbee_instance2                            │  │ │
│  │  │  iot2mqtt_cameras_instance3                           │  │ │
│  │  │  ...                                                   │  │ │
│  │  │                                                        │  │ │
│  │  │  Each container:                                       │  │ │
│  │  │  - Runs connector code (any language)                 │  │ │
│  │  │  - Manages device communication                       │  │ │
│  │  │  - Publishes to MQTT                                  │  │ │
│  │  │  - Follows standardized contract                      │  │ │
│  │  └──────────────────────────────────────────────────────┘  │ │
│  │                                                              │ │
│  │                              │                               │ │
│  │                              │ MQTT Protocol                 │ │
│  │                              ▼                               │ │
│  │  ┌──────────────────────────────────────────────────────┐  │ │
│  │  │              MQTT Broker (External)                   │  │ │
│  │  │              - Mosquitto / Others                     │  │ │
│  │  └──────────────────────────────────────────────────────┘  │ │
│  └──────────────────────────────────────────────────────────┘  │
└───────────────────────────────────────────────────────────────┘
```

### Component Responsibilities

**Web Backend (`iot2mqtt_web`)**: The orchestrator container manages the entire system lifecycle. It provides:

- REST API for configuration and management
- Dynamic rendering of setup flows from `setup.json` declarations
- Container lifecycle management through `DockerService`
- Configuration persistence through `ConfigService`
- MQTT client for platform-level communication
- Static file serving for the React frontend

The web container has privileged access to the Docker socket (`/var/run/docker.sock`) enabling it to create, start, stop, and monitor connector containers. This Docker-in-Docker pattern centralizes orchestration while maintaining container isolation.

**Test Runner (`iot2mqtt_test_runner`)**: An isolated execution environment for setup-time scripts. During connector onboarding:

- Action scripts from `connectors/<name>/actions/` are executed as subprocesses
- Scripts receive JSON input via stdin and return JSON results via stdout
- Network access enables device discovery and validation
- Isolation prevents setup scripts from affecting runtime system state

The test runner uses FastAPI to expose HTTP endpoints that the web backend calls during setup flows. Results are returned synchronously for immediate feedback to users.

**Connector Instances**: Dynamically created containers, one per configured instance. Each connector:

- Loads configuration from mounted JSON file in `/app/instances/`
- Connects to MQTT broker using credentials from `.env`
- Implements device-specific communication protocols
- Publishes device state following the MQTT contract
- Subscribes to command topics to control devices
- Manages its internal architecture (single or multi-process)

**MQTT Broker**: External message bus (typically Mosquitto) that all connectors and the web backend communicate through. Not managed by IoT2MQTT but connected to via configuration.

### Component Interaction Flows

**Instance Creation Flow**:
1. User initiates setup through web frontend
2. Frontend requests setup schema from backend (`GET /api/integrations/<name>/setup`)
3. Backend reads `connectors/<name>/setup.json` and returns flow definition
4. Frontend renders forms and tool steps dynamically
5. When tool steps execute, backend calls test-runner (`POST /actions/<name>/execute`)
6. Test-runner executes action script and returns results
7. After flow completion, backend creates instance JSON in `instances/<name>/<id>.json`
8. `DockerService` builds connector image if needed
9. `DockerService` creates container with proper mounts and environment variables
10. Container starts, loads config, connects to MQTT, begins operation

**Runtime Operation Flow**:
1. Connector container polls or subscribes to device events
2. State changes are published to MQTT topics following contract
3. Web backend subscribes to relevant topics for dashboard display
4. User sends command through web interface
5. Backend publishes command to appropriate MQTT topic
6. Connector receives command, executes device action
7. Updated state is published to MQTT
8. Frontend receives update via MQTT subscription or polling

**Update/Restart Flow**:
1. User modifies configuration through web interface
2. Backend updates instance JSON file
3. `DockerService.restart_container()` restarts the connector
4. Connector reloads configuration on startup
5. New configuration takes effect without data loss

---

## Connector Architecture

Connectors are the primary extension mechanism for IoT2MQTT. The v2.0 architecture enables connectors of arbitrary complexity while maintaining a consistent external contract. This section thoroughly documents the three complexity levels and architectural patterns.

### The Connector Contract

All connectors, regardless of internal architecture, must satisfy a standardized contract enabling consistent integration with the platform. This contract is the only mandatory aspect of connector development—everything else is implementation choice.

**Environment Variables** (injected by `docker_service.py`):

```bash
INSTANCE_NAME=<instance_id>          # Unique instance identifier
CONNECTOR_TYPE=<connector_name>      # Type of connector (e.g., "yeelight")
MODE=production                      # Operating mode (production/development)
PYTHONUNBUFFERED=1                   # Python output buffering control

# From .env (mounted read-only):
MQTT_HOST=<broker_host>              # MQTT broker address
MQTT_PORT=<broker_port>              # MQTT broker port
MQTT_USERNAME=<username>             # MQTT authentication
MQTT_PASSWORD=<password>             # MQTT authentication
MQTT_BASE_TOPIC=<base_topic>         # Root topic (e.g., "IoT2mqtt")
MQTT_CLIENT_PREFIX=<prefix>          # Client ID prefix
MQTT_QOS=<qos_level>                 # Quality of Service level (0-2)
MQTT_RETAIN=<true|false>             # Message retention flag
MQTT_KEEPALIVE=<seconds>             # Connection keepalive interval
LOG_LEVEL=<level>                    # Logging verbosity
TZ=<timezone>                        # Timezone setting
```

**Configuration File**:

Path within container: `/app/instances/<instance_id>.json`

The connector must read this file to obtain its configuration. The structure is connector-specific but typically includes:

```json
{
  "instance_id": "yeelight_ly1skw",
  "instance_type": "device",
  "connector_type": "yeelight",
  "friendly_name": "Living Room Light",
  "devices": [
    {
      "device_id": "light1",
      "ip": "192.168.1.100",
      "enabled": true
    }
  ],
  "enabled": true,
  "update_interval": 10,
  "created_at": "2025-10-12T20:25:11.640083",
  "updated_at": "2025-10-12T20:25:11.640067"
}
```

**MQTT Topics Contract** (complete specification in `docs/CONNECTOR_SPEC.md`):

*Required Subscriptions* (connector must listen to):

```
{BASE_TOPIC}/v1/instances/{instance_id}/devices/{device_id}/cmd
{BASE_TOPIC}/v1/instances/{instance_id}/devices/{device_id}/get
{BASE_TOPIC}/v1/instances/{instance_id}/groups/{group_id}/cmd
{BASE_TOPIC}/v1/instances/{instance_id}/meta/request/+
```

*Required Publications* (connector must publish to):

Status topic with Last Will and Testament:
```
Topic: {BASE_TOPIC}/v1/instances/{instance_id}/status
Payload: "online" | "offline"
QoS: 1
Retain: true
```

Device state updates:
```
Topic: {BASE_TOPIC}/v1/instances/{instance_id}/devices/{device_id}/state
Payload: {
  "timestamp": "2025-10-13T10:30:00.000Z",
  "device_id": "light1",
  "state": {
    "power": true,
    "brightness": 75,
    "color_temp": 4000,
    "online": true
  }
}
QoS: 1
Retain: true (recommended)
```

Device errors:
```
Topic: {BASE_TOPIC}/v1/instances/{instance_id}/devices/{device_id}/error
Payload: {
  "timestamp": "2025-10-13T10:30:00.000Z",
  "error_code": "CONNECTION_FAILED",
  "message": "Device unreachable",
  "severity": "error"
}
QoS: 1
Retain: false
```

Device events:
```
Topic: {BASE_TOPIC}/v1/instances/{instance_id}/devices/{device_id}/events
Payload: {
  "timestamp": "2025-10-13T10:30:00.000Z",
  "event": "motion_detected",
  "data": {
    "confidence": 0.95,
    "zone": "entrance"
  }
}
QoS: 1
Retain: false
```

**Volume Mounts** (provided by `docker_service.py`):

```
Host path                          → Container path              Mode
──────────────────────────────────────────────────────────────────────
<host_base>/shared/                → /app/shared/                ro
<host_base>/instances/<connector>/ → /app/instances/             ro
<host_base>/.env                   → /app/.env                   ro
```

Note the path transformation: on the host, instances are organized by connector type (`instances/yeelight/instance1.json`), but inside the container they appear flat (`/app/instances/instance1.json`) because only the relevant connector directory is mounted.

### Connector Complexity Levels

IoT2MQTT v2.0 supports three architectural complexity levels, each appropriate for different use cases. Developers choose the level that matches their integration requirements.

#### Level 1: Simple Single-Process

**Architecture**: A single Python process using `BaseConnector` helper class for boilerplate reduction.

**Internal Structure**:
```
Container Process Tree:
└── python main.py
    └── connector.Connector (inherits BaseConnector)
        ├── MQTT client (from mqtt_client.py)
        ├── Polling loop
        └── Device communication
```

**When Appropriate**:
- Polling-based device protocols (HTTP APIs, simple TCP)
- Few devices per instance (1-10)
- Straightforward state mapping
- No real-time event streams
- Python is sufficient for protocol implementation

**Languages/Tools**: Python 3.11+, optional libraries for specific protocols

**Example**: Yeelight connector managing smart bulbs via their proprietary WiFi protocol. The connector polls bulb state every 10 seconds, publishes to MQTT, and sends commands when received.

**Template Reference**: `connectors/_template/` provides starting point with:
- Basic `connector.py` inheriting `BaseConnector`
- `main.py` entry point
- `Dockerfile` for Python container
- `setup.json` for one-step setup flow

**Advantages**:
- Minimal code required (BaseConnector handles MQTT boilerplate)
- Easy debugging (single process)
- Simple dependency management
- Quick development cycle

**Limitations**:
- Python-only implementation
- Polling-based (not event-driven)
- Limited scalability for many devices
- Single language constraint may require workarounds for protocol libraries

#### Level 2: Multi-Process Single-Language

**Architecture**: Multiple processes within one container, coordinated by process manager. All processes typically use the same base language but handle different responsibilities.

**Internal Structure**:
```
Container Process Tree:
└── supervisord
    ├── mqtt_bridge.py (coordinator)
    ├── device_poller.py (state collection)
    ├── event_listener.py (real-time events)
    └── command_processor.py (action execution)
```

**When Appropriate**:
- Event-driven protocols alongside polling
- Clear separation of concerns (state/events/commands)
- Concurrent operations needed (multiple simultaneous requests)
- CPU-bound operations (parallel processing)
- Still within single language ecosystem

**Languages/Tools**: Python (or other single language), supervisord for process management

**Process Communication**: Localhost HTTP/TCP, shared files, or queue systems

**Example**: An RTSP camera connector where:
- Stream monitor process watches video feeds continuously
- Motion detection process analyzes frames
- Object recognition process runs ML models
- MQTT bridge coordinates and publishes results

All processes communicate via localhost HTTP endpoints, with the MQTT bridge aggregating their outputs and handling commands.

**Advantages**:
- Event-driven capabilities
- Parallel processing
- Fault isolation (process crashes don't affect others)
- Still relatively simple deployment (one container)

**Limitations**:
- Single language constraint remains
- Inter-process communication overhead
- More complex debugging
- Process coordination complexity

#### Level 3: Multi-Process Multi-Language

**Architecture**: Multiple processes in different languages coordinated within single container, managed by supervisord. This is the v2.0 flagship capability enabling unlimited connector complexity.

**Internal Structure**:
```
Container Process Tree:
└── supervisord
    ├── mqtt_bridge.py (Python - MQTT coordinator)
    ├── go2rtc (Go binary - RTSP stream manager)
    ├── motion-detector (Node.js - event processing)
    ├── object-recognition (Python + TensorFlow - ML)
    └── storage-manager (Rust - high-performance I/O)
```

**When Appropriate**:
- Leveraging existing tools (go2rtc, ffmpeg, zigbee2mqtt)
- Performance-critical components (Rust/Go)
- Rich ecosystem libraries (Node.js npm, Python ML)
- Wrapping third-party services
- Complex multi-stage pipelines

**Languages/Tools**: Any combination of Python, Node.js, Go, Rust, C/C++, compiled binaries, external tools

**Process Communication**: Localhost TCP/HTTP/WebSocket, Unix sockets, shared memory, files

**Example**: Advanced camera system connector:
- `go2rtc` (Go): Manages RTSP streams, transcoding, snapshots
- `motion-detector` (Node.js): Real-time motion detection on video frames
- `object-recognition` (Python): TensorFlow-based object classification
- `mqtt_bridge.py` (Python): Coordinates everything, implements MQTT contract

The MQTT bridge polls services via HTTP, aggregates results, and publishes unified device state. Commands from MQTT are routed to appropriate service endpoints.

**Template Reference**: `connectors/_template-multiprocess/` provides comprehensive starting point:
- `Dockerfile` with multi-language runtime
- `supervisord.conf` defining all processes
- `mqtt_bridge.py` coordinator implementing contract
- `services/` directory with example service
- Complete documentation of patterns

**Example Reference**: `connectors/_example-multiprocess/` demonstrates working implementation:
- Realistic sensor hub scenario
- Multiple protocols (HTTP, WebSocket, TCP)
- State aggregation from multiple sources
- Command distribution to appropriate services
- Production-ready patterns

**Advantages**:
- Unlimited complexity capability
- Best tool for each job (language/library choice)
- Can wrap existing projects (zigbee2mqtt, Home Assistant)
- Performance optimization opportunities
- Extensive ecosystem access

**Challenges**:
- Increased container build time
- More complex debugging (multiple languages)
- Process coordination complexity
- Larger container images
- More sophisticated error handling needed

**Key Pattern - The MQTT Bridge**:

In multi-process connectors, the MQTT bridge process is mandatory and serves as the single point implementing the MQTT contract. Other processes focus on device communication while the bridge handles:

```python
# mqtt_bridge.py (simplified example)

import os
import requests
from mqtt_client import MQTTClient

# Get configuration
INSTANCE_NAME = os.getenv('INSTANCE_NAME')
mqtt = MQTTClient(instance_id=INSTANCE_NAME)

# URLs of internal services (localhost communication)
SENSOR_API = "http://localhost:5000"
CAMERA_API = "http://localhost:8080"

# Connect to MQTT
mqtt.connect()
mqtt.publish(f"IoT2mqtt/v1/instances/{INSTANCE_NAME}/status", "online", retain=True)

# Subscribe to commands
def on_command(topic, payload):
    device_id = extract_device_id(topic)

    if "snapshot" in payload:
        # Route to camera service
        result = requests.post(f"{CAMERA_API}/snapshot")
        mqtt.publish_event(device_id, "snapshot_taken", result.json())
    elif "sensor_read" in payload:
        # Route to sensor service
        result = requests.get(f"{SENSOR_API}/read")
        mqtt.publish_state(device_id, result.json())

mqtt.subscribe("devices/+/cmd", on_command)

# Poll services and publish state
while True:
    # Aggregate state from all services
    sensor_state = requests.get(f"{SENSOR_API}/state").json()
    camera_state = requests.get(f"{CAMERA_API}/state").json()

    combined_state = {**sensor_state, **camera_state}
    mqtt.publish_state("hub", combined_state)

    time.sleep(5)
```

This pattern decouples MQTT contract compliance from device communication, allowing each component to focus on its responsibility.

### BaseConnector: Optional Helper Library

`shared/base_connector.py` provides convenient base class for Python connectors, particularly suited for Level 1 implementations. Understanding when to use it versus implementing the contract directly is important.

**What BaseConnector Provides**:

- MQTT connection management with auto-reconnect
- Configuration loading from `/app/instances/<id>.json`
- Automatic topic subscription setup
- Polling loop with error handling
- Command parsing and routing
- State publication helpers
- Graceful shutdown handling
- Secrets loading from Docker secrets

**BaseConnector Architecture**:

```python
class BaseConnector(ABC):
    def __init__(self, config_path: str = None, instance_name: str = None):
        # Load configuration
        # Initialize MQTT client
        # Setup logging

    def start(self):
        # Connect to MQTT
        # Subscribe to command topics
        # Initialize device connections
        # Start polling loop

    def _main_loop(self):
        # Periodically call get_device_state()
        # Publish results to MQTT
        # Handle errors with retry logic

    @abstractmethod
    def initialize_connection(self):
        # Connector implements device-specific setup

    @abstractmethod
    def get_device_state(self, device_id, device_config):
        # Connector implements state retrieval

    @abstractmethod
    def set_device_state(self, device_id, device_config, state):
        # Connector implements command execution
```

**When to Use BaseConnector**:

Use BaseConnector when:
- Building a simple polling-based connector
- Using Python as primary language
- Wanting to minimize boilerplate code
- Focusing on device protocol implementation
- Learning connector development

Do not use BaseConnector when:
- Implementing event-driven architecture
- Using languages other than Python
- Building multi-process connector
- Needing custom MQTT patterns
- Wrapping existing projects

**Direct Contract Implementation**:

For multi-process or non-Python connectors, implement the MQTT contract directly:

```python
# Example: Direct implementation without BaseConnector

import paho.mqtt.client as mqtt
import os
import json

INSTANCE_NAME = os.getenv('INSTANCE_NAME')
MQTT_HOST = os.getenv('MQTT_HOST')
BASE_TOPIC = os.getenv('MQTT_BASE_TOPIC')

# Create MQTT client
client = mqtt.Client(client_id=f"iot2mqtt_{INSTANCE_NAME}")

# Setup Last Will and Testament
status_topic = f"{BASE_TOPIC}/v1/instances/{INSTANCE_NAME}/status"
client.will_set(status_topic, "offline", qos=1, retain=True)

# Connect and set online
client.connect(MQTT_HOST, 1883)
client.publish(status_topic, "online", qos=1, retain=True)

# Subscribe to commands
def on_message(client, userdata, msg):
    if "/cmd" in msg.topic:
        payload = json.loads(msg.payload)
        # Handle command...

client.on_message = on_message
client.subscribe(f"{BASE_TOPIC}/v1/instances/{INSTANCE_NAME}/devices/+/cmd")

# Start processing
client.loop_forever()
```

This approach provides full control over MQTT behavior and enables non-Python implementations.

### Process Management with Supervisord

Multi-process connectors (Levels 2 and 3) use supervisord to manage process lifecycle within the container. This section explains the configuration and patterns.

**Why Supervisord Over Alternatives**:

Alternatives considered:
- **Bash scripts with background processes**: Hard to manage, poor error handling, difficult graceful shutdown
- **Docker Compose multi-container**: Violates "one instance = one container" principle, increases complexity
- **Python subprocess management**: Requires custom code, less robust than proven tool
- **systemd in container**: Overcomplicated, designed for system-level not container-level

Supervisord chosen because:
- Proven reliability in container environments
- Automatic process restart on failure
- Proper signal handling for graceful shutdown
- Per-process logging with output capture
- Simple configuration file format
- Lightweight and well-maintained

**Supervisord Configuration Pattern**:

```ini
# supervisord.conf

[supervisord]
nodaemon=true                          # Run in foreground (required for containers)
user=root                              # Container runs as root typically
logfile=/var/log/supervisor/supervisord.log
pidfile=/var/run/supervisord.pid

# Process 1: Go service
[program:go2rtc]
command=/usr/local/bin/go2rtc -c /app/config/go2rtc.yaml
autostart=true                         # Start automatically
autorestart=true                       # Restart on crash
stdout_logfile=/dev/stdout             # Stream to container logs
stdout_logfile_maxbytes=0              # No rotation (container handles this)
stderr_logfile=/dev/stderr
stderr_logfile_maxbytes=0

# Process 2: Node.js service
[program:motion-detector]
command=node /app/services/motion-detector/index.js
autostart=true
autorestart=true
stdout_logfile=/dev/stdout
stdout_logfile_maxbytes=0
stderr_logfile=/dev/stderr
stderr_logfile_maxbytes=0
environment=GO2RTC_URL="http://localhost:1984"  # Inter-process communication

# Process 3: Python ML service
[program:object-recognition]
command=python /app/services/object-recognition/detector.py
autostart=true
autorestart=true
stdout_logfile=/dev/stdout
stdout_logfile_maxbytes=0
stderr_logfile=/dev/stderr
stderr_logfile_maxbytes=0
environment=GO2RTC_URL="http://localhost:1984",MODEL_PATH="/app/models"

# Process 4: MQTT Bridge (highest priority)
[program:mqtt-bridge]
command=python /app/mqtt_bridge.py
autostart=true
autorestart=true
stdout_logfile=/dev/stdout
stdout_logfile_maxbytes=0
stderr_logfile=/dev/stderr
stderr_logfile_maxbytes=0
priority=999                           # Start last (after other services ready)
startsecs=3                            # Wait 3 seconds before considering started
```

**Process Startup Order**:

Priority field (lower numbers start first) enables dependency management:
1. Core services (go2rtc, databases) - priority 10-100
2. Processing services (motion detection, ML) - priority 100-500
3. MQTT bridge (depends on all others) - priority 999

The `startsecs` parameter prevents supervisor from considering a process running if it crashes immediately, enabling proper restart behavior.

**Container Lifecycle**:

```
Container Start
    └── supervisord starts
        ├── Reads supervisord.conf
        ├── Starts programs in priority order
        ├── Monitors process health
        └── Restarts crashed processes

Container Stop (SIGTERM received)
    └── supervisord begins shutdown
        ├── Sends SIGTERM to all processes
        ├── Waits up to stopwaitsecs (default 10)
        ├── Sends SIGKILL if processes don't exit
        └── supervisord exits (container stops)
```

**Logging Strategy**:

Supervisord forwards all process stdout/stderr to container stdout/stderr by configuring:
```ini
stdout_logfile=/dev/stdout
stdout_logfile_maxbytes=0
```

This enables Docker's native logging system to capture all process output. Container logs viewed via `docker logs <container>` show all processes with prefixes:
```
[go2rtc] Starting RTSP server on port 8554...
[motion-detector] Motion detection service initialized
[object-recognition] Loading TensorFlow model...
[mqtt-bridge] Connected to MQTT broker
```

### Localhost Communication Patterns

Multi-process connectors require inter-process communication. Since all processes run in the same container, localhost networking provides efficient, low-latency communication.

**HTTP/REST Pattern** (most common):

Service processes expose HTTP APIs on localhost ports. The MQTT bridge and other coordinators use HTTP requests:

```
Service Process:
  from flask import Flask
  app = Flask(__name__)

  @app.route('/api/state')
  def get_state():
      return {'temperature': 22.5, 'humidity': 45}

  app.run(host='localhost', port=5000)

Coordinator Process:
  import requests

  state = requests.get('http://localhost:5000/api/state').json()
  mqtt.publish_state('sensor1', state)
```

**WebSocket Pattern** (for real-time events):

When services need to push events rather than be polled:

```
Service Process:
  # WebSocket server pushing events
  async def event_generator():
      while True:
          event = await get_next_event()
          await websocket.send(json.dumps(event))

Coordinator Process:
  # WebSocket client receiving events
  async with websockets.connect('ws://localhost:8080/events') as ws:
      async for message in ws:
          event = json.loads(message)
          mqtt.publish_event('device1', event['type'], event['data'])
```

**TCP Socket Pattern** (for binary protocols):

When dealing with binary data or custom protocols:

```
Service Process:
  import socket
  sock = socket.socket()
  sock.bind(('localhost', 9000))
  sock.listen()
  # Accept connections and send binary data

Coordinator Process:
  import socket
  sock = socket.socket()
  sock.connect(('localhost', 9000))
  data = sock.recv(4096)
  # Parse binary data
```

**Shared File Pattern** (for large data or batch processing):

When passing large datasets between processes:

```
Service Process:
  # Write results to shared file
  with open('/tmp/detection_results.json', 'w') as f:
      json.dump(results, f)

Coordinator Process:
  # Read when file updated (watch with inotify)
  with open('/tmp/detection_results.json') as f:
      results = json.load(f)
```

**Queue Pattern** (for work distribution):

Using Redis or other in-memory queue when present:

```
Producer Process:
  redis_client.lpush('work_queue', json.dumps(task))

Worker Process:
  while True:
      task_json = redis_client.brpop('work_queue', timeout=1)
      if task_json:
          task = json.loads(task_json)
          process_task(task)
```

**Best Practices**:

- Use HTTP/REST for most coordination (widely understood, simple debugging)
- Reserve WebSocket for true real-time event streams
- Implement health check endpoints in each service
- Add timeouts to all inter-process calls
- Log communication errors distinctly from business logic errors
- Consider service startup order (core services before consumers)

---

## Connector Lifecycle

Understanding connector lifecycle phases is essential for building reliable connectors and debugging issues. This section details each phase from creation through shutdown.

### Phase 1: Setup (Action Script Execution)

**Trigger**: User initiates connector onboarding through web interface

**Environment**: Scripts execute in `iot2mqtt_test_runner` container, not the runtime connector container

**Flow**:

1. **User selects connector**: Frontend displays available connectors from `connectors/` directory
2. **Setup schema loading**: Backend reads `connectors/<name>/setup.json` and returns to frontend
3. **Dynamic rendering**: Frontend renders forms, selection steps, and tool triggers
4. **Form data collection**: User inputs required information (IPs, credentials, etc.)
5. **Tool execution**: When flow reaches `tool` step:
   - Frontend sends request to backend (`POST /api/actions/<connector>/execute`)
   - Backend forwards to test-runner (`POST http://test-runner:8001/actions/<connector>/execute`)
   - Test-runner locates script at `connectors/<connector>/actions/<tool>.py`
   - Script executes as subprocess with JSON input via stdin
   - Script returns JSON result via stdout: `{"ok": true/false, "result": {...}, "error": {...}}`
   - Result flows back to frontend for validation/display
6. **Flow completion**: After all steps complete, backend receives final instance configuration

**Action Script Contract**:

```python
#!/usr/bin/env python3
# Example: actions/validate.py

import json
import sys

def load_input():
    """Read JSON from stdin"""
    payload = json.load(sys.stdin)
    return payload.get('input', {})

def main():
    try:
        input_data = load_input()
        host = input_data['host']
        port = input_data['port']

        # Validate connectivity
        result = test_connection(host, port)

        # Return success
        print(json.dumps({
            "ok": True,
            "result": {
                "reachable": True,
                "host": host,
                "port": port
            }
        }))
    except Exception as e:
        # Return error
        print(json.dumps({
            "ok": False,
            "error": {
                "code": "validation_failed",
                "message": str(e),
                "retriable": True
            }
        }))

if __name__ == '__main__':
    main()
```

**What Can Go Wrong**:

- Script timeout (configurable in `setup.json` tool definition)
- Network unreachable (discovery on wrong subnet)
- Invalid credentials (authentication failure)
- Missing dependencies (script imports unavailable library)
- Invalid JSON output (malformed response)

**Error Handling**: Test-runner catches exceptions, timeouts, and invalid JSON, returning structured error response to web backend for display to user.

### Phase 2: Deployment (Container Creation)

**Trigger**: Setup flow completion with valid configuration

**Executor**: Web backend `DockerService` class

**Flow**:

1. **Configuration persistence**:
   - Backend calls `ConfigService.save_instance_config(connector_name, instance_id, config)`
   - Instance JSON written to `instances/<connector>/<instance_id>.json`
   - Sensitive fields extracted by `SecretsManager` and encrypted separately

2. **Image availability check**:
   - `DockerService.create_container()` checks if image `iot2mqtt_<connector>:latest` exists
   - If missing, calls `DockerService.build_image(connector_name)`
   - Build reads `connectors/<connector>/Dockerfile` and builds image
   - Build logs streamed to web backend for monitoring

3. **Container configuration preparation**:
   ```python
   container_config = {
       "image": f"iot2mqtt_{connector_name}:latest",
       "name": f"iot2mqtt_{connector_name}_{instance_id}",
       "detach": True,
       "restart_policy": {"Name": "unless-stopped"},
       "environment": [
           f"INSTANCE_NAME={instance_id}",
           f"CONNECTOR_TYPE={connector_name}",
           "MODE=production",
           "PYTHONUNBUFFERED=1"
       ],
       "volumes": {
           "/host/path/shared": {"bind": "/app/shared", "mode": "ro"},
           "/host/path/instances/connector": {"bind": "/app/instances", "mode": "ro"},
           "/host/path/.env": {"bind": "/app/.env", "mode": "ro"}
       },
       "network_mode": "host",  # Enables device discovery
       "labels": {
           "iot2mqtt.type": "connector",
           "iot2mqtt.connector": connector_name,
           "iot2mqtt.instance": instance_id
       }
   }
   ```

4. **Container creation**:
   - `docker_client.containers.run(**container_config)` creates and starts container
   - Container ID returned to web backend
   - Container immediately begins executing (proceeds to Phase 3)

**Volume Mount Path Transformation**:

Critical understanding: paths differ between host and container perspectives.

On host filesystem:
```
/opt/iot2mqtt/instances/yeelight/yeelight_ly1skw.json
/opt/iot2mqtt/instances/yeelight/yeelight_abc123.json
```

Docker mount specification (in `docker_service.py`):
```python
volumes = {
    "/opt/iot2mqtt/instances/yeelight": {
        "bind": "/app/instances",
        "mode": "ro"
    }
}
```

Inside container:
```
/app/instances/yeelight_ly1skw.json
/app/instances/yeelight_abc123.json
```

The connector directory is mounted as the container's `/app/instances/`, so connectors see a flat structure. `BaseConnector` and direct implementations must load `/app/instances/{INSTANCE_NAME}.json`.

**What Can Go Wrong**:

- Image build failure (Dockerfile errors, missing dependencies)
- Insufficient disk space (build cache or image storage)
- Port conflicts (if using exposed ports)
- Mount path errors (incorrect host path resolution)
- Docker daemon unavailable (socket connection failure)

**Error Handling**: `DockerService` catches Docker API exceptions and returns `None` for container ID, with errors logged. Web backend returns appropriate HTTP status to frontend with error details.

### Phase 3: Initialization (Connector Startup)

**Trigger**: Container start

**Executor**: Connector code within newly created container

**Flow**:

1. **Container entry point execution**:
   - Docker runs `CMD` from Dockerfile (typically `python main.py` or `supervisord`)
   - Environment variables injected by Docker are available
   - Volume mounts are accessible

2. **Configuration loading**:
   ```python
   # BaseConnector example
   instance_name = os.getenv('INSTANCE_NAME')
   config_path = f"/app/instances/{instance_name}.json"
   with open(config_path) as f:
       config = json.load(f)
   ```

3. **Secrets loading** (if using Docker secrets):
   ```python
   secret_path = f"/run/secrets/{instance_name}_creds"
   if os.path.exists(secret_path):
       with open(secret_path) as f:
           for line in f:
               key, value = line.strip().split('=', 1)
               config['credentials'][key] = value
   ```

4. **MQTT connection establishment**:
   ```python
   # Load MQTT config from .env (mounted at /app/.env)
   from dotenv import load_dotenv
   load_dotenv('/app/.env')

   mqtt_host = os.getenv('MQTT_HOST')
   mqtt_port = int(os.getenv('MQTT_PORT'))

   # Create client with LWT
   client = mqtt.Client(client_id=f"iot2mqtt_{instance_name}")
   status_topic = f"{BASE_TOPIC}/v1/instances/{instance_name}/status"
   client.will_set(status_topic, "offline", qos=1, retain=True)

   # Connect
   client.connect(mqtt_host, mqtt_port, keepalive=60)

   # Publish online status
   client.publish(status_topic, "online", qos=1, retain=True)
   ```

5. **Topic subscriptions**:
   ```python
   # Subscribe to command topics
   client.subscribe(f"{BASE_TOPIC}/v1/instances/{instance_name}/devices/+/cmd")
   client.subscribe(f"{BASE_TOPIC}/v1/instances/{instance_name}/devices/+/get")
   client.subscribe(f"{BASE_TOPIC}/v1/instances/{instance_name}/meta/request/+")
   ```

6. **Device connection initialization**:
   - Connector-specific: may open TCP sockets, HTTP sessions, serial ports
   - Example: Yeelight connector creates `Bulb` objects for each configured IP
   - Connection failures logged but don't necessarily prevent startup

7. **Multi-process startup** (Level 3 connectors):
   - Supervisord starts all configured programs
   - Core services start first (by priority)
   - MQTT bridge starts last after dependencies ready
   - Health checks ensure services are functional

**BaseConnector Initialization Sequence**:

```python
connector = Connector(instance_name=instance_name)  # Loads config, creates MQTT client
connector.start()  # Detailed sequence:
    # 1. mqtt.connect() - establish MQTT connection
    # 2. _setup_subscriptions() - subscribe to command topics
    # 3. initialize_connection() - connector implements device setup
    # 4. Start _main_loop() in background thread
connector.run_forever()  # Keep main thread alive
```

**What Can Go Wrong**:

- Configuration file missing or malformed (JSON parse error)
- MQTT broker unreachable (network, credentials, firewall)
- Devices offline during initialization (network, power)
- Resource conflicts (port already bound, file lock held)
- Import errors (missing Python packages in container)
- Supervisor process crashes immediately (configuration error)

**Error Handling**:

Most initialization errors should be non-fatal to allow container to start. Connectors should:
- Log errors clearly
- Publish error state to MQTT if possible
- Retry connections with exponential backoff
- Set health check to unhealthy state

Critical errors (config missing, MQTT broker permanently unreachable) may cause container exit. Restart policy will restart container, potentially resolving transient issues.

### Phase 4: Runtime (Steady State Operation)

**Duration**: Continuous until shutdown or configuration change

**Activities**:

**For Polling Connectors** (Level 1, simple Level 2):

Main loop repeatedly:
1. Iterate configured devices
2. Query device state (HTTP GET, TCP request, etc.)
3. Parse response into standardized format
4. Publish to MQTT state topic
5. Sleep for `update_interval` seconds
6. Repeat

```python
# BaseConnector._main_loop() simplified

while self.running:
    for device_config in self.config['devices']:
        if not device_config['enabled']:
            continue

        device_id = device_config['device_id']

        try:
            # Connector implements this
            state = self.get_device_state(device_id, device_config)

            if state:
                # Publish to MQTT
                self.mqtt.publish_state(device_id, state)

                # Cache for GET requests
                self.devices[device_id] = {
                    'state': state,
                    'last_update': datetime.now()
                }
        except Exception as e:
            logger.error(f"Error updating {device_id}: {e}")
            self.mqtt.publish_error(device_id, "UPDATE_ERROR", str(e))

    time.sleep(self.update_interval)
```

**For Event-Driven Connectors** (Level 2/3):

Services push events as they occur:
1. Device sends event (motion detected, button pressed)
2. Service receives via WebSocket/callback/subscription
3. Service processes event data
4. Service calls MQTT bridge endpoint or publishes directly
5. Bridge publishes to MQTT event topic

```python
# Event-driven pattern

async def handle_device_event(event):
    """Called by device protocol library when event occurs"""

    device_id = event['device_id']
    event_type = event['type']
    event_data = event['data']

    # Publish immediately (no polling delay)
    mqtt.publish_event(device_id, event_type, event_data)

    # Update cached state if needed
    if event_type == 'state_change':
        mqtt.publish_state(device_id, event_data)
```

**Command Processing**:

MQTT message received on command topic:
1. Connector's MQTT client receives message via subscription callback
2. Parse topic to extract device ID
3. Parse payload JSON for command details
4. Validate command (timestamp not stale, device exists)
5. Execute command (call device API, send protocol message)
6. Wait for device acknowledgment (with timeout)
7. Publish command response if request included response ID
8. Publish updated state reflecting command execution

```python
# Command handling pattern

def on_command(topic, payload):
    # Extract device ID from topic
    device_id = topic.split('/')[-2]

    # Find device configuration
    device_config = find_device_config(device_id)
    if not device_config:
        return

    # Validate timestamp
    cmd_time = datetime.fromisoformat(payload['timestamp'])
    if (datetime.now() - cmd_time).total_seconds() > 30:
        logger.warning("Ignoring stale command")
        return

    # Execute command
    try:
        command_values = payload.get('values', {})
        result = set_device_state(device_id, device_config, command_values)

        # Send response if requested
        if 'id' in payload:
            response = {
                "cmd_id": payload['id'],
                "status": "success" if result else "error",
                "timestamp": datetime.now().isoformat()
            }
            mqtt.publish(f"devices/{device_id}/cmd/response", response)

        # Publish updated state
        new_state = get_device_state(device_id, device_config)
        mqtt.publish_state(device_id, new_state)

    except Exception as e:
        logger.error(f"Command execution failed: {e}")
        mqtt.publish_error(device_id, "COMMAND_FAILED", str(e))
```

**Multi-Process Coordination** (Level 3):

MQTT bridge continuously:
1. Poll service APIs for state updates
2. Aggregate results from multiple services
3. Publish consolidated state to MQTT
4. Listen for MQTT commands
5. Route commands to appropriate service
6. Monitor service health
7. Restart failed services (handled by supervisord)

```python
# MQTT bridge runtime loop

async def coordination_loop():
    while True:
        try:
            # Poll all internal services
            camera_state = await get_camera_state()
            sensor_state = await get_sensor_state()
            motion_state = await get_motion_state()

            # Aggregate
            combined_state = {
                'camera': camera_state,
                'sensors': sensor_state,
                'motion_detected': motion_state['detected'],
                'last_motion': motion_state['timestamp']
            }

            # Publish to MQTT
            mqtt.publish_state('hub', combined_state)

            # Health check all services
            for service in ['camera', 'sensor', 'motion']:
                if not await check_service_health(service):
                    logger.error(f"{service} service unhealthy")
                    mqtt.publish_error('hub', f'{service.upper()}_UNHEALTHY',
                                     f"{service} service not responding")

        except Exception as e:
            logger.error(f"Coordination error: {e}")

        await asyncio.sleep(5)
```

**What Can Go Wrong**:

- Network interruptions (device unreachable, MQTT broker disconnect)
- Device protocol changes (firmware update breaks API)
- Memory leaks (in long-running processes)
- CPU spikes (inefficient polling, processing load)
- Deadlocks (in multi-threaded implementations)
- Log overflow (excessive debug logging)
- Service crashes (in multi-process connectors)

**Error Handling**:

Runtime errors should be resilient:
- Catch exceptions at appropriate levels (device, loop, process)
- Log errors with full context (device ID, operation, exception)
- Publish error states to MQTT for visibility
- Implement retry logic with exponential backoff
- Track error counts and cease operations if threshold exceeded
- Supervisord automatically restarts crashed processes
- MQTT auto-reconnect on connection loss

### Phase 5: Shutdown (Graceful Termination)

**Trigger**:
- User stops container via web interface
- Container restart for configuration update
- System shutdown
- Container crash/kill

**Signal Flow**:

```
Docker sends SIGTERM to container
    └── Container's PID 1 (main.py or supervisord) receives signal
        └── Signal handler executes cleanup
            ├── Stop MQTT publishing
            ├── Publish offline status
            ├── Close device connections
            ├── Flush buffers
            └── Stop loops/threads

If not exited within timeout (default 10s):
    Docker sends SIGKILL (forceful termination)
        └── Immediate process death (no cleanup)
```

**BaseConnector Shutdown**:

```python
# Signal registration in main.py

import signal
import sys

def signal_handler(signum, frame):
    logger.info(f"Received signal {signum}, shutting down...")
    connector.stop()
    sys.exit(0)

signal.signal(signal.SIGTERM, signal_handler)
signal.signal(signal.SIGINT, signal_handler)

# BaseConnector.stop() implementation

def stop(self):
    logger.info("Stopping connector")

    # Stop main loop
    self.running = False

    # Wait for loop thread to finish
    if self.main_thread:
        self.main_thread.join(timeout=10)

    # Clean up device connections
    try:
        self.cleanup_connection()  # Connector implements
    except Exception as e:
        logger.error(f"Cleanup error: {e}")

    # Disconnect MQTT (will trigger LWT)
    self.mqtt.disconnect()

    logger.info("Connector stopped")
```

**Multi-Process Shutdown**:

```
SIGTERM received by supervisord
    └── supervisord sends SIGTERM to all child processes
        ├── Each process handles signal
        ├── Processes have stopwaitsecs to exit (default 10)
        └── If not exited, supervisord sends SIGKILL

All processes exited
    └── supervisord exits
        └── Container stops
```

```ini
# supervisord.conf shutdown configuration

[program:mqtt-bridge]
command=python /app/mqtt_bridge.py
stopwaitsecs=10           # Wait 10s for graceful shutdown
stopsignal=TERM          # Send SIGTERM first
stopasgroup=true         # Send signal to process group
```

**Last Will and Testament Behavior**:

When MQTT connection is lost (even ungraceful shutdown), the broker automatically publishes the LWT message configured during connection:

```python
# LWT configured during connection
client.will_set(
    topic=f"{BASE_TOPIC}/v1/instances/{instance_id}/status",
    payload="offline",
    qos=1,
    retain=True
)
```

On graceful shutdown, connector should explicitly publish offline before disconnecting to avoid LWT delay:

```python
# Graceful shutdown
mqtt.publish(status_topic, "offline", qos=1, retain=True)
time.sleep(0.5)  # Ensure message delivered
mqtt.disconnect()
```

**What Can Go Wrong**:

- Timeout exceeded (cleanup takes too long, forceful kill)
- Resources not released (file handles, sockets left open)
- Hanging threads (threads don't respond to stop signal)
- LWT not published (broker offline during shutdown)
- Partial state (device left in intermediate state)

**Best Practices**:

- Implement signal handlers in all long-running processes
- Set reasonable timeouts for cleanup operations
- Publish offline status explicitly before disconnect
- Close device connections properly
- Flush log buffers
- Release locks and file handles
- Test shutdown behavior thoroughly
- Monitor LWT messages in production

---

## Container Orchestration

The web backend's `DockerService` class (`web/backend/services/docker_service.py`) manages the complete lifecycle of connector containers. Understanding its patterns is essential for extending the platform.

### DockerService Architecture

**Initialization and Path Resolution**:

```python
class DockerService:
    def __init__(self, base_path: str = None):
        # Resolve container base path
        self.base_path = Path(base_path or os.getenv("IOT2MQTT_PATH", "/app"))

        # Connect to Docker daemon
        self.client = docker.DockerClient(base_url='unix:///var/run/docker.sock')

        # Determine host base path (critical for volume mounts)
        self.host_base_path = self._get_host_base_path()
```

**Host Path Detection**:

The web container runs at `/app` inside its container, but needs to mount host paths into connector containers. It determines the host path by:

1. Inspecting its own container mounts via Docker API
2. Finding the mount where destination is `/app/connectors`
3. Extracting the source (host path)
4. Using parent directory as host base path

Example:
```
Web container mount: /opt/iot2mqtt/connectors → /app/connectors
Therefore host base: /opt/iot2mqtt
```

Fallback to `HOST_IOT2MQTT_PATH` environment variable if detection fails (useful for development outside Docker).

### Image Build Process

Before creating a connector container, `DockerService` ensures the image exists:

```python
def build_image(self, connector_name: str, tag: str = None) -> bool:
    connector_path = self.base_path / "connectors" / connector_name
    dockerfile = connector_path / "Dockerfile"

    if not dockerfile.exists():
        # Create default Dockerfile if missing
        self._create_default_dockerfile(connector_path)

    tag = tag or f"iot2mqtt_{connector_name}:latest"

    try:
        image, build_logs = self.client.images.build(
            path=str(connector_path),
            tag=tag,
            rm=True,  # Remove intermediate containers
            forcerm=True
        )

        # Stream build logs
        for log in build_logs:
            if 'stream' in log:
                logger.info(log['stream'].strip())

        return True
    except Exception as e:
        logger.error(f"Build failed for {connector_name}: {e}")
        return False
```

**Default Dockerfile**:

If connector lacks a Dockerfile, one is generated:

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY *.py ./

# Environment variables
ENV MODE=production
ENV PYTHONUNBUFFERED=1

# Run the connector
CMD ["python", "-u", "main.py"]
```

This enables quick prototyping—drop a `connector.py` and `requirements.txt` in a directory and the system builds it automatically.

### Container Creation

```python
def create_container(self, connector_name: str, instance_id: str,
                    config: Dict[str, Any]) -> Optional[str]:
    container_name = f"iot2mqtt_{connector_name}_{instance_id}"

    # Ensure image exists (build if needed)
    image_tag = f"iot2mqtt_{connector_name}:latest"
    try:
        self.client.images.get(image_tag)
    except docker.errors.ImageNotFound:
        if not self.build_image(connector_name, image_tag):
            return None

    # Ensure instance directory exists on host
    instances_dir = self.host_base_path / "instances" / connector_name
    instances_dir.mkdir(parents=True, exist_ok=True)

    # Prepare container configuration
    container_config = {
        "image": image_tag,
        "name": container_name,
        "detach": True,
        "restart_policy": {"Name": "unless-stopped"},
        "environment": [
            f"INSTANCE_NAME={instance_id}",
            f"CONNECTOR_TYPE={connector_name}",
            "MODE=production",
            "PYTHONUNBUFFERED=1"
        ],
        "volumes": {
            str(self.host_base_path / "shared"): {
                "bind": "/app/shared",
                "mode": "ro"
            },
            str(instances_dir): {
                "bind": "/app/instances",
                "mode": "ro"
            },
            str(self.host_base_path / ".env"): {
                "bind": "/app/.env",
                "mode": "ro"
            }
        },
        "network_mode": "host",
        "labels": {
            "iot2mqtt.type": "connector",
            "iot2mqtt.connector": connector_name,
            "iot2mqtt.instance": instance_id
        }
    }

    # Create and start container
    try:
        container = self.client.containers.run(**container_config)
        logger.info(f"Created container {container_name}")
        return container.short_id
    except Exception as e:
        logger.error(f"Container creation failed: {e}")
        return None
```

### Volume Mounting Strategy

**Shared Libraries** (`shared/`):
```
Host: /opt/iot2mqtt/shared/
Container: /app/shared/
Mode: Read-only
Purpose: BaseConnector, MQTTClient, helper utilities
```

Read-only prevents connectors from accidentally modifying shared code.

**Instance Configurations** (`instances/<connector>/`):
```
Host: /opt/iot2mqtt/instances/yeelight/
Container: /app/instances/
Mode: Read-only
Purpose: Instance JSON files
```

Note the path transformation: the connector-specific directory on the host becomes the flat `/app/instances/` inside the container. This allows multiple instances of the same connector type to share the container image while accessing only their relevant configurations.

Read-only prevents connectors from modifying their own configuration (updates must go through web backend).

**Environment File** (`.env`):
```
Host: /opt/iot2mqtt/.env
Container: /app/.env
Mode: Read-only
Purpose: MQTT credentials, system settings
```

Single source of truth for MQTT configuration and other global settings. Read-only ensures connectors cannot modify system-wide configuration.

### Environment Variable Injection

Injected by `docker_service.py` during container creation:

```python
"environment": [
    f"INSTANCE_NAME={instance_id}",      # Required: instance identifier
    f"CONNECTOR_TYPE={connector_name}",  # Added in v2.0: connector type
    "MODE=production",                   # Operating mode
    "PYTHONUNBUFFERED=1"                 # Python output buffering
]
```

Plus all variables from `.env` file are available due to the volume mount. Connectors can load them using:

```python
from dotenv import load_dotenv
load_dotenv('/app/.env')

mqtt_host = os.getenv('MQTT_HOST')
mqtt_port = int(os.getenv('MQTT_PORT'))
# etc.
```

Or `BaseConnector` loads them automatically through `mqtt_client.py`.

### Network Configuration

```python
"network_mode": "host"
```

Host networking is used (container shares host network namespace) for several reasons:

**Device Discovery**: Many IoT protocols use broadcast/multicast (mDNS, SSDP, ZigBee). These don't work across Docker bridge networks. Host mode enables connectors to discover devices on the LAN.

**Simplified Access**: Devices at `192.168.1.x` are directly reachable without port mapping or NAT.

**Performance**: Direct network stack access, no NAT overhead.

**MQTT Broker Access**: If MQTT broker runs on host, `localhost` works directly.

Trade-off: Less isolation. Connectors can access all host network services. Accept this for device management use case. Security relies on connector trustworthiness (connectors are part of the system, not untrusted user code).

### Restart Policy

```python
"restart_policy": {"Name": "unless-stopped"}
```

Docker automatically restarts container if it crashes, unless explicitly stopped by user. This provides resilience against transient failures:

- Device causes connector crash → automatic restart
- Network interruption → retry connection after restart
- Memory leak causes OOM → restart provides fresh state

User-initiated stops (via web interface) are respected—container won't restart automatically.

Alternative policies not used:
- `no`: No restart (poor for production)
- `always`: Restarts even after user stop (annoying for maintenance)
- `on-failure`: Only restarts on error exit codes (missed process kills)

### Container Lifecycle Operations

**Start**:
```python
def start_container(self, container_id: str) -> bool:
    container = self.get_container(container_id)
    if container:
        try:
            container.start()
            return True
        except Exception as e:
            logger.error(f"Start failed: {e}")
    return False
```

**Stop** (graceful, 10 second timeout):
```python
def stop_container(self, container_id: str, timeout: int = 10) -> bool:
    container = self.get_container(container_id)
    if container:
        try:
            container.stop(timeout=timeout)  # SIGTERM, then SIGKILL after timeout
            return True
        except Exception as e:
            logger.error(f"Stop failed: {e}")
    return False
```

**Restart** (stop then start):
```python
def restart_container(self, container_id: str, timeout: int = 10) -> bool:
    container = self.get_container(container_id)
    if container:
        try:
            container.restart(timeout=timeout)
            return True
        except Exception as e:
            logger.error(f"Restart failed: {e}")
    return False
```

**Remove** (with force option):
```python
def remove_container(self, container_id: str, force: bool = False) -> bool:
    container = self.get_container(container_id)
    if container:
        try:
            container.remove(force=force)  # force stops if running
            return True
        except Exception as e:
            logger.error(f"Remove failed: {e}")
    return False
```

### Log Access

```python
def get_container_logs(self, container_id: str, lines: int = 100,
                      since: datetime = None,
                      follow: bool = False) -> Generator[Dict[str, Any], None, None]:
    container = self.get_container(container_id)
    if not container:
        return

    try:
        kwargs = {
            "tail": lines,
            "stream": True,
            "timestamps": True,
            "follow": follow
        }

        if since:
            kwargs["since"] = since

        for line in container.logs(**kwargs):
            if isinstance(line, bytes):
                line = line.decode('utf-8')

            # Parse timestamp and log content
            parts = line.strip().split(' ', 1)
            if len(parts) == 2:
                timestamp_str, content = parts
                timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
            else:
                timestamp = datetime.now()
                content = line.strip()

            # Determine log level from content
            content_lower = content.lower()
            if 'error' in content_lower or 'exception' in content_lower:
                level = 'error'
            elif 'warning' in content_lower:
                level = 'warning'
            elif 'success' in content_lower or 'connected' in content_lower:
                level = 'success'
            else:
                level = 'info'

            yield {
                "timestamp": timestamp.isoformat(),
                "level": level,
                "content": content
            }
    except Exception as e:
        logger.error(f"Log retrieval failed: {e}")
```

The web interface uses this to display real-time logs with color coding based on detected level.

### Container Listing and Filtering

```python
def list_containers(self, all: bool = True) -> List[Dict[str, Any]]:
    containers = []

    if not self.client:
        return containers

    try:
        for container in self.client.containers.list(all=all):
            # Skip web container itself
            if container.name == "iot2mqtt_web":
                continue

            # Filter by IoT2MQTT containers
            if container.name.startswith("iot2mqtt_") or \
               "iot2mqtt" in container.labels.get("com.docker.compose.project", ""):

                info = {
                    "id": container.short_id,
                    "name": container.name,
                    "image": container.image.tags[0] if container.image.tags else container.image.short_id,
                    "status": container.status,
                    "state": container.attrs["State"]["Status"],
                    "created": container.attrs["Created"],
                    "ports": container.ports,
                    "labels": container.labels
                }

                # Extract instance info from name
                if container.name.startswith("iot2mqtt_"):
                    parts = container.name[9:].split('_', 1)  # Remove "iot2mqtt_" prefix
                    if len(parts) > 1:
                        info["connector_type"] = parts[0]
                        info["instance_id"] = parts[1]

                containers.append(info)
    except Exception as e:
        logger.error(f"Container listing failed: {e}")

    return containers
```

Labels and naming conventions enable the web interface to distinguish connector containers from other Docker containers on the host.

---

## MQTT Contract Integration

The MQTT contract is the system's integration protocol. This section summarizes key aspects and explains integration patterns. For complete specification, see `docs/CONNECTOR_SPEC.md`.

### Topic Structure and Namespace

All topics follow hierarchical structure:

```
{BASE_TOPIC}/v1/instances/{instance_id}/{category}/{identifier}/{operation}
```

Components:
- `{BASE_TOPIC}`: Configurable root (default "IoT2mqtt"), allows multiple system instances
- `v1`: API version for future compatibility
- `instances/{instance_id}`: Instance-specific namespace preventing topic collisions
- `{category}`: Message category (devices, groups, meta, global)
- `{identifier}`: Specific device/group ID
- `{operation}`: Action or message type (state, cmd, error, events)

Example topic for device command:
```
IoT2mqtt/v1/instances/yeelight_ly1skw/devices/light1/cmd
```

### Required Publications

**Instance Status** (mandatory with LWT):

```
Topic: {BASE_TOPIC}/v1/instances/{instance_id}/status
Payload: "online" | "offline"
QoS: 1
Retain: true

Purpose: Indicates connector availability
LWT: Broker publishes "offline" if connection lost
```

Implementation:
```python
# Set LWT during connection
client.will_set(status_topic, "offline", qos=1, retain=True)
client.connect(broker_host, broker_port)

# Publish online after connection
client.publish(status_topic, "online", qos=1, retain=True)

# Explicitly publish offline before disconnect (graceful shutdown)
client.publish(status_topic, "offline", qos=1, retain=True)
client.disconnect()
```

**Device State Updates**:

```json
Topic: {BASE_TOPIC}/v1/instances/{instance_id}/devices/{device_id}/state
Payload: {
  "timestamp": "2025-10-13T10:30:00.000Z",
  "device_id": "light1",
  "state": {
    "power": true,
    "brightness": 75,
    "color_temp": 4000,
    "online": true
  }
}
QoS: 1
Retain: true (recommended)
```

State structure is connector-defined but should be consistent for device type. Retained messages ensure new subscribers immediately receive last known state.

**Individual Property Topics** (optional but recommended):

```
Topic: {BASE_TOPIC}/v1/instances/{instance_id}/devices/{device_id}/state/power
Payload: true

Topic: {BASE_TOPIC}/v1/instances/{instance_id}/devices/{device_id}/state/brightness
Payload: 75
```

Allows subscribers to monitor specific properties without parsing full state object. Useful for dashboard widgets and automations.

**Device Errors**:

```json
Topic: {BASE_TOPIC}/v1/instances/{instance_id}/devices/{device_id}/error
Payload: {
  "timestamp": "2025-10-13T10:30:00.000Z",
  "error_code": "CONNECTION_TIMEOUT",
  "message": "Device did not respond within 5 seconds",
  "severity": "warning",
  "retry_info": {
    "attempt": 3,
    "max_attempts": 5,
    "next_retry": "2025-10-13T10:30:30.000Z"
  }
}
QoS: 1
Retain: false
```

Error codes should be consistent within connector. Severity levels: "info", "warning", "error", "critical".

**Device Events**:

```json
Topic: {BASE_TOPIC}/v1/instances/{instance_id}/devices/{device_id}/events
Payload: {
  "timestamp": "2025-10-13T10:30:00.000Z",
  "event": "motion_detected",
  "data": {
    "confidence": 0.95,
    "zone": "entrance",
    "image_url": "/snapshots/motion_1234.jpg"
  }
}
QoS: 1
Retain: false
```

Events represent discrete occurrences (button press, motion, threshold exceeded). Not retained—subscribers must be connected to receive.

### Required Subscriptions

**Device Commands**:

```
Topic: {BASE_TOPIC}/v1/instances/{instance_id}/devices/{device_id}/cmd
Payload: {
  "id": "cmd_uuid_1234",
  "timestamp": "2025-10-13T10:30:00.000Z",
  "values": {
    "power": true,
    "brightness": 80
  },
  "timeout": 5000
}
```

Connector must:
1. Parse topic to extract device ID
2. Validate timestamp (reject if > 30 seconds old)
3. Find device configuration
4. Execute command via device protocol
5. Publish command response if `id` present
6. Publish updated state

Command response:
```json
Topic: {BASE_TOPIC}/v1/instances/{instance_id}/devices/{device_id}/cmd/response
Payload: {
  "cmd_id": "cmd_uuid_1234",
  "status": "success",
  "timestamp": "2025-10-13T10:30:01.000Z",
  "result": {
    "power": true,
    "brightness": 80
  }
}
```

**Device State Requests**:

```
Topic: {BASE_TOPIC}/v1/instances/{instance_id}/devices/{device_id}/get
Payload: {
  "properties": ["power", "brightness"]  // Optional: specific properties
}
```

Connector should immediately query device and publish current state. If `properties` specified, filter response to include only requested properties.

**Group Commands**:

```
Topic: {BASE_TOPIC}/v1/instances/{instance_id}/groups/{group_id}/cmd
Payload: {
  "values": {
    "power": false
  }
}
```

Apply command to all devices in the group. Group membership defined in instance configuration:

```json
{
  "groups": [
    {
      "group_id": "living_room",
      "devices": ["light1", "light2", "light3"]
    }
  ]
}
```

**Meta Requests**:

```
Topic: {BASE_TOPIC}/v1/instances/{instance_id}/meta/request/devices_list
Topic: {BASE_TOPIC}/v1/instances/{instance_id}/meta/request/info
```

Respond with:
```json
Topic: {BASE_TOPIC}/v1/instances/{instance_id}/meta/devices_list
Payload: [
  {
    "device_id": "light1",
    "global_id": "yeelight_ly1skw_light1",
    "model": "YLDP13YL",
    "enabled": true,
    "online": true
  }
]

Topic: {BASE_TOPIC}/v1/instances/{instance_id}/meta/info
Payload: {
  "instance_id": "yeelight_ly1skw",
  "connector_type": "yeelight",
  "devices_count": 3,
  "groups_count": 1,
  "uptime": 3600
}
```

### Why MQTT as Integration Protocol

**Language Agnostic**: Any language with MQTT client library can participate. Enables multi-language connectors and heterogeneous system components.

**Publish/Subscribe Model**: Decouples publishers from subscribers. Add new consumers (dashboards, automations, loggers) without modifying connectors.

**Message Persistence**: QoS 1/2 ensures delivery even if subscriber temporarily offline. Retained messages provide last known state to new subscribers.

**Lightweight**: Minimal overhead, suitable for IoT devices and high-frequency updates.

**Battle-Tested**: MQTT is industry standard for IoT with robust broker implementations and extensive tooling.

**Observable**: MQTT explorers (MQTTx, MQTT Explorer) enable easy debugging and monitoring. All traffic is visible.

**Flexible**: Topic structure supports arbitrary hierarchies and wildcards. Enables sophisticated routing and filtering.

---

## Troubleshooting and Debugging

### Common Connector Issues

**Container Won't Start**:

Symptoms: Container immediately exits after creation

Check:
1. Container logs: `docker logs iot2mqtt_<connector>_<instance>`
2. Dockerfile syntax errors
3. Missing Python dependencies in requirements.txt
4. Entry point script (`main.py`) not executable or has syntax error
5. Configuration file missing or malformed JSON

Debug:
```bash
# Run container interactively to see startup
docker run -it --rm \
  -e INSTANCE_NAME=test_instance \
  -v /path/to/instances:/app/instances:ro \
  iot2mqtt_yeelight:latest \
  /bin/bash

# Inside container, manually run entry point
python -u main.py
```

**MQTT Connection Refused**:

Symptoms: Logs show "Connection refused" or "Name resolution failed"

Check:
1. MQTT broker is running and reachable
2. Host/port in `.env` are correct
3. Network mode is `host` (for localhost broker) or broker is on LAN
4. Firewall not blocking MQTT port (1883)
5. Authentication credentials in `.env` are correct

Debug:
```bash
# From container, test MQTT connectivity
docker exec iot2mqtt_yeelight_instance1 bash -c "apk add mosquitto-clients && mosquitto_pub -h $MQTT_HOST -p $MQTT_PORT -t test -m test"
```

**Device Not Discovered**:

Symptoms: Device exists on network but connector doesn't find it

Check:
1. Device is on same subnet as connector container
2. Network mode is `host` (required for broadcast/multicast discovery)
3. Device has discovery protocol enabled (varies by device)
4. Firewall not blocking discovery traffic
5. Device is powered on and connected to network

Debug:
```bash
# Network scan from container
docker exec iot2mqtt_yeelight_instance1 nmap -sP 192.168.1.0/24

# Check if discovery protocol works manually
docker exec iot2mqtt_yeelight_instance1 python -c "from yeelight import discover_bulbs; print(discover_bulbs())"
```

**Commands Not Working**:

Symptoms: MQTT commands published but device doesn't respond

Check:
1. Connector subscribed to correct command topic
2. Topic pattern in connector matches published topic
3. Command payload structure matches connector expectations
4. Device is online and reachable
5. Command timestamp not stale (> 30 seconds)

Debug:
```bash
# Monitor MQTT traffic
mosquitto_sub -h localhost -t 'IoT2mqtt/v1/instances/#' -v

# Publish test command manually
mosquitto_pub -h localhost -t 'IoT2mqtt/v1/instances/yeelight_ly1skw/devices/light1/cmd' -m '{"timestamp":"2025-10-13T10:00:00Z","values":{"power":true}}'
```

**State Not Updating**:

Symptoms: Device state changes but not reflected in MQTT

Check:
1. Connector polling interval not too long
2. Connector main loop is running (check logs)
3. Device API returns current state
4. Connector publishes to correct state topic
5. State topic has retain flag set

Debug:
```python
# Add debug logging in connector
logger.debug(f"Polling device {device_id}")
state = self.get_device_state(device_id, device_config)
logger.debug(f"Received state: {state}")
self.mqtt.publish_state(device_id, state)
logger.debug(f"Published state to MQTT")
```

### Multi-Process Debugging

**Process Crashes Repeatedly**:

Symptoms: Supervisord keeps restarting a process

Check:
1. Process logs in container output
2. Process has all required dependencies
3. Environment variables set correctly
4. Ports not conflicting (multiple processes binding same port)
5. Process not crashing during startup

Debug:
```bash
# Get container logs with process identification
docker logs iot2mqtt_cameras_instance1

# Execute shell in container to test process manually
docker exec -it iot2mqtt_cameras_instance1 bash
python /app/services/motion-detector/detector.py  # Run process manually
```

**Inter-Process Communication Failing**:

Symptoms: Services running but not communicating

Check:
1. Services listening on correct localhost ports
2. No port conflicts (lsof -i inside container)
3. HTTP endpoints returning expected responses
4. Timeouts not too short for slow operations
5. Service startup order (dependencies started first)

Debug:
```bash
# Inside container, check ports
docker exec iot2mqtt_cameras_instance1 netstat -tuln

# Test service endpoint
docker exec iot2mqtt_cameras_instance1 curl http://localhost:5000/health
```

**MQTT Bridge Not Publishing**:

Symptoms: Services working but no MQTT messages

Check:
1. Bridge process is running
2. Bridge connected to MQTT broker
3. Bridge polling services successfully
4. Bridge error logs for exceptions
5. MQTT credentials correct in bridge environment

Debug:
```bash
# Check bridge process status
docker exec iot2mqtt_cameras_instance1 supervisorctl status mqtt-bridge

# View bridge logs specifically
docker logs iot2mqtt_cameras_instance1 2>&1 | grep "\[mqtt-bridge\]"
```

### Log Access Strategies

**Container Logs**:

Basic access:
```bash
docker logs iot2mqtt_yeelight_instance1

# Follow in real-time
docker logs -f iot2mqtt_yeelight_instance1

# Last 100 lines
docker logs --tail 100 iot2mqtt_yeelight_instance1

# Since timestamp
docker logs --since "2025-10-13T10:00:00" iot2mqtt_yeelight_instance1
```

**Web Interface**:

Navigate to Containers → Select Container → Logs tab

Features:
- Real-time streaming
- Color-coded by level
- Filterable by keyword
- Downloadable for analysis

**Multi-Process Log Filtering**:

When using supervisord, logs include process prefixes:
```
[go2rtc] 2025-10-13 10:00:00 Starting RTSP server...
[motion-detector] 2025-10-13 10:00:01 Initializing motion detection...
[mqtt-bridge] 2025-10-13 10:00:02 Connected to MQTT broker
```

Filter for specific process:
```bash
docker logs iot2mqtt_cameras_instance1 2>&1 | grep "\[motion-detector\]"
```

**Structured Logging**:

Recommended pattern for connectors:
```python
import logging

# Configure structured logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

# Use consistently
logger.info(f"Processing device {device_id}")
logger.warning(f"Device {device_id} not responding, attempt {retry}/5")
logger.error(f"Failed to update {device_id}: {str(e)}")
```

### Testing Connectors Locally

**Outside Docker**:

Before containerizing, test connector logic locally:

```bash
# Set environment variables
export INSTANCE_NAME=test_instance
export MQTT_HOST=localhost
export MQTT_PORT=1883

# Create test configuration
mkdir -p test_instances
cat > test_instances/test_instance.json <<EOF
{
  "instance_id": "test_instance",
  "connector_type": "yeelight",
  "devices": [
    {"device_id": "test_light", "ip": "192.168.1.100", "enabled": true}
  ],
  "update_interval": 5
}
EOF

# Run connector directly
cd connectors/yeelight
python main.py

# Observe logs and MQTT traffic
mosquitto_sub -h localhost -t 'IoT2mqtt/#' -v
```

**Inside Docker (Development Mode)**:

Use development mode for hot-reload:

```bash
# Start connector in development mode
docker run -it --rm \
  --name iot2mqtt_yeelight_test \
  --network host \
  -e INSTANCE_NAME=test_instance \
  -e MODE=development \
  -v $(pwd)/connectors/yeelight:/app/connector:rw \
  -v $(pwd)/shared:/app/shared:ro \
  -v $(pwd)/test_instances:/app/instances:ro \
  iot2mqtt_yeelight:latest

# In connector main.py, enable hot reload with watchdog
```

The `main.py` in yeelight connector already supports development mode with file watching—when `connector.py` changes, it automatically reloads without restarting container.

**Unit Testing**:

Test connector methods in isolation:

```python
# tests/test_yeelight_connector.py

import unittest
from connectors.yeelight.connector import Connector

class TestYeelightConnector(unittest.TestCase):
    def setUp(self):
        self.config = {
            "instance_id": "test",
            "devices": [
                {"device_id": "light1", "ip": "192.168.1.100"}
            ]
        }
        self.connector = Connector(config=self.config)

    def test_parse_capabilities(self):
        props = {"power": "on", "bright": 80, "ct": 4000}
        caps = self.connector._parse_capabilities(props)
        self.assertIn("power", caps)
        self.assertIn("brightness", caps)

    def test_state_parsing(self):
        # Mock device response
        # Test state conversion logic
        pass

if __name__ == '__main__':
    unittest.main()
```

**Integration Testing**:

Test full connector behavior with real or mocked devices:

```python
# tests/integration/test_yeelight_integration.py

import time
import paho.mqtt.client as mqtt
from connectors.yeelight.connector import Connector

def test_connector_publishes_state():
    # Start connector
    connector = Connector(instance_name="test")
    connector.start()

    # Subscribe to MQTT
    received_messages = []
    def on_message(client, userdata, msg):
        received_messages.append(msg)

    mqtt_client = mqtt.Client()
    mqtt_client.on_message = on_message
    mqtt_client.connect("localhost", 1883)
    mqtt_client.subscribe("IoT2mqtt/v1/instances/test/devices/+/state")
    mqtt_client.loop_start()

    # Wait for connector to poll and publish
    time.sleep(15)

    # Verify message received
    assert len(received_messages) > 0, "No state messages published"

    # Cleanup
    connector.stop()
    mqtt_client.loop_stop()
```

---

## Deployment and Operations

### Instance Creation via Web Interface

**User Flow**:

1. Navigate to Integrations page
2. Click "Add Integration"
3. Select connector type (e.g., "Yeelight")
4. Follow setup flow rendered from `setup.json`:
   - Enter IP address (form step)
   - Validate connection (tool step)
   - Configure device settings (form step)
   - Review configuration (summary step)
   - Confirm creation
5. System creates instance and starts container
6. Dashboard shows new device

**Behind the Scenes**:

- Frontend requests setup schema: `GET /api/integrations/yeelight/setup`
- Backend returns `connectors/yeelight/setup.json` content
- Frontend renders each step dynamically
- On tool steps, frontend calls: `POST /api/actions/yeelight/execute`
- Backend proxies to test-runner for script execution
- On completion, frontend calls: `POST /api/instances`
- Backend:
  - Validates configuration
  - Calls `ConfigService.save_instance_config()`
  - Calls `DockerService.create_container()`
  - Returns success/error
- Frontend navigates to instance detail page

### Configuration Updates

**Process**:

1. User modifies configuration in web interface (future feature)
2. Backend validates changes
3. Backend updates instance JSON file
4. Backend restarts connector container
5. Connector reloads configuration on startup
6. New settings take effect

**Implementation** (to be added):

```python
# PUT /api/instances/{instance_id}
def update_instance(instance_id: str, updated_config: dict):
    # Parse instance ID to get connector type
    connector_type = extract_connector_type(instance_id)

    # Update configuration file
    config_service.save_instance_config(connector_type, instance_id, updated_config)

    # Restart container
    container_name = f"iot2mqtt_{connector_type}_{instance_id}"
    docker_service.restart_container(container_name)

    return {"status": "updated"}
```

Restart is necessary because:
- Connector loaded configuration during initialization
- No hot-reload mechanism for configuration (by design, keeps connectors simple)
- Restart is fast (< 10 seconds typically)
- Brief downtime acceptable for configuration changes

### Monitoring and Health Checks

**Container Health**:

Docker health checks (not currently implemented but recommended):

```dockerfile
# In connector Dockerfile
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
  CMD python -c "import sys; sys.exit(0 if check_health() else 1)"
```

Health check script should verify:
- MQTT connection alive
- Main process running
- Device communications working
- No excessive error rates

**MQTT Status Monitoring**:

Subscribe to status topics:
```
IoT2mqtt/v1/instances/+/status
```

Track:
- Instances that are offline (payload = "offline")
- Instances that haven't published recently (stale retained messages)
- Rapid online/offline cycles (restart loops)

**Error Topic Monitoring**:

Subscribe to error topics:
```
IoT2mqtt/v1/instances/+/devices/+/error
```

Alert on:
- Critical severity errors
- Repeated errors for same device
- Error rate increase

**Log Analysis**:

Aggregate container logs for analysis:

```bash
# Export logs for analysis
docker logs iot2mqtt_yeelight_instance1 > yeelight_instance1.log

# Search for errors
grep -i error yeelight_instance1.log

# Count error frequency
grep -i error yeelight_instance1.log | wc -l

# Extract timestamps of errors for timeline
grep -i error yeelight_instance1.log | cut -d' ' -f1-2
```

**Resource Usage**:

Monitor container resource consumption:

```bash
# Real-time stats
docker stats iot2mqtt_yeelight_instance1

# Specific metrics
docker stats --no-stream --format "table {{.Container}}\t{{.CPUPerc}}\t{{.MemUsage}}" iot2mqtt_yeelight_instance1
```

Set alerts for:
- CPU > 80% sustained
- Memory growth indicating leak
- Network bandwidth spikes

### Backup and Recovery

**What to Back Up**:

```
/opt/iot2mqtt/
├── .env                    # MQTT credentials, system config (CRITICAL)
├── instances/              # Instance configurations (CRITICAL)
│   ├── yeelight/
│   └── zigbee/
├── secrets/                # Encrypted secrets (CRITICAL)
│   ├── .master.key        # Encryption key (MOST CRITICAL)
│   └── instances/
```

Do NOT need to back up:
- `connectors/` (code, in git)
- `web/` (code, in git)
- `shared/` (code, in git)
- Docker images (rebuild from Dockerfile)
- Container state (ephemeral)

**Backup Strategy**:

```bash
#!/bin/bash
# backup.sh - Backup IoT2MQTT critical data

BACKUP_DIR="/backups/iot2mqtt"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="iot2mqtt_backup_${TIMESTAMP}.tar.gz"

cd /opt/iot2mqtt

tar czf "${BACKUP_DIR}/${BACKUP_FILE}" \
  .env \
  instances/ \
  secrets/

echo "Backup created: ${BACKUP_DIR}/${BACKUP_FILE}"

# Retain last 7 backups
ls -t ${BACKUP_DIR}/iot2mqtt_backup_*.tar.gz | tail -n +8 | xargs rm -f
```

Schedule with cron:
```
0 2 * * * /opt/iot2mqtt/backup.sh
```

**Recovery Process**:

```bash
# 1. Install fresh system (Docker, IoT2MQTT)
git clone https://github.com/your-org/IoT2mqtt.git
cd IoT2mqtt

# 2. Restore backup
tar xzf /backups/iot2mqtt_backup_20251013_020000.tar.gz

# 3. Start system
./scripts/run.sh

# 4. Connectors will auto-create from instance configs
# Containers will be created and started automatically
# MQTT connections will resume
# Devices will be rediscovered if needed
```

Recovery time: 5-10 minutes depending on number of connectors and container build times.

### Scaling Considerations

**Single Host Limitations**:

Current architecture runs all containers on single Docker host. Limitations:

- Number of containers limited by host resources
- All connectors share host network for device discovery
- Single point of failure

Practical limits (example host with 16GB RAM, 8 cores):
- ~50-100 simple connectors (Level 1)
- ~20-30 multi-process connectors (Level 3)
- Device count limited by protocol (some protocols broadcast-heavy)

**Multi-Host Future Considerations**:

For larger deployments, consider:

- Docker Swarm or Kubernetes orchestration
- Shared configuration storage (NFS, distributed file system)
- MQTT broker clustering for high availability
- Load balancing for web interface
- Distributed connector placement (connectors near devices)

Current architecture supports this evolution—the MQTT contract remains identical, only orchestration layer changes.

---

## Design Decisions and Rationales

Understanding why the system is architected as it is helps contributors make consistent decisions and avoid regressions.

### Why One Instance Equals One Container?

**Decision**: Each connector instance gets its own dedicated container.

**Rationale**:

**Isolation**: Connectors for different device types have different dependencies (libraries, binaries, tools). Container isolation prevents dependency conflicts. Yeelight connector needs `yeelight` Python library; Zigbee connector might need Zigbee2MQTT; camera connector needs ffmpeg. All coexist without interaction.

**Failure Isolation**: If one connector crashes, others continue running. A memory leak in one connector doesn't affect others. Restart policies apply per-instance, so problematic connector can restart without disrupting stable ones.

**Resource Control**: Docker's resource limits (CPU, memory) apply per-container. Can allocate more resources to resource-intensive connectors (video processing) while limiting lightweight ones (simple sensors).

**Independent Updates**: Upgrade connector for one instance without affecting others. Can test new connector version with single instance before rolling out to all.

**Simplified Management**: Web interface manages containers directly via Docker API. One-to-one mapping simplifies UI—each row in container list is one instance. No need to track which instances run in which containers.

**Clear Lifecycle**: Instance creation = container creation. Instance deletion = container removal. No ambiguity about which instances are active.

**Alternative Considered**: Multi-instance containers where one container runs multiple instances of the same connector type. Rejected because:
- Shared fate (one crash affects multiple instances)
- Complex resource attribution
- More difficult to manage via web interface
- Minimal resource savings (connector instances are lightweight)

### Why MQTT as Integration Protocol?

**Decision**: Use MQTT for all device communication between connectors and consumers.

**Rationale**:

**Language Agnostic**: MQTT clients available for virtually every language. Enables:
- Multi-language connectors (Level 3 architecture)
- Integration with external systems (Home Assistant, Node-RED, custom dashboards)
- Future components in any language

**Decoupling**: Publishers don't know about subscribers. Add new consumers (analytics, alerting, logging) without modifying connectors. Connectors focus solely on device communication and MQTT publishing.

**Persistence**: QoS 1/2 and retained messages ensure reliability:
- Messages delivered even if consumer temporarily offline
- New subscribers immediately receive last known state
- System state survives restarts

**Scalability**: Pub/sub model scales horizontally. Add brokers, use bridging, cluster for high availability. Each connector is independent publisher—no central bottleneck.

**Industry Standard**: MQTT is proven standard for IoT with robust implementations (Mosquitto, HiveMQ, EMQX), extensive tooling (MQTT Explorer, MQTTx), and wide adoption.

**Observable**: All system communication visible by subscribing to topics. Debugging becomes transparent. Can add monitoring by subscribing to relevant topics without instrumenting connectors.

**Alternatives Considered**:

- **HTTP REST**: Requires connectors to expose endpoints, implement authentication, handle request routing. More complex, less scalable, no pub/sub. Good for request/response but poor for state updates and events.

- **WebSocket**: Good for real-time communication but requires persistent connections, complex connection management, no message persistence. Better for specific use cases within connectors (Level 3) than system-wide integration.

- **gRPC**: Strong typing, efficient, but language-specific (not all languages have good gRPC support), more complex, overkill for IoT use case.

- **Direct Database**: Connectors write to shared database, consumers read. Creates tight coupling, single point of failure, scaling challenges, difficult to add consumers, no real-time notification.

MQTT chosen because it's the best fit for IoT integration: lightweight, scalable, language-agnostic, reliable, and observable.

### Why Support Multi-Process Within Single Container?

**Decision**: Enable multi-process connectors within single container rather than multi-container setups (docker-compose stacks).

**Rationale**:

**Preserves One-Instance-One-Container Principle**: Maintaining this principle simplifies:
- Container management (one container to start/stop/restart)
- Web UI (one row per instance)
- Resource attribution (clear which instance consumes resources)
- Log access (one container to query)

**Sufficient for Most Use Cases**: Multi-process within single container provides:
- Multi-language capability (Go, Python, Node.js all in one image)
- Process isolation (crash doesn't affect others)
- Localhost communication (efficient, no network overhead)
- Coordinated lifecycle (supervisord manages all)

This covers 95% of connector requirements. Only extreme edge cases need multi-container (e.g., running existing complex apps with own orchestration needs).

**Simpler Deployment**: Single container means:
- Standard Docker `run` command (no compose files to parse)
- One image to build
- One health check to define
- One set of volume mounts

Multi-container would require:
- Custom docker-compose.yml per instance
- Complex variable substitution
- Network creation per instance
- Multiple images to build
- Orchestration of orchestration (web managing compose)

**Developer Familiarity**: Supervisord pattern is well-known for managing multiple processes in containers. Docker documentation includes examples. Developers find it approachable.

**Localhost Performance**: All processes in same container communicate via localhost:
- No network latency (loopback interface)
- No NAT overhead
- No port mapping complexity
- Simple debugging (curl localhost:port works)

**Alternative Considered**: Multi-container instances using docker-compose. Each instance gets its own compose file defining multiple services. Rejected because:
- Violates one-instance-one-container principle
- More complex to manage (Docker API for single containers vs compose)
- Web backend would need to parse/generate compose files
- Network isolation more complex (each instance needs own network)
- Resource attribution harder (multiple containers per instance)
- Log aggregation more complex
- Minimal benefit over multi-process (isolation already provided by processes and supervisord)

### Why is BaseConnector Optional?

**Decision**: `BaseConnector` is a helper library, not a requirement. Connectors can implement MQTT contract directly.

**Rationale**:

**Language Freedom**: Making BaseConnector mandatory would lock connectors into Python. Optional design enables:
- Go connectors using native MQTT libraries
- Node.js connectors using popular npm packages
- Rust connectors for performance-critical applications
- Wrapping existing tools written in any language

This is essential for Level 3 multi-language architecture.

**Flexibility**: Some connector patterns don't fit BaseConnector's assumptions:
- Event-driven vs polling (BaseConnector assumes polling loop)
- Custom MQTT patterns (BaseConnector uses specific topic structure)
- Non-device models (BaseConnector assumes devices with get/set state)
- Integration with existing services (may have own architecture)

Optional design lets developers choose best approach for their use case.

**Learning Path**: BaseConnector is useful for learning:
- Shows MQTT contract implementation example
- Provides working polling pattern
- Handles common boilerplate
- Good for first connector development

Once developers understand the contract, they can implement directly for more control.

**Maintenance**: Forcing all connectors through BaseConnector creates maintenance burden:
- Changes to BaseConnector affect all connectors
- Hard to evolve without breaking compatibility
- Limits innovation (new patterns require changing base class)

Optional design lets BaseConnector evolve independently or even be replaced without affecting connectors that don't use it.

**Contract-Based Design**: The real interface is the MQTT contract (environment variables, topics, payloads). BaseConnector is one way to implement it, but not the only way. This separation makes the system more robust and flexible.

**Alternative Considered**: Mandatory BaseConnector inheritance. Every connector extends BaseConnector and implements abstract methods. Rejected because:
- Limits language choice to Python
- Prevents alternative architectural patterns
- Creates tight coupling between framework and implementations
- Reduces system evolvability
- Not necessary—MQTT contract is sufficient interface

**Best of Both Worlds**: Current design gives developers choice:
- Use BaseConnector for quick development and common patterns
- Implement contract directly for flexibility and alternative languages
- Mix approaches (some connectors use BaseConnector, others don't)

---

## References and Further Reading

### Detailed Documentation

**CONNECTOR_SPEC.md**: Complete specification of the connector contract including all MQTT topics, payload schemas, environment variables, and best practices. Required reading for connector developers. Located at `docs/CONNECTOR_SPEC.md`.

**setup-flows.md**: Full reference for setup flow schema including all step types, tool definitions, OAuth integration, templating syntax, and validation rules. Essential for creating connector onboarding experiences. Located at `docs/setup-flows.md`.

**backend-services.md**: Detailed documentation of web backend services including ConfigService, DockerService, and MQTTService. Useful for understanding platform internals. Located at `docs/backend-services.md`.

**runtime-storage.md**: Explanation of file paths, directory structure, and data storage patterns. Helpful for understanding where configuration and secrets live. Located at `docs/runtime-storage.md`.

### Templates and Examples

**Simple Template** (`connectors/_template/`): Minimal connector using BaseConnector. Best starting point for polling-based connectors. Includes basic Dockerfile, requirements.txt, and single-step setup.json.

**Multi-Process Template** (`connectors/_template-multiprocess/`): Comprehensive template demonstrating supervisord-based multi-process architecture. Shows Python + Node.js coordination, MQTT bridge pattern, and service communication. Includes detailed README explaining patterns.

**Working Example** (`connectors/_example-multiprocess/`): Functional multi-process connector implementing realistic sensor hub scenario. Demonstrates state aggregation, protocol handling, and production-ready patterns.

**Yeelight Connector** (`connectors/yeelight/`): Production connector for Yeelight smart bulbs. Shows real-world usage of BaseConnector, device discovery, command handling, and error recovery.

### Source Code Reference

**Base Connector** (`shared/base_connector.py`): Optional helper class providing MQTT boilerplate, polling loop, and common patterns. Study this to understand one way to implement the contract.

**MQTT Client** (`shared/mqtt_client.py`): Advanced MQTT client with LWT, timestamp ordering, response handling, and convenience methods. Useful even outside BaseConnector.

**Docker Service** (`web/backend/services/docker_service.py`): Container orchestration logic. Read this to understand how containers are created, configured, and managed.

**Config Service** (`web/backend/services/config_service.py`): Configuration management with file locking and secret handling. Shows how instance configs are stored and loaded.

**Test Runner** (`test-runner/main.py`): Action script executor. Understand how setup-time scripts run in isolated environment.

### API Documentation

**REST API Reference** (`docs/api-reference.md`): Complete HTTP API documentation for programmatic interaction with the platform.

**Integration Best Practices** (`docs/integration-best-practices.md`): Guidelines for designing and implementing high-quality connectors.

### External Resources

**MQTT Specification**: http://mqtt.org/documentation - Official MQTT protocol documentation

**Docker Documentation**: https://docs.docker.com/ - Docker concepts, API reference, best practices

**Supervisord Documentation**: http://supervisord.org/ - Process manager used in multi-process connectors

**Paho MQTT Client**: https://www.eclipse.org/paho/clients/python/ - Python MQTT library used by BaseConnector

---

## Document Maintenance

**Version**: This document describes IoT2MQTT v2.0 architecture including multi-process connector capabilities introduced in the v2.0 release.

**Update Triggers**: This document should be reviewed and updated when:

- New connector complexity levels are added
- MQTT contract changes (new required topics, payload schemas)
- Environment variables injected by `docker_service.py` change
- Volume mounting strategy changes
- BaseConnector API changes
- Major architectural decisions are made

**Ownership**: This document is maintained by the IoT2MQTT core team. Contributions and corrections are welcome via pull requests.

**Related Documents**: Changes to this architecture document may necessitate updates to:
- `docs/CONNECTOR_SPEC.md` (if contract changes)
- Template READMEs (if new patterns introduced)
- `docs/setup-flows.md` (if setup architecture changes)
- Example implementations (if patterns evolve)

---

**Last Updated**: 2025-10-13
**IoT2MQTT Version**: 2.0
**Document Version**: 1.0
