# Multi-Process Connector Template Dockerfile
# This template demonstrates running multiple services (Python + Node.js) in a single container
# managed by supervisord for process coordination and automatic restart

FROM python:3.11-slim

# Install system dependencies
# - supervisor: Process manager for running multiple services
# - nodejs/npm: Runtime for Node.js services
# - curl: Health checks and HTTP requests
# - build-essential: Compilation tools for native Python/Node modules
RUN apt-get update && apt-get install -y \
    supervisor \
    curl \
    nodejs \
    npm \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies
# Copy requirements first to leverage Docker layer caching
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# Install Node.js service dependencies
# Each service has its own package.json in its subdirectory
COPY services/nodejs-service/package*.json /app/services/nodejs-service/
WORKDIR /app/services/nodejs-service
RUN npm install --production

# Return to app root and copy all application code
WORKDIR /app
COPY . /app/

# Copy supervisord configuration to system location
# This configuration defines all processes and their management rules
COPY supervisord.conf /etc/supervisor/conf.d/supervisord.conf

# Create log directory for supervisor
RUN mkdir -p /var/log/supervisor

# Environment variables
# These are injected by docker_service.py when creating the container:
# - INSTANCE_NAME: Unique identifier for this connector instance
# - CONNECTOR_TYPE: Type of connector (for logging/observability)
# - MODE: Operating mode (production/development)
# Additional variables from .env file are mounted and loaded by MQTTClient
ENV PYTHONUNBUFFERED=1

# Expose ports if needed
# Example: If go2rtc or other services need external access
# EXPOSE 8554 1984

# Health check
# Verify supervisord is running and at least the MQTT bridge process is healthy
# Customize this to check your specific critical processes
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD supervisorctl status mqtt-bridge | grep -q RUNNING || exit 1

# Start supervisord as the main process
# Supervisord will start all configured processes and monitor them
# Using -n flag to run in foreground so Docker can monitor it
CMD ["/usr/bin/supervisord", "-n", "-c", "/etc/supervisor/conf.d/supervisord.conf"]
