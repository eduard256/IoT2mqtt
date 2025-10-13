# IoT2MQTT Connector Specification v2.0

## Executive Summary

IoT2MQTT connectors operate under a fundamental principle: maximum flexibility within containers while maintaining strict external contract compliance. This architecture enables developers to implement connectors using any programming language, any number of processes, and any level of complexity, provided they adhere to the standardized MQTT communication contract.

The single-container constraint means one instance equals one Docker container. Inside that container, developers have complete freedom. Run a simple Python script. Launch multiple processes with supervisord. Embed entire third-party applications. Combine Go binaries with Node.js services and Python coordinators. The platform imposes no restrictions on internal implementation—only on external behavior.

This specification defines the mandatory contract every connector must implement, describes optional helper utilities available to simplify development, and provides detailed guidance for creating connectors at three distinct complexity levels. Whether building a basic polling-based device connector or wrapping a complete existing IoT platform, this document serves as the authoritative reference.

## Connector Complexity Levels

### Level One: Simple Single-Process Connectors

Single-process connectors consist of one primary program running inside the container. Typically written in Python using the optional BaseConnector helper class, these connectors excel at straightforward polling-based device communication scenarios.

**When to choose Level One:**
- Devices communicate via simple request-response protocols like HTTP REST APIs
- State updates require periodic polling rather than event-driven notifications
- Device count remains manageable (typically under fifty devices per instance)
- Development team prefers Python and values rapid prototyping
- No external dependencies require separate long-running processes

**Typical examples include:**
- Smart light bulbs exposing HTTP control interfaces
- Thermostats providing JSON API endpoints
- Simple IP cameras with REST APIs for snapshot retrieval
- Network-attached sensors reporting via HTTP POST

**Advantages of Level One:**
- Fastest development time using BaseConnector helper
- Simplest debugging with single-threaded execution flow
- Lowest resource consumption per container
- Straightforward error handling and recovery
- Direct mapping between code and container behavior

**Limitations of Level One:**
- Inefficient for event-driven architectures requiring persistent connections
- Cannot leverage performance benefits of compiled languages for compute-intensive tasks
- Single point of failure—if main process crashes, entire connector stops
- Difficult to integrate existing libraries or tools written in other languages
- Thread-based concurrency in Python limited by Global Interpreter Lock

### Level Two: Multi-Process Single-Container Connectors

Multi-process connectors run several independent programs inside one container, coordinated by a process supervisor like supervisord. Each process serves a specific purpose: stream handling, event processing, computation, coordination.

**When to choose Level Two:**
- Application requires multiple programming languages for different components
- Some tasks benefit from compiled language performance while others need Python flexibility
- Long-running connections to external services must coexist with MQTT coordination
- Separation of concerns improves maintainability and testing
- Resource-intensive operations should run in separate processes to avoid blocking

**Typical examples include:**
- Camera systems combining RTSP stream handling (Go), motion detection (Node.js), object recognition (Python), and MQTT coordination (Python)
- Audio processing connectors using compiled audio codecs, real-time analysis services, and control logic
- Protocol bridges running third-party protocol implementations alongside translation layers
- Performance-critical connectors offloading computation to optimized binaries

**Advantages of Level Two:**
- Leverage language-specific strengths—Go for concurrency, Python for integration, Node.js for async I/O
- Process isolation improves fault tolerance—individual process crashes don't terminate entire container
- Independent process scaling—allocate resources appropriately to compute-heavy versus control-flow components
- True parallel execution across CPU cores without Global Interpreter Lock constraints
- Easier integration of existing tools and libraries regardless of implementation language

**Limitations of Level Two:**
- Increased complexity in process coordination and inter-process communication
- More difficult debugging requiring analysis of multiple concurrent process logs
- Higher resource overhead from multiple runtime environments
- Potential race conditions in shared resource access via localhost services
- Additional supervisord configuration and management overhead

### Level Three: Wrapper Connectors Embedding Third-Party Applications

Wrapper connectors embed complete external applications inside the container, adding a translation layer that converts between the external application's protocols and IoT2MQTT's standardized MQTT contract.

**When to choose Level Three:**
- Mature open-source projects already solve your device communication needs
- Rebuilding existing functionality provides no additional value
- Upstream project maintains active development and bug fixes
- Device support expands as upstream project adds compatibility
- Connector serves as integration glue rather than primary implementation

**Typical examples include:**
- Zigbee2MQTT wrapper providing Zigbee device support through MQTT topic translation
- Home Assistant wrapper enabling access to hundreds of supported integrations
- ESPHome wrapper connecting ESP8266/ESP32 devices via its native API
- Node-RED wrapper exposing flows as IoT2MQTT device abstractions

**Advantages of Level Three:**
- Immediate access to extensive device support from mature projects
- Upstream bug fixes and security updates benefit your connector automatically
- Community-driven device compatibility additions require no connector changes
- Reduced maintenance burden—focus on translation layer not device protocols
- Proven stability from battle-tested upstream implementations

**Limitations of Level Three:**
- Larger container images from embedded complete applications
- Dependency on upstream project stability and API compatibility
- Limited control over embedded application behavior and performance
- Double-hop latency through translation layer for time-sensitive operations
- Potential licensing complications requiring careful compliance review

### Decision Tree for Complexity Selection

**Start with these questions:**

Can you implement device communication in Python with simple polling? Choose Level One using BaseConnector.

Do you need multiple programming languages or long-running background services? Choose Level Two with supervisord coordination.

Does an existing open-source project already provide device communication? Choose Level Three wrapper pattern.

**Secondary considerations:**

If performance-critical operations exist in Level One connector, consider Level Two to offload computation to compiled binaries.

If Level Two coordination complexity becomes unwieldy, evaluate whether existing projects (Level Three) solve the same problem.

If Level Three upstream project lacks required functionality, consider Level Two custom implementation instead.

## Mandatory Contract Elements

Every connector, regardless of internal implementation, must satisfy these contract requirements to function properly within the IoT2MQTT ecosystem.

### Environment Variables Contract

Connectors receive environment variables from two sources: the root environment file and the container creation process.

**From root .env file mounted at /app/.env:**

MQTT_HOST specifies the MQTT broker hostname or IP address. Connectors must use this value for establishing broker connections.

MQTT_PORT specifies the MQTT broker TCP port number, typically 1883 for unencrypted connections or 8883 for TLS.

MQTT_USERNAME provides authentication credentials for brokers requiring username-password authentication. May be empty for anonymous access.

