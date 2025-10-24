FROM python:3.11-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1
ENV IOT2MQTT_PATH=/app

COPY requirements.txt ./
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

COPY . .

CMD ["python", "main.py"]
