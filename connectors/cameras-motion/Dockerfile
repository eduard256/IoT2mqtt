# Camera Motion Detection Connector
# FFmpeg-based motion detection for IP cameras
FROM python:3.11-slim

# Install FFmpeg (required for motion detection)
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy connector code
COPY connector.py motion_detector.py ./

# Copy shared libraries (mounted by docker_service.py)
# Note: /app/shared is mounted at runtime

# Default command
CMD ["python", "-u", "connector.py"]