MQTT_PASSWORD provides authentication credentials paired with MQTT_USERNAME. May be empty for anonymous access.

MQTT_BASE_TOPIC defines the root topic prefix for all MQTT communications. Connectors must prepend this to all topic paths.

MQTT_CLIENT_PREFIX defines the client ID prefix used when connecting to the broker. Connectors should append instance identifiers to ensure unique client IDs.

MQTT_QOS specifies the default Quality of Service level for message publishing, typically 0, 1, or 2.

MQTT_RETAIN indicates whether state messages should use the MQTT retain flag, typically "true" or "false".

MQTT_KEEPALIVE specifies the keepalive interval in seconds for maintaining broker connections.

LOG_LEVEL controls logging verbosity, accepting values like DEBUG, INFO, WARNING, ERROR, CRITICAL.

TZ specifies the timezone for timestamp generation, using standard timezone database names.

**Injected by docker_service during container creation:**

INSTANCE_NAME contains the unique identifier for this specific connector instance. This value serves as the instance_id in all MQTT topic paths.

MODE indicates operational mode, either "production" for deployed instances or "development" for testing scenarios with features like hot reload.

PYTHONUNBUFFERED disables Python output buffering when set to "1", ensuring logs appear immediately rather than being buffered.

IOT2MQTT_PATH specifies the base application path inside the container, typically "/app".

**Accessing environment variables:**

Python connectors using BaseConnector automatically load the .env file via the python-dotenv library. The MQTTClient class reads MQTT configuration directly from environment variables.

Custom connectors in other languages must read environment variables using language-native mechanisms. Go programs use os.Getenv, Node.js uses process.env, shell scripts use standard variable syntax.

Configuration values from the instance JSON file at /app/instances/{instance_id}.json supplement environment variables but never replace mandatory contract variables.

### MQTT Topics Contract

All MQTT communication follows standardized topic patterns. The BASE_TOPIC variable from environment prepends all topics.

**Inbound topics that connectors must subscribe to:**

The devices command topic follows the pattern {BASE_TOPIC}/v1/instances/{instance_id}/devices/{device_id}/cmd. Messages contain command payloads as JSON objects. Connectors receive these messages and execute requested device actions.

The payload structure includes an optional id field containing a unique command identifier for response tracking. An optional timestamp field contains ISO 8601 formatted timestamps for command ordering. The values field contains the actual command parameters as a JSON object. An optional timeout field specifies maximum execution time in milliseconds.

The devices get topic follows the pattern {BASE_TOPIC}/v1/instances/{instance_id}/devices/{device_id}/get. Messages request current device state. Connectors respond by publishing current state to the state topic.

The payload structure includes an optional properties field listing specific properties to return. If omitted, connectors should return complete device state.

The groups command topic follows the pattern {BASE_TOPIC}/v1/instances/{instance_id}/groups/{group_id}/cmd. Messages contain commands targeting all devices in the specified group. Connectors iterate through group members executing the command for each.

The meta request topic follows the pattern {BASE_TOPIC}/v1/instances/{instance_id}/meta/request/+. The wildcard segment specifies the request type. Connectors handle requests like devices_list to return available devices or info to return instance metadata.

**Outbound topics that connectors must publish to:**

The status topic follows the pattern {BASE_TOPIC}/v1/instances/{instance_id}/status. Connectors publish "online" when starting successfully and configure Last Will and Testament to publish "offline" on unexpected disconnection. This topic must use QoS 1 and retain flag for reliable status indication.

The Last Will and Testament configuration happens during MQTT client initialization. Set the LWT topic to the status topic path, payload to "offline", QoS to 1, and retain to true. Publish "online" immediately after successful connection with QoS 1 and retain true.

The device state topic follows the pattern {BASE_TOPIC}/v1/instances/{instance_id}/devices/{device_id}/state. Connectors publish device state updates as JSON objects containing current property values. Include timestamp field with ISO 8601 formatted current time and device_id field identifying the device.

State messages typically use retain flag so late-joining subscribers receive last known state. QoS level should match the MQTT_QOS environment variable default.

The device error topic follows the pattern {BASE_TOPIC}/v1/instances/{instance_id}/devices/{device_id}/error. Connectors publish error notifications when device operations fail. Include timestamp field, error_code identifying the error type, message providing human-readable description, and severity indicating impact level (info, warning, error, critical).

The optional device events topic follows the pattern {BASE_TOPIC}/v1/instances/{instance_id}/devices/{device_id}/events. Connectors publish discrete events like motion detection or button presses that don't represent state changes. Event messages should not use retain flag since events are time-bound occurrences.

The devices list response topic follows the pattern {BASE_TOPIC}/v1/instances/{instance_id}/meta/devices_list. Connectors publish arrays of device information in response to meta request messages. Each device entry includes device_id, global_id combining instance and device identifiers, model information, enabled status, and online status.

Individual property topics following the pattern {BASE_TOPIC}/v1/instances/{instance_id}/devices/{device_id}/state/{property_name} allow selective subscriptions to specific device properties. These topics are optional but improve efficiency for subscribers interested in single values rather than complete state objects.

### Configuration File Access

Every connector instance has an associated configuration file in JSON format. On the host system, files exist at instances/{connector_type}/{instance_id}.json. During container creation, the system mounts the connector-specific directory into the container, making configurations appear at /app/instances/{instance_id}.json from the container perspective.

**Configuration file structure:**

The instance_id field contains the unique identifier matching INSTANCE_NAME environment variable.

The connector_type field specifies which connector implementation this instance uses.

The friendly_name field provides a human-readable label for this instance.

The enabled field indicates whether this instance should actively run, typically boolean true or false.

The update_interval field specifies polling frequency in seconds for polling-based connectors.

The devices array contains device-specific configurations. Each device entry includes device_id unique within this instance, IP addresses or connection details in connection-specific fields, device model information, friendly names, and enabled flags.

The groups array contains group definitions for collective device operations. Each group entry includes group_id and a devices array listing member device_ids.

Additional connector-specific configuration fields may exist based on connector requirements. Connectors define their own schema for these additional fields.

**Loading configuration files:**

BaseConnector automatically loads the configuration file using the INSTANCE_NAME environment variable to construct the path /app/instances/{instance_name}.json.

Custom connectors must load the file manually. Read the INSTANCE_NAME environment variable, construct the path /app/instances/{instance_name}.json, open and parse the JSON file, extract required configuration values.

Configuration validation should happen during connector startup. Verify required fields exist, validate field value ranges and types, check device connectivity if applicable, log warnings for missing optional fields.

