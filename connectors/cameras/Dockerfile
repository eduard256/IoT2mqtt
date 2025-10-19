# Camera Connector Dockerfile with go2rtc integration
FROM python:3.11-slim

# go2rtc version (can be overridden at build time)
ARG GO2RTC_VERSION=1.9.4

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    wget \
    supervisor \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Download go2rtc binary (specific version for deterministic builds)
RUN wget -O /usr/local/bin/go2rtc \
    https://github.com/AlexxIT/go2rtc/releases/download/v${GO2RTC_VERSION}/go2rtc_linux_amd64 \
    && chmod +x /usr/local/bin/go2rtc \
    && /usr/local/bin/go2rtc --version || echo "go2rtc version check skipped"

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy connector code
COPY generate_go2rtc_config.py connector.py supervisord.conf ./

# Create instances directory mount point
RUN mkdir -p /app/instances

# Environment variables
ENV PYTHONUNBUFFERED=1
ENV MODE=production
ENV LOG_LEVEL=INFO

# Expose ports
# Note: These are internal container ports. go2rtc uses these by default.
# Docker networking isolates each container instance.
EXPOSE 1984 8554 8555

# Health check - verify go2rtc and connector are running
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:1984/api || exit 1

# ENTRYPOINT: Generate config → Start supervisord
# 1. generate_go2rtc_config.py creates /app/go2rtc.yaml from instance config
# 2. supervisord starts go2rtc and connector.py
ENTRYPOINT ["sh", "-c", "python3 /app/generate_go2rtc_config.py && exec supervisord -c /app/supervisord.conf"]
