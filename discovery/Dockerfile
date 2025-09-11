FROM python:3.11-slim

WORKDIR /app

# Установка зависимостей
RUN pip install --no-cache-dir \
    docker==6.1.3 \
    paho-mqtt==1.6.1 \
    python-dotenv==1.0.0

# Копируем код
COPY discovery_manager.py /app/
COPY requirements.txt* /app/

# Установка дополнительных зависимостей если есть
RUN if [ -f requirements.txt ]; then pip install --no-cache-dir -r requirements.txt; fi

# Монтируем конфиги и папку коннекторов
VOLUME ["/app/config.json", "/app/discovered.json", "/app/connectors"]

# Переменные окружения
ENV PYTHONUNBUFFERED=1
ENV MODE=production

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
  CMD python -c "import json; data = json.load(open('/app/discovered.json')); exit(0 if 'devices' in data else 1)"

# Запуск
CMD ["python", "-u", "discovery_manager.py"]