Configuration changes require container restart. The system does not support hot-reloading of configuration files. When users modify instance configuration through the web interface, the system restarts the container to apply changes.

### Health Checks and Status Reporting

Docker health checks enable the container orchestration system to monitor connector operational status. Define health checks in the connector Dockerfile using the HEALTHCHECK instruction.

**Implementing health checks:**

Simple connectors verify the main process remains running. Check that required ports bind successfully if the connector exposes ports. Verify critical internal state indicates operational readiness.

Multi-process connectors should verify all critical processes remain alive. Query supervisord status endpoints to enumerate process states. Check that inter-process communication channels remain open. Verify no processes have entered restart loops.

Wrapper connectors must verify both the wrapped application and translation layer function correctly. Query the wrapped application's health or status endpoints. Verify the translation layer maintains MQTT connectivity. Check that message flow occurs between wrapped application and MQTT.

**Health check timing considerations:**

Set interval to determine how frequently Docker executes the health check. Typical values range from thirty seconds to several minutes depending on startup time and resource sensitivity.

Set timeout to specify maximum execution time for the health check command. Should be shorter than the interval to prevent overlapping checks.

Set start_period to allow time for initialization before marking failures as unhealthy. Critical for connectors with long startup sequences or dependency warming.

Set retries to specify how many consecutive failures constitute unhealthy status. Prevents transient network issues from triggering unnecessary restarts.

**Status topic as health indicator:**

The MQTT status topic provides application-level health indication separate from container health. Publish "online" only after completing all initialization including device connections and internal service startup.

Configure Last Will and Testament before establishing the connection so unexpected disconnections immediately publish "offline" status. This provides faster failure detection than Docker health checks alone for network connectivity issues.

Periodically verify MQTT connection remains active even when no messages require publishing. Some MQTT clients provide ping or keepalive mechanisms that detect silent connection failures.

## Optional BaseConnector Helper Class

The BaseConnector class located in shared/base_connector.py provides convenience functionality for simple Python connectors. Using BaseConnector is entirely optional—connectors may implement the MQTT contract directly without this helper.

### When to Use BaseConnector

BaseConnector suits connectors with these characteristics: implemented in Python, poll devices periodically for state updates, communicate with devices over standard protocols like HTTP or TCP, handle relatively small device counts, require straightforward command processing without complex asynchronous operations.

**Advantages of using BaseConnector:**

Configuration loading handles JSON parsing and path resolution automatically using INSTANCE_NAME environment variable.

MQTT client initialization configures connection parameters from environment variables, establishes connection with retry logic, sets up Last Will and Testament for status reporting.

Subscription management automatically subscribes to devices command topics, devices get topics, groups command topics, meta request topics with appropriate wildcards.

Message routing dispatches incoming MQTT messages to appropriate handler methods based on topic patterns.

Polling loop executes periodic device updates at configurable intervals, catches and logs exceptions to prevent crash loops, publishes state updates automatically, implements error counting with automatic shutdown on persistent failures.

State publishing wraps MQTTClient methods with timestamp injection and error handling.

### When to Implement Contract Directly

Avoid BaseConnector for connectors with these requirements: event-driven architecture receiving device-initiated notifications, websocket or long-lived connection management, complex asynchronous operations, multiple concurrent device operations, languages other than Python, custom MQTT quality of service or retention policies.

Implement the contract directly using the MQTTClient class from shared/mqtt_client.py. This class handles MQTT connectivity and message formatting without imposing the polling loop architecture that BaseConnector provides.

### BaseConnector Abstract Methods

Subclasses must implement these abstract methods to create a functioning connector.

**initialize_connection method:**

Called once during connector startup after MQTT connection establishes but before the polling loop begins. Use this method to establish connections to devices or external services, validate configuration parameters, perform device discovery if applicable, initialize internal state and caches, verify external service availability.

Raise exceptions for unrecoverable initialization failures. BaseConnector catches these exceptions, logs error messages, and terminates the connector cleanly.

**cleanup_connection method:**

Called once during connector shutdown after the polling loop stops but before MQTT disconnection. Use this method to close device connections gracefully, flush any pending operations, release external resources, save state if persistence is required, stop background threads or processes.

BaseConnector calls this method even if errors occurred during operation, so implement defensively to handle partial initialization states.

**get_device_state method:**

Called once per device per polling interval to retrieve current device state. Receives device_id string identifying the device and device_config dictionary containing device-specific configuration from the instance JSON file.

Return a dictionary containing current device state with keys representing properties and values containing current values. Include boolean online field indicating reachability. Include string or datetime last_update field indicating when state was retrieved.

Return None if the device is unreachable or state retrieval fails. BaseConnector logs warnings for None returns but continues polling other devices.

Implement appropriate timeout values to prevent one slow device from blocking updates for all devices. Catch device-specific exceptions and return None rather than allowing exceptions to propagate.

**set_device_state method:**

Called when command messages arrive requesting device state changes. Receives device_id string identifying the target device, device_config dictionary containing device-specific configuration, and state dictionary containing the requested changes.

Return boolean True if the command executed successfully. Return boolean False if the command failed but the connector should continue operating.

Raise exceptions only for catastrophic failures requiring connector shutdown. BaseConnector catches exceptions, publishes error messages, and continues operation unless critical errors exceed threshold.

Apply commands to the device using appropriate device protocols. Validate command values before transmission. Handle device-specific errors with appropriate recovery mechanisms. Consider implementing command queuing for rate-limited devices.

### BaseConnector Configuration Access

The config attribute contains the complete parsed instance JSON configuration. Access configuration values using dictionary syntax like self.config.get('update_interval', 10) with defaults for optional fields.

The instance_id attribute contains the unique instance identifier from the configuration file. Use this when constructing log messages or internal identifiers.

The mqtt attribute provides access to the MQTTClient instance for advanced operations. Call mqtt.publish for custom topic publications. Call mqtt.subscribe for additional topic subscriptions beyond default patterns. Access mqtt.connected to check connection status.

### BaseConnector Protected Methods

The _load_config method handles configuration file loading and parsing. Constructs the path /app/instances/{instance_name}.json using INSTANCE_NAME environment variable. Opens and parses the JSON file with error handling. Calls _load_secrets to inject sensitive values from Docker secrets. Returns the complete configuration dictionary.

Override this method only if alternative configuration sources are required. Always call the parent implementation via super()._load_config() when overriding.

