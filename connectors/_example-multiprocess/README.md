# Multi-Process Sensor Hub - Reference Implementation

This is a complete working example demonstrating the **multi-process connector architecture** for IoT2MQTT. It shows how to build complex connectors that coordinate multiple services within a single container while maintaining clean separation of concerns.

## Purpose

This example serves as a **reference implementation** for developers building complex multi-process connectors. Unlike templates which provide minimal structure, this example includes:

- **Complete working code** for all services
- **Realistic sensor simulation** with changing values and errors
- **Production-ready patterns** for error handling and state management
- **Extensive comments** explaining design decisions
- **Manual testing procedures** to understand behavior

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│           Docker Container (sensor-hub instance)            │
│                                                             │
│  ┌──────────────────┐    ┌──────────────────┐            │
│  │ Serial Handler   │    │  HTTP Poller     │            │
│  │ (Python/Flask)   │    │  (Node.js/Express)│            │
│  │ Port: 5001       │    │  Port: 5002       │            │
│  │                  │    │                   │            │
│  │ - Temperature    │    │ - Motion          │            │
│  │ - Humidity       │    │ - Detection       │            │
│  └────────┬─────────┘    └────────┬──────────┘            │
│           │                       │                        │
│           │ REST API             │ REST API               │
│           │                       │                        │
│           └───────────┬───────────┘                        │
│                       │                                    │
│                       ▼                                    │
│           ┌────────────────────┐                          │
│           │ State Aggregator   │                          │
│           │ (Python/Flask)     │                          │
│           │ Port: 5003         │                          │
│           │                    │                          │
│           │ - Caching (10s)    │                          │
│           │ - Coordination     │                          │
│           └─────────┬──────────┘                          │
│                     │                                      │
│                     │ REST API                            │
│                     │                                      │
│                     ▼                                      │
│           ┌──────────────────────┐                        │
│           │   MQTT Bridge        │                        │
│           │   (Python)           │                        │
│           │                      │                        │
│           │ - IoT2MQTT Contract  │ ◄────── MQTT Broker   │
│           │ - State Publishing   │                        │
│           │ - Command Routing    │                        │
│           └──────────────────────┘                        │
│                                                            │
│  All processes managed by supervisord                     │
└────────────────────────────────────────────────────────────┘
```

## Why Multiple Processes?

This example demonstrates scenarios where multiple processes are beneficial:

1. **Protocol Diversity**: Serial handler in Python, HTTP poller in Node.js - using the best tool for each protocol
2. **Separation of Concerns**: Each service has a single responsibility making code clearer and more maintainable
3. **Independent Scaling**: Services can be monitored and restarted independently by supervisord
4. **Language Optimization**: Use Python for data processing, Node.js for async I/O operations

## Services Description

### 1. Serial Handler (Python/Flask)

**Purpose**: Simulates reading from sensors connected via serial port

**Location**: `services/serial-handler/app.py`

**Endpoints**:
- `GET /health` - Service health status
- `GET /sensors` - List all sensors handled by this service
- `GET /sensor/{sensor_id}` - Get current reading (performs fresh read)
- `GET /sensor/{sensor_id}/cached` - Get cached reading (no hardware access)
- `GET /errors` - Current sensor errors

**Simulation Details**:
- Temperature: Base 22°C ± 3°C daily variation + noise
- Humidity: Base 45% ± 10% daily variation + noise
- Random sensor errors (5% probability) to demonstrate error handling

**Why Python**: Excellent libraries for serial communication (pyserial), easy data processing

### 2. HTTP Poller (Node.js/Express)

**Purpose**: Polls motion detectors that expose HTTP endpoints

**Location**: `services/http-poller/index.js`

**Endpoints**:
- `GET /health` - Service health status
- `GET /sensors` - List all motion sensors being polled
- `GET /sensor/{sensor_id}` - Get current motion detector state
- `GET /sensor/{sensor_id}/health` - Get sensor connection health stats
- `GET /errors` - Current polling errors

**Polling Behavior**:
- Polls all sensors every 5 seconds (configurable via `POLL_INTERVAL`)
- Maintains connection health statistics
- Motion detection with realistic patterns (higher during "active hours")
- Simulates network timeouts (3% probability)

**Why Node.js**: Excellent async I/O for HTTP polling, event-driven architecture

### 3. State Aggregator (Python/Flask)

**Purpose**: Coordination layer providing unified API and caching

**Location**: `services/state-aggregator/app.py`

**Endpoints**:
- `GET /health` - Aggregate health across all protocol handlers
- `GET /devices` - List all devices from all handlers
- `GET /device/{device_id}` - Get device state (with caching)
- `POST /device/{device_id}/force-refresh` - Force cache refresh
- `GET /cache/stats` - Cache statistics
- `POST /cache/clear` - Clear all cached readings
- `GET /errors` - Aggregate errors from all handlers

**Caching Strategy**:
- Default TTL: 10 seconds (configurable via `CACHE_TTL`)
- Thread-safe cache implementation using locks
- Per-device cache tracking
- Automatic cache invalidation on TTL expiration

**Design Decision**: This service is optional but recommended. It simplifies MQTT bridge logic and reduces load on protocol handlers. For simple connectors, MQTT bridge can query handlers directly.

### 4. MQTT Bridge (Python)

**Purpose**: Implements IoT2MQTT MQTT contract

**Location**: `mqtt_bridge.py`

**Responsibilities**:
- Subscribe to MQTT command topics (`devices/+/cmd`)
- Subscribe to get state requests (`devices/+/get`)
- Subscribe to meta requests (`meta/request/+`)
- Publish device states periodically (every 10 seconds default)
- Publish error notifications
- Maintain online/offline status via LWT

**MQTT Contract Compliance**:
- Uses `MQTTClient` from `shared/mqtt_client.py`
- Follows topic structure: `{BASE_TOPIC}/v1/instances/{instance_id}/...`
- Implements Last Will and Testament for status
- Publishes structured state with timestamps
- Routes commands to appropriate handlers (read-only in this example)

**Why Separate Service**: Keeps MQTT contract implementation isolated from business logic. All protocol handling is delegated to other services.

## Internal API Contracts

### Serial Handler → State Aggregator

```http
GET /sensor/{sensor_id}
Response: {
  "sensor_id": "temp_living_room",
  "type": "temperature",
  "value": 22.5,
  "unit": "°C",
  "timestamp": "2025-01-01T12:00:00",
  "quality": "good"
}

