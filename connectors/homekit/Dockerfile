# HomeKit Connector Dockerfile
# Multi-process architecture: BaseConnector (MQTT) + AsyncIO HAP Service
FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    libffi-dev \
    libssl-dev \
    avahi-utils \
    libavahi-compat-libdnssd-dev \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy connector code
COPY . .

# Copy shared libraries
COPY ../../shared /app/shared

# Expose HAP service port (internal communication)
EXPOSE 8765

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV MODE=production

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8765/health', timeout=5)" || exit 1

# Entry point
CMD ["python", "main.py"]