The _load_secrets method integrates Docker secrets into configuration. Checks for instance-specific secrets at /run/secrets/{instance_name}_creds. Parses key-value pairs from secrets file. Injects values into config dictionary under appropriate keys.

The _setup_logging method configures Python logging module. Reads LOG_LEVEL environment variable. Configures basicConfig with appropriate format and level.

Override to customize logging configuration, such as adding handlers for external logging services or implementing structured logging.

The _main_loop method implements the polling loop. Iterates through configured devices at update_interval frequency. Calls get_device_state for each enabled device. Publishes state updates via MQTT. Handles exceptions with error counting. Sleeps between iterations using time.sleep.

Override if custom polling behavior is required, but consider whether implementing the contract directly might be clearer.

The _handle_command method processes device command messages. Parses command topics to extract device_id. Validates command timestamps to prevent processing stale commands. Looks up device configuration from the config devices array. Calls set_device_state with parsed command values. Publishes response messages if command includes id field for tracking.

The _handle_get method processes device get request messages. Extracts device_id from topic. Retrieves current state from internal cache if available. Calls get_device_state if cached state is unavailable. Filters returned state to requested properties if specified. Publishes filtered state to device state topic.

The _handle_group_command method processes group command messages. Extracts group_id from topic. Looks up group configuration from config groups array. Iterates through group member device_ids. Calls set_device_state for each enabled device in the group with the command values.

The _handle_meta_request method processes metadata request messages. Handles devices_list requests by iterating through configured devices and publishing array of device information. Handles info requests by publishing instance metadata like connector type and device counts.

### BaseConnector Lifecycle

The start method initiates connector operation. Connects to MQTT broker with retry logic. Sets up topic subscriptions using _setup_subscriptions. Calls initialize_connection for connector-specific initialization. Starts the polling loop in a daemon thread. Publishes "online" status. Returns boolean indicating startup success.

The stop method terminates connector operation. Sets running flag to false to signal loop termination. Waits for polling thread to complete with timeout. Calls cleanup_connection for connector-specific cleanup. Disconnects from MQTT broker. Publishes "offline" status via Last Will and Testament.

The run_forever method combines start with indefinite execution. Calls start method. Enters sleep loop until KeyboardInterrupt. Catches interrupt signals and calls stop for graceful shutdown. Suitable for use as the main entry point in connector scripts.

## Multi-Process Container Implementation

Multi-process connectors run several independent programs within one container, requiring process management, coordination, and lifecycle handling.

### Process Manager Selection

Supervisord provides robust process management with extensive configuration options, automatic process restarts, logging aggregation, and optional web interface for monitoring. Installation requires adding python-supervisor package to the container image. Configuration uses INI-format files defining programs and their execution parameters.

Custom Python supervisor scripts offer complete control over process lifecycle and coordination logic. Implement using subprocess module for process launching and monitoring. Handle signals explicitly for graceful shutdown. Suitable when supervisord configuration becomes too complex or when tight integration with connector logic is required.

Shell script process managers provide simplest implementation for straightforward multi-process scenarios. Launch processes in background using ampersand syntax. Capture process IDs for later signal delivery. Implement signal traps for SIGTERM and SIGINT handling. Best for containers with two or three simple processes without complex dependencies.

### Supervisord Configuration

Install supervisord in the Dockerfile by including python-supervisor or supervisor packages depending on the base image. Copy supervisord configuration files into appropriate locations. Expose supervisord web interface port if monitoring is desired.

Create the main configuration file at /etc/supervisor/conf.d/supervisord.conf. Begin with the supervisord section setting nodaemon to true for foreground execution, logfile path for supervisor logs, pidfile path for process ID storage.

Add program sections for each process. Specify command with full path to executable and arguments. Set autostart true to launch process during supervisor startup. Set autorestart true to restart process after unexpected termination. Configure stdout_logfile to /dev/stdout with maxbytes zero for container-friendly logging. Configure stderr_logfile to /dev/stderr with maxbytes zero. Set priority values to control startup order when dependencies exist. Include environment variables using the environment key with comma-separated name=value pairs.

Add a group section to manage related processes collectively. List member program names in the programs key. Groups enable operations like restarting all processes simultaneously.

**Process dependencies and startup order:**

Use priority values to sequence process startup. Lower priority numbers start first. Assign priority values with gaps to allow insertion of additional processes later. Typical sequence launches infrastructure processes first with priorities like 100, then application processes with priorities like 500, then coordination processes with priorities like 900.

Implement health checking using the startsecs parameter to specify how long a process must run before considering startup successful. Processes crashing before startsecs elapses trigger restart logic immediately.

Handle slow-starting dependencies using sleep delays or explicit health checks. If process B depends on process A's readiness, either include startup delays in process B's command, or implement health check loops that wait for process A's listening port or health endpoint.

### Inter-Process Communication

Processes within a container communicate via localhost network interfaces since they share the container's network namespace. Launch services binding to localhost addresses. Configure clients to connect to localhost with appropriate ports. Use port numbers above 1024 to avoid requiring root privileges.

HTTP REST APIs provide simple inter-process communication. Launch Node.js Express servers, Python Flask applications, or Go HTTP servers on localhost ports. Other processes make HTTP requests using standard client libraries. Suitable for request-response patterns and state queries.

Unix domain sockets offer better performance than TCP for high-volume inter-process communication. Create sockets in shared paths like /tmp/process.sock. Ensure appropriate file permissions for socket access. Suitable for high-frequency communication or large data transfers.

Message queues like Redis or RabbitMQ add complexity but provide reliable asynchronous communication. Embed lightweight message brokers in the container if needed. Configure processes as producers and consumers. Consider whether external MQTT broker could serve this role instead.

Shared memory via files provides simplest state sharing. Write JSON state files to /tmp or other shared paths. Implement file locking to prevent concurrent access issues. Suitable for infrequent state updates or configuration sharing.

### Logging in Multi-Process Containers

Configure all processes to write logs to stdout and stderr. Supervisord captures this output when stdout_logfile and stderr_logfile point to /dev/stdout and /dev/stderr respectively. Docker aggregates these streams into the container log.

Include process identifiers in log lines to distinguish output sources. Prefix log messages with process name or service identifier. Use structured logging formats like JSON for machine parsing. Include timestamps in log entries for accurate sequencing.

Set supervisord's stdout_logfile_maxbytes and stderr_logfile_maxbytes to zero to disable supervisord's log rotation. Let Docker handle log rotation using container logging drivers.

Consider implementing log levels consistently across processes. Use environment variables to configure log verbosity. Ensure DEBUG level logging doesn't overwhelm log aggregation systems.

