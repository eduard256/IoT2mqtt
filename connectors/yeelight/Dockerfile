# Yeelight Connector Dockerfile
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies if needed
# RUN apt-get update && apt-get install -y \
#     build-essential \
#     && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy connector code
COPY *.py ./

# Create instances directory
RUN mkdir -p instances

# Environment variables
ENV PYTHONUNBUFFERED=1
ENV MODE=production
ENV LOG_LEVEL=INFO

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import sys; sys.exit(0)" || exit 1

# Run the connector
CMD ["python", "-u", "main.py"]