Error Response (503): {
  "error": "READ_TIMEOUT",
  "message": "Sensor did not respond",
  "timestamp": "2025-01-01T12:00:00"
}
```

### HTTP Poller → State Aggregator

```http
GET /sensor/{sensor_id}
Response: {
  "sensor_id": "motion_front_door",
  "type": "motion",
  "motion_detected": true,
  "battery_level": 95.5,
  "signal_strength": -52,
  "timestamp": "2025-01-01T12:00:00"
}
```

### State Aggregator → MQTT Bridge

```http
GET /devices
Response: {
  "devices": [
    {
      "device_id": "temp_living_room",
      "type": "temperature",
      "handler": "serial",
      "status": "online"
    }
  ],
  "count": 1
}

GET /device/{device_id}
Response: Same as handler response, plus:
  "cached": false,
  "cache_age": 2.5
```

## Configuration

Configuration is loaded from the instance JSON file mounted at `/app/instances/{instance_id}.json`.

Example instance configuration:

```json
{
  "instance_id": "sensor_hub_01",
  "connector_type": "sensor-hub",
  "update_interval": 10,
  "config": {
    "cache_ttl": 10,
    "sensors": [
      {
        "sensor_id": "temp_living_room",
        "sensor_type": "temperature",
        "friendly_name": "Living Room Temperature"
      },
      {
        "sensor_id": "motion_front_door",
        "sensor_type": "motion",
        "friendly_name": "Front Door Motion"
      }
    ]
  }
}
```

## Environment Variables

Set by `docker_service.py` when creating the container:

**Required:**
- `INSTANCE_NAME` - Instance identifier (e.g., `sensor_hub_01`)
- `CONNECTOR_TYPE` - Connector type (`sensor-hub`)
- `MQTT_HOST` - MQTT broker host
- `MQTT_PORT` - MQTT broker port (default: 1883)
- `MQTT_BASE_TOPIC` - Base MQTT topic (default: `IoT2mqtt`)

**Optional:**
- `UPDATE_INTERVAL` - State publish interval in seconds (default: 10)
- `CACHE_TTL` - Cache TTL in seconds (default: 10)
- `LOG_LEVEL` - Logging level (default: INFO)

**Internal (set by supervisord):**
- `SERVICE_PORT` - Port for each service (5001, 5002, 5003)
- `SERIAL_HANDLER_URL` - URL for serial handler API
- `HTTP_POLLER_URL` - URL for HTTP poller API
- `STATE_AGGREGATOR_URL` - URL for state aggregator API

## Process Management

All processes are managed by **supervisord** configured in `supervisord.conf`.

**Start Order** (via priority settings):
1. **Priority 100**: Serial Handler + HTTP Poller (parallel, no dependencies)
2. **Priority 200**: State Aggregator (waits 5s for handlers to be ready)
3. **Priority 300**: MQTT Bridge (waits 10s for all services)

**Restart Behavior**:
- Protocol handlers: Auto-restart immediately on failure
- State aggregator: Auto-restart with 5 retries
- MQTT bridge: Auto-restart with 5 retries (most critical)

**Log Aggregation**:
All process logs are redirected to Docker stdout/stderr for unified viewing via `docker logs`.

## Building and Testing

### Build the Container

```bash
cd /home/eduard/IoT2mqtt
docker build -t iot2mqtt_sensor-hub:latest connectors/_example-multiprocess/
```

### Run Manually for Testing

```bash
docker run --rm -it \
  --name sensor-hub-test \
  --network iot2mqtt_network \
  -e INSTANCE_NAME=test_sensor_hub \
  -e CONNECTOR_TYPE=sensor-hub \
  -e MQTT_HOST=mqtt \
  -e MQTT_PORT=1883 \
  -e MQTT_BASE_TOPIC=IoT2mqtt \
  -v /opt/iot2mqtt/shared:/app/shared:ro \
  -v /opt/iot2mqtt/.env:/app/.env:ro \
  iot2mqtt_sensor-hub:latest