### Graceful Shutdown Handling

Supervisord propagates SIGTERM signals to managed processes when the container stops. Configure programs to handle SIGTERM by shutting down gracefully. Set stopwaitsecs to appropriate values allowing time for cleanup. Supervisord sends SIGKILL after stopwaitsecs expires if process hasn't terminated.

Implement signal handlers in process code. Python uses signal module to register handlers. Node.js uses process.on for signal events. Go uses signal.Notify channel. Shell scripts use trap command.

Shutdown order matters when processes have dependencies. Stop processes in reverse priority order by assigning higher priority values to infrastructure processes. Alternatively, use supervisord's group stop commands to control shutdown sequence explicitly.

Ensure MQTT bridge process publishes "offline" status before termination. Implement signal handlers that disconnect MQTT cleanly. Configure supervisord stopwaitsecs to allow time for MQTT disconnect and Last Will and Testament delivery.

Flush pending operations during shutdown. Write cached state to persistent storage. Close database connections. Cancel pending HTTP requests. Release file locks.

### Resource Management in Multi-Process Containers

Monitor memory usage across all processes. Allocate container memory limits accounting for all processes plus overhead. Use Docker memory constraints to prevent host system impact from runaway processes.

Configure process-specific memory limits if supervisord supports them, though Docker-level limits are typically sufficient. Profile memory usage during testing to establish appropriate limits.

CPU allocation affects process scheduling. Set Docker CPU limits if multiple containers compete for resources. Within the container, processes share available CPU based on operating system scheduling unless cgroups provide process-level constraints.

Disk I/O patterns matter for containers with multiple processes writing logs or state files. Use memory-backed temporary filesystems for high-frequency writes. Write persistent state to mounted volumes. Avoid excessive disk I/O that could impact other containers on the host.

## Wrapper Pattern for Third-Party Applications

Wrapper connectors embed complete external applications inside the container, adding translation layers to bridge protocols and data formats.

### Including External Applications

Add external applications to the container using several approaches depending on the application's distribution method and update requirements.

**Git submodules for source-based applications:**

Initialize git submodules in the connector directory pointing to upstream repositories. Clone submodules during Docker image build. Build the external application from source as part of the Dockerfile. Pin submodule commits to specific releases for stability. Update submodules deliberately when upgrading to newer versions.

**Package manager installation:**

Install external applications using apt, apk, yum, or other package managers in the Dockerfile. Pin package versions explicitly to prevent unexpected updates. Add required package repositories if applications aren't in base repositories. Clean package manager caches after installation to minimize image size.

**Binary downloads:**

Download pre-built binaries during Docker build using curl or wget. Verify download integrity using checksums or GPG signatures. Extract archives into appropriate installation paths. Set executable permissions on binary files. Remove download artifacts after extraction to minimize image size.

**Docker multi-stage builds for optimization:**

Use builder stages to compile external applications or process large files. Copy only runtime artifacts into final image stage. Exclude development dependencies and build tools from final image. Produces smaller, more secure final images with reduced attack surface.

### MQTT Translation Layer Pattern

Translation layers convert between external application MQTT topics and IoT2MQTT standardized topics. Run translation processes alongside the external application, subscribing to both topic namespaces and republishing messages in the target format.

**Translation layer architecture:**

Subscribe to external application's MQTT topics using wildcards matching its topic structure. Parse incoming messages extracting relevant state or event information. Transform data formats and structures into IoT2MQTT schemas. Publish transformed messages to IoT2MQTT topics following the mandatory contract.

Subscribe to IoT2MQTT command topics. Parse incoming commands extracting operation parameters. Transform commands into external application's format and structure. Publish transformed commands to external application's topics.

Maintain state mappings between external identifiers and IoT2MQTT device IDs. Handle identifier translation in both directions. Store mappings in memory or persistent storage depending on stability requirements.

**Bidirectional translation example:**

External applications like Zigbee2MQTT publish device state to topics like zigbee2mqtt/device_name. Translation layer subscribes to zigbee2mqtt/# wildcard. Extracts device_name from topic. Maps device_name to IoT2MQTT device_id. Transforms state payload from Zigbee2MQTT format to IoT2MQTT format. Publishes to IoT2MQTT/v1/instances/instance_id/devices/device_id/state.

IoT2MQTT publishes commands to topics like IoT2MQTT/v1/instances/instance_id/devices/device_id/cmd. Translation layer subscribes to this pattern. Maps device_id to Zigbee2MQTT device_name. Transforms command payload from IoT2MQTT format to Zigbee2MQTT format. Publishes to zigbee2mqtt/device_name/set.

**Error handling in translation:**

Invalid or malformed messages from external application should be logged but not crash the translation layer. Unknown device identifiers should trigger warnings but allow translation to continue for known devices. Failed transformations should publish error messages to IoT2MQTT error topics. Translation layer should implement reconnection logic if MQTT connections drop.

### Configuration Integration

External applications typically read configuration files from specific paths. Mount or copy configuration files into expected locations during container startup. Generate configuration files from instance JSON if dynamic configuration is required. Template configuration files using environment variable substitution.

**Configuration file generation:**

Read instance JSON configuration at container startup. Extract external-application-specific settings. Generate configuration files using templates or programmatic construction. Write configuration files to paths expected by external application. Ensure file permissions allow external application to read configuration.

**Environment variable injection:**

External applications may read configuration from environment variables. Set additional environment variables in supervisord program sections. Derive environment values from instance JSON configuration. Pass through relevant IoT2MQTT environment variables if external application supports similar patterns.

### Monitoring Wrapped Application Health

Wrapper connectors must verify both the wrapped application and translation layer function correctly before reporting online status.

Query wrapped application health endpoints if available. Many applications provide HTTP health check endpoints. Poll these endpoints during startup and periodically during operation. Report unhealthy if wrapped application health checks fail.

Verify translation layer maintains MQTT subscriptions. Implement subscription acknowledgment tracking. Monitor message flow to detect silent failures. Report unhealthy if subscriptions drop without reconnection.

Check inter-process communication channels remain open. Verify shared resources like Unix sockets or HTTP ports remain accessible. Report unhealthy if communication channels fail.

Implement composite health checks combining multiple indicators. Require all components report healthy before marking container healthy. Use appropriate health check timing to accommodate slow-starting wrapped applications.

## Setup Phase Integration

The setup phase occurs when users create new connector instances through the web interface. This phase executes connector-specific scripts that validate configurations, test connectivity, and discover devices before the runtime container launches.

