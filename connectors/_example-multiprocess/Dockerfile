# IoT2MQTT Multi-Process Sensor Hub Example
# Demonstrates running multiple services in a single container
FROM python:3.11-slim

# Install system dependencies
# - supervisor: Process manager for coordinating multiple services
# - curl: For health checks and testing
# - nodejs/npm: For the HTTP poller service
RUN apt-get update && apt-get install -y \
    supervisor \
    curl \
    nodejs \
    npm \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies first (better caching)
# Copy requirements files for all Python services
COPY requirements.txt /app/
COPY services/serial-handler/requirements.txt /app/services/serial-handler/
COPY services/state-aggregator/requirements.txt /app/services/state-aggregator/

# Install all Python packages in one layer
RUN pip install --no-cache-dir -r /app/requirements.txt && \
    pip install --no-cache-dir -r /app/services/serial-handler/requirements.txt && \
    pip install --no-cache-dir -r /app/services/state-aggregator/requirements.txt

# Install Node.js dependencies
# Copy package files first for better caching
COPY services/http-poller/package*.json /app/services/http-poller/
WORKDIR /app/services/http-poller
RUN npm ci --only=production

# Copy application code
# Copied last to maximize cache hits during development
WORKDIR /app
COPY services/ /app/services/
COPY mqtt_bridge.py /app/
COPY supervisord.conf /etc/supervisor/conf.d/supervisord.conf

# Environment variables
# These will be overridden by docker_service.py with instance-specific values
ENV INSTANCE_NAME=example_sensor_hub
ENV CONNECTOR_TYPE=sensor-hub
ENV PYTHONUNBUFFERED=1

# Expose internal API ports (not published externally, only for inter-process communication)
# 5001: Serial handler API
# 5002: HTTP poller API
# 5003: State aggregator API
EXPOSE 5001 5002 5003

# Health check verifies that at least the state aggregator is responding
# This is a proxy for overall system health since it depends on other services
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:5003/health || exit 1

# Start supervisord which will launch and manage all services
# The -n flag keeps supervisor in foreground so Docker can track it
CMD ["/usr/bin/supervisord", "-n", "-c", "/etc/supervisor/conf.d/supervisord.conf"]