```

### Test Internal APIs

Once running, from another terminal:

```bash
# Get container ID
CONTAINER_ID=$(docker ps | grep sensor-hub-test | awk '{print $1}')

# Test serial handler
docker exec $CONTAINER_ID curl -s http://localhost:5001/health
docker exec $CONTAINER_ID curl -s http://localhost:5001/sensors
docker exec $CONTAINER_ID curl -s http://localhost:5001/sensor/temp_living_room

# Test HTTP poller
docker exec $CONTAINER_ID curl -s http://localhost:5002/health
docker exec $CONTAINER_ID curl -s http://localhost:5002/sensors
docker exec $CONTAINER_ID curl -s http://localhost:5002/sensor/motion_front_door

# Test state aggregator
docker exec $CONTAINER_ID curl -s http://localhost:5003/health
docker exec $CONTAINER_ID curl -s http://localhost:5003/devices
docker exec $CONTAINER_ID curl -s http://localhost:5003/device/temp_living_room
docker exec $CONTAINER_ID curl -s http://localhost:5003/cache/stats
```

### Monitor MQTT Topics

Subscribe to see published states:

```bash
# Subscribe to all topics for this instance
mosquitto_sub -h localhost -t 'IoT2mqtt/v1/instances/test_sensor_hub/#' -v

# Subscribe to specific device states
mosquitto_sub -h localhost -t 'IoT2mqtt/v1/instances/test_sensor_hub/devices/+/state' -v

# Check instance status
mosquitto_sub -h localhost -t 'IoT2mqtt/v1/instances/test_sensor_hub/status' -v
```

### Test MQTT Commands

Send test commands (note: this example's sensors are read-only, but demonstrates routing):

```bash
# Request device state
mosquitto_pub -h localhost \
  -t 'IoT2mqtt/v1/instances/test_sensor_hub/devices/temp_living_room/get' \
  -m '{}'