### Actions Directory Structure

Connector setup scripts reside in the actions subdirectory within each connector directory. Each script handles one specific setup task like device discovery, connection validation, or credential testing. Scripts execute in the test-runner container which provides a clean Python environment with common libraries installed.

Place scripts with descriptive names reflecting their purpose. Use discover.py for device discovery operations. Use validate.py for connection testing. Use authenticate.py for credential validation. Make scripts executable with appropriate shebang lines.

### Setup.json Tool Declarations

The setup.json file declares available tools using the tools object. Each tool entry specifies the script entry point, timeout duration, and optional parameters.

Tools contain the entry field pointing to the script path relative to the connector directory like actions/discover.py. The timeout field specifies maximum execution time in seconds, typically five to thirty seconds depending on operation complexity. The network field indicates whether the tool requires network access.

Optional secrets field lists parameter names containing sensitive information that should be masked in logs. Optional description field provides human-readable tool explanation for documentation.

Web interface setup flows reference tools by their key names. When users progress through setup steps, the web interface invokes tools by posting to the test-runner API endpoint with tool name and input parameters.

### Action Script Input Contract

Action scripts receive input through stdin as JSON formatted data. The test-runner invokes scripts using subprocess with input JSON piped to stdin. Scripts must read stdin, parse JSON, extract input parameters, and execute appropriate operations.

Input JSON structure contains tool field with the tool name and input field containing parameters specific to this invocation. Parameter names and types match the form fields defined in the setup.json schema.

Scripts access parameters by parsing the input object. Extract expected parameters with appropriate defaults for optional values. Validate parameter types and value ranges. Return errors for invalid or missing required parameters.

### Action Script Output Contract

Action scripts write output to stdout as JSON formatted data. The test-runner captures stdout and returns it to the web interface. Scripts must produce valid JSON as their final stdout content. Any debugging or logging output should go to stderr, not stdout.

Output JSON structure contains ok field with boolean value indicating success or failure. For successful executions, include result field containing operation results as an object or array. For failed executions, include error field containing error details.

Error objects contain code field with machine-readable error identifier like connection_failed or invalid_credentials. Include message field with human-readable error description. Include retriable field with boolean indicating whether retrying might succeed after user intervention.

Result objects structure depends on the tool purpose. Discovery tools return arrays of discovered devices with device identifiers, model information, and connection details. Validation tools return connection status and device properties. Authentication tools return session tokens or capability information.

### Discovery Script Patterns

Discovery scripts scan networks or enumerate available devices. Use connector-specific discovery protocols appropriate for the device type. Common patterns include network scanning for IP devices, Bluetooth scanning for BLE devices, and API queries for cloud-connected devices.

Implement appropriate timeouts to prevent indefinite script execution. Network scans should timeout after specified duration. API queries should implement retry logic with backoff. Return partial results if discovery completes partially within timeout.

Return discovered devices as arrays with consistent structure. Include device_id or suggested identifier. Include ip or connection address. Include model or device type information. Include capabilities or supported features. Include properties reflecting current device state if available.

Handle discovery failures gracefully. Return empty arrays rather than errors if no devices found. Log detailed error information to stderr for debugging. Return errors only for catastrophic failures preventing discovery execution.

### Validation Script Patterns

Validation scripts verify connectivity to specific devices or services. Accept connection parameters like IP address and port from input. Attempt connection using appropriate protocols. Return success with device information or failure with diagnostic details.

Implement connection timeouts appropriate for the protocol. TCP connections typically timeout within five seconds. HTTP requests timeout within ten seconds. Longer timeouts may be appropriate for slow networks or initialization delays.

Return detailed error information for failures. Include network error codes or exception messages. Suggest remediation steps when possible. Distinguish between network failures, authentication failures, and protocol incompatibilities.

Return device properties when validation succeeds. Include firmware version, model information, and capability flags. This information helps users verify correct device identification. Properties inform subsequent configuration steps.

### Test-Runner Execution Environment

The test-runner container runs Ubuntu Linux with Python three point eleven and common networking utilities. Connectors requiring specific Python libraries should list dependencies in requirements.txt. The test-runner installs these libraries automatically if present in the connector directory.

Scripts execute with /app/connectors/{connector_name} as working directory. Reference other connector files using relative paths. Access configuration templates or data files from the connector directory.

No persistent state exists between script executions. Each invocation runs in a fresh subprocess. Scripts requiring multiple steps must be designed as independent operations or implement external state storage.

Network access is available from the test-runner container. Scripts can connect to devices on the local network. Outbound internet access supports cloud API operations. The test-runner shares the Docker host network when network mode is host.

Environment variables from the .env file are not automatically available to action scripts. Scripts requiring MQTT broker information or other global settings must receive these through input parameters passed from the web interface.

### Timeout and Error Handling

The test-runner enforces timeout limits specified in setup.json tool declarations. Scripts exceeding timeouts receive SIGTERM signals. Scripts should handle signals gracefully but test-runner sends SIGKILL after additional grace period if necessary.

Return timeout errors in the standard error format with code "timeout" and retriable true. The web interface displays timeout errors with options to retry with longer timeout values.

Implement internal timeouts within scripts to provide better error messages. Catch timeout exceptions from libraries. Return descriptive timeout errors rather than letting test-runner timeout handling trigger.

Handle all exceptions within scripts. Use try-except blocks around operations that might fail. Convert exceptions to error output JSON rather than allowing uncaught exceptions. Log exception details to stderr for debugging while returning user-friendly messages to stdout.

## Docker Best Practices

Effective container design improves performance, security, and maintainability.

### Multi-Stage Builds

Multi-stage builds separate build-time dependencies from runtime artifacts, producing smaller final images with reduced attack surface.

Begin with a builder stage using a comprehensive base image containing compilers and development tools. Install build dependencies. Copy source code. Execute compilation or build processes. Generate build artifacts.

Follow with a runtime stage using a minimal base image containing only runtime dependencies. Copy artifacts from builder stage using COPY from directive. Install runtime dependencies only. Set up runtime configuration and users.

Benefits include significantly smaller image sizes since build tools excluded from final image, faster deployment from smaller image downloads, reduced security exposure from fewer installed packages, cleaner separation between build and runtime concerns.

### Security Considerations

Run processes as non-root users when possible. Create dedicated users in Dockerfile using RUN useradd. Switch to non-root user using USER directive before CMD or ENTRYPOINT. Configure supervisord to run processes as specific users.

