FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Environment variables
ENV PYTHONUNBUFFERED=1
ENV MODE=production
ENV WEB_PORT=3000
ENV IOT2MQTT_PATH=/app

# Expose port
EXPOSE 3000

# Run the application
CMD ["python", "-u", "main.py"]