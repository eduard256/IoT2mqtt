# Multi-Process Connector Template

This template demonstrates how to create complex IoT2MQTT connectors that run multiple services (Python, Node.js, Go, etc.) within a single Docker container managed by **supervisord**.

## 🎯 When to Use This Template

Use this template when your connector needs:

- **Multiple programming languages** - Combine Python, Node.js, Go, Rust, etc.
- **Multiple processes** - Run several services that coordinate via HTTP APIs
- **Complex architecture** - Go2rtc for streaming + Python for AI + Node.js for real-time processing
- **Existing projects** - Wrap external projects like Zigbee2MQTT with your MQTT bridge
- **High-performance workloads** - Use the right language for each task

Use the simple `_template` instead if you only need a single Python process.

## 🏗️ Architecture Overview

```
┌─────────────────────────────────────────────────────┐
│  Docker Container (single instance)                 │
│                                                     │
│  ┌─────────────────────────────────────────────┐  │
│  │  Supervisord (Process Manager)              │  │
│  │                                              │  │
│  │  ┌────────────────┐  ┌──────────────────┐  │  │
│  │  │ Python Service │  │ Node.js Service  │  │  │
│  │  │ Port 5001      │  │ Port 5002        │  │  │
│  │  │ HTTP REST API  │  │ HTTP REST API    │  │  │
│  │  └────────────────┘  └──────────────────┘  │  │
│  │           ▲                    ▲            │  │
│  │           │  localhost HTTP    │            │  │
│  │           │                    │            │  │
│  │  ┌────────┴────────────────────┴─────────┐ │  │
│  │  │  MQTT Bridge (Coordinator)            │ │  │
│  │  │  - Implements IoT2MQTT contract       │ │  │
│  │  │  - Routes MQTT → HTTP to services     │ │  │
│  │  │  - Polls services → publishes MQTT    │ │  │
│  │  └───────────────────────────────────────┘ │  │
│  └─────────────────────────────────────────────┘  │
│                                                     │
│  All processes communicate via localhost:port      │
│  MQTT connection to broker (external)              │
└─────────────────────────────────────────────────────┘
```

## 📁 Directory Structure

```
connectors/_template-multiprocess/
├── Dockerfile               # Multi-stage build with all languages
├── supervisord.conf         # Process management configuration
├── requirements.txt         # Python dependencies
├── mqtt_bridge.py          # Main coordinator (implements MQTT contract)
│
├── services/               # Backend services
│   ├── python-service/
│   │   ├── app.py         # Flask HTTP API
│   │   └── requirements.txt
│   └── nodejs-service/
│       ├── index.js       # Express HTTP API
│       └── package.json
│
├── actions/               # Setup-time validation scripts
│   └── example_validate.py
│
├── setup.json            # Web UI setup flow
├── manifest.json         # Connector metadata
└── README.md            # This file
```

## 🔧 How It Works

### 1. Supervisord Process Management

Supervisord starts and monitors all processes:

- **Priority-based startup** - Backend services start first (priority 10), MQTT bridge starts last (priority 999)
- **Automatic restart** - If a process crashes, supervisord restarts it
- **Log aggregation** - All process logs go to Docker stdout/stderr
- **Graceful shutdown** - Properly terminates all processes on container stop

### 2. Service Coordination via HTTP

Services expose HTTP REST APIs on localhost:

```python
# MQTT Bridge calls Python service
response = requests.post('http://localhost:5001/command', json={...})

# MQTT Bridge polls Node.js service
status = requests.get('http://localhost:5002/status')
```

This pattern works with **any language** - as long as services expose HTTP APIs, they can coordinate.

### 3. MQTT Bridge Pattern

The `mqtt_bridge.py` is the **only component** that talks to MQTT. It:

1. **Subscribes** to MQTT command topics
2. **Routes** commands to appropriate backend services via HTTP
3. **Polls** services for status updates
4. **Publishes** combined state to MQTT

This clean separation means backend services don't need MQTT knowledge - they just need HTTP APIs.