Some connectors require root privileges for network operations or device access. Document why root access is necessary. Consider capabilities-based restrictions instead of full root access. Minimize the scope of operations requiring elevated privileges.

Avoid including sensitive information in images. Never hardcode credentials in Dockerfiles or source code. Use environment variables and Docker secrets for sensitive data. Include .dockerignore file excluding sensitive files from build context.

Pin base image versions explicitly using full tags with digests. Avoid latest tags that change unpredictably. Update base images deliberately after testing. Scan images for vulnerabilities using tools like Trivy.

### Volume Mounting Patterns

Connectors receive mounted volumes for configuration and shared libraries. Understand mount points and access patterns.

Configuration directory mounts at /app/instances containing instance-specific JSON files. Mount is read-only preventing containers from modifying configuration. Read configuration during startup and cache values rather than repeatedly accessing files.

Shared libraries mount at /app/shared containing common Python modules like base_connector.py and mqtt_client.py. Mount is read-only ensuring consistency across connector instances. Import shared modules using sys.path manipulation if necessary.

Root .env file mounts at /app/.env containing environment variables. Mount is read-only preventing modification. Load file using libraries like python-dotenv or parse manually for other languages.

Some connectors may require persistent storage for caching or state. Define additional volumes in the container configuration. Mount volumes at paths outside /app to avoid conflicts. Implement appropriate file locking for concurrent access scenarios.

### Health Check Implementation

Define health checks in Dockerfile using HEALTHCHECK instruction. Specify interval, timeout, start period, and retry count appropriate for the connector's characteristics.

Implement health check commands that verify critical functionality. For simple connectors, check that main process responds to simple queries. For multi-process connectors, verify all critical processes remain running. For wrapper connectors, verify both wrapped application and translation layer function.

Use lightweight health check commands that execute quickly. Avoid expensive operations like complete device scans. Check local process status or localhost HTTP endpoints. Implement dedicated health check endpoints if necessary.

Return exit code zero for healthy status. Return non-zero exit codes for unhealthy status. Log detailed health check failures to assist debugging but keep health check command output minimal.

Consider implementing health check endpoints in connectors that expose HTTP interfaces. Provide GET endpoint at /health returning simple success response. Include checks for MQTT connectivity, critical process status, and essential resource availability.

### Logging Best Practices

Write logs to stdout and stderr for Docker to capture. Avoid writing log files to disk unless required for integration with wrapped applications that generate logs.

Structure log messages consistently. Include timestamps in ISO 8601 format. Include log level indicators like INFO, WARNING, ERROR. Include process or service identifiers in multi-process containers. Include context like device identifiers or operation types.

Use structured logging formats like JSON for machine parsing. Include fields for timestamp, level, message, service, and contextual data. Libraries like Python's structlog or Node.js's winston support structured logging.

Control log verbosity using LOG_LEVEL environment variable. Implement log level checks before expensive log message construction. Avoid excessive debug logging that overwhelms log aggregation systems.

Handle exceptions with appropriate logging. Log exception messages and stack traces to stderr. Include context about the operation that failed. Log at ERROR level for exceptions that impact functionality and WARNING level for exceptions that are handled gracefully.

## Troubleshooting Guide

Common issues and resolution strategies for connector development.

### Container Startup Failures

Container fails to start or exits immediately after launch. Check container logs using Docker logs command. Look for exceptions or error messages during initialization. Verify environment variables are set correctly especially INSTANCE_NAME. Confirm configuration file exists at expected path and contains valid JSON.

Verify base image downloads successfully and all packages install correctly. Check Dockerfile syntax for errors. Ensure all COPY or ADD commands reference existing files. Test Dockerfile builds successfully on development machine.

Configuration parsing errors often cause startup failures. Validate JSON syntax in configuration files. Verify required fields exist in configuration. Check field types match expectations. Add detailed error logging during configuration loading.

### MQTT Connection Issues

Container runs but MQTT status never shows online. Verify MQTT_HOST and MQTT_PORT environment variables match broker configuration. Check network connectivity between container and broker using ping or telnet. Verify authentication credentials if broker requires username and password.

Examine MQTT client logs for connection errors. Look for authentication failures, protocol version mismatches, or network timeouts. Verify Last Will and Testament configuration happens before connection attempt.

Test MQTT connectivity using command-line tools like mosquitto_pub from within the container. Execute docker exec to access running container. Attempt manual MQTT connection to isolate connector code from network issues.

### Multi-Process Coordination Problems

Some processes in multi-process containers fail while others run successfully. Check supervisord logs for process startup failures. Verify process commands are correct with full paths to executables. Ensure required dependencies are installed for each process's language runtime.

Review process startup order and dependencies. Processes depending on other processes may fail if dependencies haven't started. Implement startup delays or health check loops. Adjust supervisord priority values to sequence startup.

Inter-process communication failures indicate network or permission issues. Verify processes bind to localhost addresses correctly. Check that ports don't conflict between processes. Verify file permissions for Unix domain sockets if used.

### Device Communication Failures

Connector starts successfully but devices show offline or unreachable. Verify device IP addresses or connection details in configuration match actual devices. Check network connectivity between container and devices using ping. Verify devices are powered on and networked properly.

Examine device-specific protocol implementations. Add detailed logging around device communication operations. Capture protocol traffic using tools like tcpdump for debugging. Verify connector speaks correct protocol version or dialect.

Authentication or authorization failures prevent device access. Verify credentials in configuration match device expectations. Check device access control lists or firewall rules. Ensure container's network identity has appropriate permissions.

### State Update Problems

Device states don't update in MQTT topics or update irregularly. Verify get_device_state method executes without exceptions. Check that polling interval allows sufficient time for device queries. Ensure state publishing calls happen after successful state retrieval.

State transformations may introduce bugs. Add logging before and after transformations. Verify data types match MQTT publication expectations. Check for None values or missing keys causing silent failures.

MQTT quality of service or retention settings affect state visibility. Verify QoS matches broker capabilities. Check retained message behavior for state topics. Ensure subscribers connect with appropriate QoS levels.

### Memory or Resource Leaks

Container memory usage grows over time until system kills process. Profile memory usage using tools like memory_profiler for Python. Look for unbounded collections like caches without expiration. Verify external resources like HTTP connections close properly.

Check for reference cycles preventing garbage collection in languages with automatic memory management. Ensure event handlers or callbacks are cleaned up after use. Review logging implementations for potential memory accumulation.

