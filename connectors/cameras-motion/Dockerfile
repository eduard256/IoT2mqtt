# Camera Motion Detection Connector
# FFmpeg-based motion detection for IP cameras
FROM python:3.11-slim

# Install FFmpeg (required for motion detection) with retry
RUN set -e; \
    RETRIES=3; \
    for i in $(seq 1 $RETRIES); do \
        echo "apt-get attempt $i/$RETRIES"; \
        if apt-get update && \
            apt-get install -y --no-install-recommends \
                ffmpeg; then \
            break; \
        fi; \
        if [ $i -eq $RETRIES ]; then \
            echo "ERROR: apt-get failed after $RETRIES attempts"; \
            exit 1; \
        fi; \
        sleep 5; \
    done && \
    rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements and install with retry
COPY requirements.txt .
RUN set -e; \
    RETRIES=3; \
    for i in $(seq 1 $RETRIES); do \
        echo "pip install attempt $i/$RETRIES"; \
        if pip install --no-cache-dir -r requirements.txt; then \
            break; \
        fi; \
        if [ $i -eq $RETRIES ]; then \
            echo "ERROR: pip install failed after $RETRIES attempts"; \
            exit 1; \
        fi; \
        sleep 5; \
    done

# Copy connector code
COPY connector.py motion_detector.py ./

# Copy shared libraries (mounted by docker_service.py)
# Note: /app/shared is mounted at runtime

# Default command
CMD ["python", "-u", "connector.py"]