# Request devices list
mosquitto_pub -h localhost \
  -t 'IoT2mqtt/v1/instances/test_sensor_hub/meta/request/devices_list' \
  -m '{}'

# Request instance info
mosquitto_pub -h localhost \
  -t 'IoT2mqtt/v1/instances/test_sensor_hub/meta/request/info' \
  -m '{}'
```

## Troubleshooting

### Services Not Starting

Check supervisord status:

```bash
docker exec $CONTAINER_ID supervisorctl status
```

Check individual service logs:

```bash
# View all logs
docker logs $CONTAINER_ID

# Filter for specific service
docker logs $CONTAINER_ID 2>&1 | grep "serial-handler"
docker logs $CONTAINER_ID 2>&1 | grep "http-poller"
```

### State Aggregator Cannot Reach Handlers

Verify handlers are responding:

```bash
docker exec $CONTAINER_ID curl http://localhost:5001/health
docker exec $CONTAINER_ID curl http://localhost:5002/health
```

Check supervisord startup timing - aggregator starts after 5s delay to allow handlers to initialize.

### MQTT Bridge Not Publishing

1. Verify MQTT connection:
```bash
docker logs $CONTAINER_ID | grep "Connected to MQTT broker"
```

2. Check state aggregator availability:
```bash
docker exec $CONTAINER_ID curl http://localhost:5003/health
```

3. Verify environment variables:
```bash
docker exec $CONTAINER_ID env | grep MQTT
```

### Cache Not Working as Expected

Check cache statistics:

```bash
docker exec $CONTAINER_ID curl http://localhost:5003/cache/stats
```

Clear cache and force refresh:

```bash
docker exec $CONTAINER_ID curl -X POST http://localhost:5003/cache/clear
```

## Customizing This Example

### Adding New Sensor Types

1. **Extend Protocol Handler** - Add new sensor type to appropriate handler
2. **Update State Aggregator** - Add routing logic for new sensor type
3. **Update MQTT Bridge** - Handle new device type in command routing
4. **Update setup.json** - Add new sensor type option

### Adding New Protocol Handler

1. **Create New Service** - Add to `services/new-handler/`
2. **Update Dockerfile** - Install dependencies for new language/libraries
3. **Update supervisord.conf** - Add process configuration with appropriate priority
4. **Update State Aggregator** - Add new handler to device routing
5. **Update Documentation** - Document new protocol and API contract

### Replacing Simulation with Real Hardware

1. **Serial Handler**: Replace simulation code with `pyserial` communication
2. **HTTP Poller**: Replace simulated polling with actual HTTP requests to sensor endpoints
3. **Error Handling**: Keep existing error handling patterns, adapt to real hardware errors

## Learning Path

1. **Start Simple**: Read `mqtt_bridge.py` to understand MQTT contract implementation
2. **Protocol Handlers**: Study `services/serial-handler/app.py` and `services/http-poller/index.js` for protocol patterns
3. **Coordination**: Examine `services/state-aggregator/app.py` for caching and aggregation patterns
4. **Process Management**: Review `supervisord.conf` for multi-process orchestration
5. **Testing**: Follow manual testing procedures to understand behavior

## Production Considerations

This example demonstrates patterns for production but uses simplifications for clarity:

**For Production Deployment:**

- Replace Flask development server with Gunicorn/uWSGI
- Replace Node.js standalone with PM2 or similar process manager
- Add structured logging with log levels and rotation
- Implement metrics collection (Prometheus exporter)
- Add authentication between services if security model requires
- Use external cache (Redis) instead of in-memory for state aggregator
- Implement circuit breakers for handler-to-handler communication
- Add distributed tracing for request flow visibility

## References

- [CONNECTOR_SPEC.md](../../docs/CONNECTOR_SPEC.md) - Complete IoT2MQTT connector specification
- [_template-multiprocess](../_template-multiprocess/) - Minimal template for starting new multi-process connectors
- [Yeelight Connector](../yeelight/) - Example of simple single-process connector using BaseConnector

## License

This example is part of the IoT2MQTT project and follows the project's license.