Multi-process containers require careful resource monitoring. Set memory limits at Docker level to prevent host system impact. Monitor individual process memory usage using supervisord or operating system tools. Identify which process leaks resources.

### Debugging Techniques

Access running containers using docker exec with bash or sh shells. Inspect filesystem contents and running processes. Check environment variables and mounted volumes. Test network connectivity and device communication interactively.

Increase logging verbosity by setting LOG_LEVEL to DEBUG. Add extensive logging around problem areas. Use structured logging to track operation flow. Correlate log entries using unique identifiers for operations.

Test connectors locally before deployment. Run containers on development machines. Use Docker Compose for local multi-container testing if needed. Inject test configurations and validate behavior.

Isolate problems by simplifying configurations. Test with single device before multiple devices. Disable optional features. Strip connector to minimal functionality then add features incrementally.

## Migration Guide

Developers familiar with BaseConnector-only patterns should understand when and how to adopt more advanced approaches.

### From BaseConnector to Direct Contract Implementation

Simple connectors using BaseConnector may benefit from direct contract implementation when event-driven architecture becomes necessary, when performance requirements exceed Python polling capabilities, when integration with languages other than Python is desired, or when fine-grained control over MQTT behavior is required.

Steps for migration include: retain configuration file loading but implement manually instead of using BaseConnector, instantiate MQTTClient directly and manage connection lifecycle, implement custom subscription handling for command and get topics, develop event-driven architecture replacing polling loop, maintain MQTT topic contract exactly matching specifications.

Advantages of direct implementation include elimination of polling overhead for event-driven scenarios, improved performance from removing base class abstraction, greater flexibility in MQTT quality of service and retention policies, easier integration of alternative programming languages.

Disadvantages include more code to maintain without base class conveniences, explicit handling of all contract requirements without helper methods, more complex error handling and recovery logic.

### From Single-Process to Multi-Process

Connectors experiencing performance bottlenecks, requiring integration of multiple languages, or managing complex long-running operations should consider multi-process architecture.

Identify which operations benefit from separate processes. CPU-intensive computations benefit from dedicated processes unrestricted by Global Interpreter Lock. Long-running network connections isolate blocking operations from control logic. Language-specific libraries that lack Python bindings require native language processes.

Design inter-process communication patterns. Choose HTTP REST APIs for request-response patterns. Select Unix domain sockets for high-volume data transfer. Consider message queues for asynchronous operations. Implement shared state mechanisms for coordination.

Implement process management using supervisord for simplicity, custom Python scripts for control, or shell scripts for minimal overhead. Configure process startup order accounting for dependencies. Implement health checks verifying all critical processes run successfully.

Test multi-process coordination thoroughly. Verify processes start in correct order. Confirm inter-process communication works under load. Validate graceful shutdown propagates to all processes. Monitor resource usage to ensure processes don't compete destructively.

### From Custom Implementation to Wrapper Pattern

When discovering existing open-source projects provide equivalent functionality, consider wrapping them rather than maintaining custom implementations.

Evaluate whether upstream projects meet requirements. Verify device support matches needs. Check project maintenance status and community activity. Review licensing compatibility with project requirements. Assess configuration flexibility and extension points.

Design translation layer architecture. Determine which MQTT topics require translation. Map upstream identifiers to IoT2MQTT device IDs. Transform message payloads between formats. Handle errors and edge cases gracefully.

Embed upstream projects using appropriate methods. Add git submodules for source-based projects. Install packages for distribution-available projects. Download binaries for pre-built releases. Configure build processes in Dockerfile.

Maintain wrapper layer separately from upstream updates. Implement version pinning to control update timing. Test translation layer against upstream changes. Document upstream version compatibility. Provide upgrade paths for instance configurations.

## Reference Documentation

### Relevant Source Files

**web/backend/services/docker_service.py**
Manages Docker container lifecycle including creation, starting, stopping, and removal. The create_container method constructs container configurations with appropriate volumes, environment variables, and network settings. Implements image building from Dockerfile when images don't exist. Handles container naming conventions and labeling for identification.

**web/backend/services/config_service.py**
Manages instance configuration files and environment variable loading. Provides methods for reading and writing instance JSON files with appropriate file locking. Handles configuration validation and schema enforcement. Manages secrets integration for sensitive configuration values. Implements configuration directory structure maintenance.

**shared/mqtt_client.py**
Provides MQTT client wrapper with IoT2MQTT-specific functionality. Implements connection management with retry logic and Last Will and Testament configuration. Provides convenience methods for publishing state, errors, events with appropriate topic construction. Handles message routing and callback dispatch for subscriptions. Implements QoS and retention flag management.

**shared/base_connector.py**
Implements optional base class for simple Python connectors. Provides configuration loading, MQTT client initialization, polling loop implementation, and command handling. Defines abstract methods that subclasses must implement for device-specific operations. Includes helper methods for state publishing and error handling.

**test-runner/main.py**
Implements FastAPI service executing connector action scripts during setup phase. Provides endpoints for tool execution receiving tool name and parameters. Executes Python scripts as subprocesses with stdin/stdout communication. Implements timeout handling and error reporting. Manages action script isolation and security.

**connectors/yeelight/connector.py**
Reference implementation demonstrating BaseConnector usage for simple polling-based devices. Shows configuration loading, device state retrieval, command handling, and MQTT integration. Illustrates error handling patterns and device communication protocols. Serves as template for similar connector types.

**connectors/_template/connector.py**
Minimal connector template showing required structure. Demonstrates abstract method implementation patterns. Provides starting point for new connector development. Documents expected file structure and organization.

### Additional Resources

Project documentation at docs/ directory contains architecture overviews, deployment guides, and API references. Setup flow specifications in connector setup.json files demonstrate declarative interface definitions. Example implementations in connectors/ directory show various patterns and approaches.

Upstream MQTT specification documents MQTT protocol version three point one point one features used throughout the platform. Docker documentation covers container best practices, networking, and volume management relevant to connector development. Supervisord documentation explains process management configuration and operation for multi-process connectors.

### Version History

Version two point zero represents major architectural expansion enabling connectors of arbitrary complexity while maintaining backward compatibility with simple implementations. Previous version one focused exclusively on Python polling-based connectors using mandatory base class inheritance. Version two eliminates mandatory patterns, defines clear contracts, and documents advanced implementation approaches while retaining all version one capabilities.

Future versions may introduce additional convenience utilities for common patterns, expanded language-specific integration examples, standardized observability and metrics collection, and enhanced inter-connector communication mechanisms for complex scenarios requiring coordination between instances.