## 🚀 Quick Start

### 1. Copy Template

```bash
cp -r connectors/_template-multiprocess connectors/my-connector
cd connectors/my-connector
```

### 2. Customize Services

**Option A: Modify existing services**

Edit `services/python-service/app.py` and `services/nodejs-service/index.js` to implement your logic.

**Option B: Add new services**

1. Create new directory in `services/`
2. Add service code
3. Update `Dockerfile` to install dependencies
4. Add process to `supervisord.conf`

**Option C: Add binary services (Go, Rust, etc.)**

```dockerfile
# In Dockerfile, add:
RUN wget -O /usr/local/bin/go2rtc \
    https://github.com/AlexxIT/go2rtc/releases/latest/download/go2rtc_linux_amd64 \
    && chmod +x /usr/local/bin/go2rtc
```

```ini
# In supervisord.conf, add:
[program:go2rtc]
command=/usr/local/bin/go2rtc -c /app/config/go2rtc.yaml
autostart=true
autorestart=true
priority=5
```

### 3. Update MQTT Bridge

Edit `mqtt_bridge.py` to:

- Add service URLs
- Implement command routing logic
- Define state polling logic
- Map internal state to MQTT format

### 4. Configure Setup Flow

Edit `setup.json` to define your Web UI configuration flow.

### 5. Build and Test

```bash
# Build Docker image
docker build -t iot2mqtt_my-connector:latest .

# Run container with required environment
docker run --rm -it \
  -e INSTANCE_NAME=test_instance \
  -e CONNECTOR_TYPE=my-connector \
  -e MQTT_HOST=mqtt_broker \
  -e MQTT_PORT=1883 \
  -e MQTT_USERNAME=user \
  -e MQTT_PASSWORD=pass \
  -e MQTT_BASE_TOPIC=IoT2mqtt \
  -v $(pwd)/../../shared:/app/shared:ro \
  iot2mqtt_my-connector:latest
```

### 6. Check Process Status

Inside container:

```bash
# View all processes
supervisorctl status

# Restart a service
supervisorctl restart python-service

# View logs
supervisorctl tail mqtt-bridge
```

## 🔌 Adding New Services

### Example: Adding a Go Service

**1. Update Dockerfile:**

```dockerfile
# Install Go
RUN apt-get update && apt-get install -y golang-go

# Build Go service
COPY services/go-service/ /app/services/go-service/
WORKDIR /app/services/go-service
RUN go build -o service main.go
```

**2. Add to supervisord.conf:**

```ini
[program:go-service]
command=/app/services/go-service/service
autostart=true
autorestart=true
priority=10
environment=PORT=5003
```

**3. Update mqtt_bridge.py:**

```python
GO_SERVICE_URL = os.getenv('GO_SERVICE_URL', 'http://localhost:5003')

def _call_go_service(self, endpoint: str, data: dict):
    resp = requests.post(f"{GO_SERVICE_URL}/{endpoint}", json=data)
    return resp.json()
```

## 📝 IoT2MQTT Contract Implementation

The MQTT bridge **must** follow the IoT2MQTT contract:

### Required Environment Variables

- `INSTANCE_NAME` - Unique instance identifier
- `CONNECTOR_TYPE` - Type of connector (for logging)
- `MQTT_HOST`, `MQTT_PORT`, `MQTT_USERNAME`, `MQTT_PASSWORD` - From .env file
- `MQTT_BASE_TOPIC` - Base topic prefix

### Required MQTT Topics

**Subscribe (receive commands):**
```
{BASE_TOPIC}/v1/instances/{instance_id}/devices/{device_id}/cmd
{BASE_TOPIC}/v1/instances/{instance_id}/devices/{device_id}/get
{BASE_TOPIC}/v1/instances/{instance_id}/meta/request/+
```

**Publish (send state):**
```
{BASE_TOPIC}/v1/instances/{instance_id}/status  (online/offline with LWT)
{BASE_TOPIC}/v1/instances/{instance_id}/devices/{device_id}/state
{BASE_TOPIC}/v1/instances/{instance_id}/devices/{device_id}/error
```

