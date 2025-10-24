FROM python:3.11-slim

WORKDIR /app

# Install system dependencies with retry
RUN set -e; \
    RETRIES=3; \
    for i in $(seq 1 $RETRIES); do \
        echo "apt-get attempt $i/$RETRIES"; \
        if apt-get update && apt-get install -y \
            iputils-ping \
            net-tools \
            curl \
            build-essential \
            gcc \
            python3-dev \
            libffi-dev \
            libssl-dev \
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

# Copy requirements and install Python dependencies with retry
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

# Copy application code
COPY main.py .
COPY tests/ ./tests/

# Environment variables
ENV PYTHONUNBUFFERED=1
ENV TEST_RUNNER_PORT=8001

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8001/health || exit 1

# Expose port
EXPOSE 8001

# Run the application
CMD ["python", "-u", "main.py"]
