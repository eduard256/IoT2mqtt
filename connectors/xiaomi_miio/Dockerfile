# Xiaomi MiIO Connector for IoT2MQTT
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    make \
    libffi-dev \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy shared modules first
COPY shared/ /app/shared/

# Copy connector files
COPY connectors/xiaomi_miio/ /app/connectors/xiaomi_miio/

# Install Python dependencies
RUN pip install --no-cache-dir -r /app/connectors/xiaomi_miio/requirements.txt
RUN pip install --no-cache-dir paho-mqtt python-dotenv

# Set environment variables
ENV PYTHONPATH=/app:$PYTHONPATH
ENV CONNECTOR_TYPE=xiaomi_miio

# Create volume for configuration
VOLUME ["/app/instances", "/app/config"]

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import sys; sys.path.insert(0, '/app'); from connectors.xiaomi_miio.connector import Connector; print('OK')" || exit 1

# Run the connector
CMD ["python", "-m", "connectors.xiaomi_miio.connector"]