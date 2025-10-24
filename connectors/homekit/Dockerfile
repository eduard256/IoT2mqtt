FROM python:3.11-slim

WORKDIR /app

# Install system dependencies for networking and zeroconf
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    libavahi-compat-libdnssd-dev \
    avahi-utils \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy connector files
COPY connector.py homekit_manager.py main.py ./

# Copy shared libraries from parent
# Note: shared/ directory is mounted at runtime by docker-compose

# Make main.py executable
RUN chmod +x main.py

# Health check
HEALTHCHECK --interval=30s --timeout=3s --retries=3 --start-period=10s \
    CMD python3 /app/shared/healthcheck.py

# Run connector
CMD ["python3", "main.py"]