See `docs/CONNECTOR_SPEC.md` for complete specification.

## 🐛 Troubleshooting

### Services Not Starting

**Check supervisord status:**
```bash
docker exec -it <container> supervisorctl status
```

**View service logs:**
```bash
docker exec -it <container> supervisorctl tail -f python-service
```

**Common issues:**
- Port conflicts (two services on same port)
- Missing dependencies (check Dockerfile installation)
- Incorrect working directory (set in supervisord.conf)

### Services Can't Communicate

**Verify localhost connectivity:**
```bash
docker exec -it <container> curl http://localhost:5001/health
```

**Common issues:**
- Service not binding to 0.0.0.0 (bind to all interfaces)
- Firewall rules (unlikely in container)
- Wrong port in URL

### MQTT Connection Issues

**Check MQTT credentials:**
```bash
docker exec -it <container> env | grep MQTT
```

**Test MQTT connectivity:**
```bash
docker exec -it <container> curl mqtt://mqtt_host:1883
```

**Common issues:**
- .env file not mounted correctly
- Wrong MQTT broker address
- Authentication credentials incorrect

### Process Crashes and Restarts

**View crash logs:**
```bash
docker logs <container> | grep ERROR
```

**Disable autorestart for debugging:**
```ini
# In supervisord.conf
autorestart=false  # Temporarily disable
```

**Common issues:**
- Uncaught exceptions in service code
- Resource exhaustion (memory/CPU)
- Dependency conflicts

## 🔍 Real-World Examples

### Camera Management System

```
Services:
- go2rtc: RTSP stream handling (Go binary)
- motion-detector: Frame analysis (Node.js)
- object-recognition: AI processing (Python + TensorFlow)
- mqtt-bridge: Coordination (Python)
```

### Zigbee2MQTT Wrapper

```
Services:
- zigbee2mqtt: Original project (Node.js)
- mqtt-parser: Translate Z2M MQTT → IoT2MQTT (Python)
```

### Industrial IoT Gateway

```
Services:
- modbus-reader: Read PLC data (Python)
- data-processor: Process and aggregate (Go for performance)
- mqtt-bridge: Publish to IoT2MQTT (Python)
```

## 📚 Additional Resources

- **CONNECTOR_SPEC.md** - Complete contract specification
- **_template/** - Simple single-process template
- **Supervisord Docs** - http://supervisord.org/
- **IoT2MQTT Wiki** - Project documentation

## ⚠️ Important Notes

### One Container = One Instance

Each connector instance runs in its own container. Do not try to run multiple instances in the same container - create separate containers instead.

### Localhost Communication

All services share the same network namespace, so they can communicate via `localhost`. This is fast and secure.

### Log Aggregation

All process stdout/stderr goes to Docker logs. Use structured logging (JSON) for easier parsing:

```python
logger.info(json.dumps({"event": "command_received", "device": device_id}))
```

### Resource Limits

Multi-process containers use more resources. Set appropriate Docker resource limits:

```yaml
deploy:
  resources:
    limits:
      memory: 2G
      cpus: '2.0'
```

## 🎓 Best Practices

1. **Start services in order** - Use supervisord priorities
2. **Implement health checks** - Each service should expose `/health`
3. **Handle graceful shutdown** - Respond to SIGTERM
4. **Use environment variables** - For all configuration
5. **Log everything** - Structured logs help debugging
6. **Test locally first** - Before deploying to IoT2MQTT
7. **Document your services** - Explain what each does
8. **Keep services focused** - Each service should do one thing well

## 💡 When NOT to Use Multi-Process

Use simple `_template` if:
- Single Python process is sufficient
- No need for multiple languages
- Simple polling device connector
- Learning IoT2MQTT for the first time

Multi-process adds complexity - only use it when you need the power it provides.

---

**Need help?** Check the IoT2MQTT documentation or open an issue on GitHub.
