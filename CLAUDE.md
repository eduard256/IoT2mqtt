# IoT2MQTT - Документация для AI разработчиков

## 🎯 Философия проекта

IoT2MQTT - это революционная система для умного дома, которая:
- **MQTT First** - все построено вокруг MQTT, не Home Assistant
- **Минимальная задержка** - прямое подключение к устройствам без лишних слоев
- **Микросервисная архитектура** - один контейнер = один аккаунт/инстанс
- **Независимость коннекторов** - каждый коннектор полностью автономен
- **Простота без overengineering** - минимум абстракций
- **Долгосрочность** - код который будет работать годами

## 📋 Quick Start для AI

Когда пользователь просит создать новый коннектор:

1. **Анализируй источник** (HA интеграция, документация API, SDK)
2. **Копируй шаблон** из `connectors/_template/`
3. **Реализуй connector.py** с минимальными изменениями
4. **Создай setup.py** копируя UI оригинального приложения
5. **Тестируй** с реальными устройствами или моками

## 🏗️ Архитектура системы

### Структура MQTT топиков

```
{base_topic}/v1/                          # base_topic настраивается (default: IoT2mqtt)
├── instances/
│   ├── {instance_id}/                    # Уникальный ID инстанса
│   │   ├── status                        # online/offline с LWT (retained)
│   │   ├── discovered                    # Новые найденные устройства
│   │   ├── devices/
│   │   │   ├── {device_id}/
│   │   │   │   ├── state                 # Полное состояние (retained)
│   │   │   │   ├── state/{property}      # Отдельные свойства
│   │   │   │   ├── cmd                   # Команды с timestamp
│   │   │   │   ├── cmd/response          # Ответы (TTL 5 min)
│   │   │   │   ├── events                # События (button press, motion)
│   │   │   │   ├── telemetry            # Метрики
│   │   │   │   ├── error                # Ошибки устройства
│   │   │   │   └── availability         # online/offline (retained)
│   │   ├── groups/
│   │   │   └── {group_name}/
│   │   │       ├── state
│   │   │       ├── cmd
│   │   │       └── members
│   │   └── meta/
│   │       ├── info                     # Информация об инстансе
│   │       └── devices_list             # Список устройств
├── bridge/
│   ├── status                           # Статус bridge (LWT)
│   ├── transactions/                    # Координация транзакций
│   │   └── {tx_id}/
│   │       ├── request
│   │       ├── status
│   │       └── result
│   ├── request/+                        # API команды
│   └── response/+                       # Ответы
├── global/
│   ├── devices/                         # Глобальный реестр
│   │   └── {instance_id}_{device_id}/
│   └── events                           # Глобальная шина событий
└── discovery/
    └── homeassistant/                   # Опциональный HA Discovery
```

### Структура проекта

```
IoT2mqtt/
├── iot2mqtt.py                 # Главный лаунчер с TUI
├── setup_mqtt.py              # Настройка MQTT и base_topic
├── .env                       # Общие настройки (без паролей!)
├── .gitignore                 # Игнорирует secrets и instances
├── secrets/                   # Docker secrets (не в git!)
│   ├── mqtt_admin.secret    
│   └── instances/            
├── docker-compose.yml         # Автогенерируемый
├── CLAUDE.md                  # Этот файл
├── README.md                 
├── shared/                    # Монтируется как read-only volume
│   ├── mqtt_client.py        
│   ├── base_connector.py     
│   ├── discovery.py          
│   └── utils.py             
├── bridge/                    # API Gateway и координатор
│   ├── main.py               
│   ├── transaction_coordinator.py
│   ├── response_cleaner.py  
│   └── Dockerfile            
└── connectors/
    └── _template/            # Эталонный шаблон
        ├── connector.py      # Основная логика
        ├── setup.py         # CLI создания инстанса
        ├── manage.py        # CLI управления
        ├── main.py          # Точка входа
        ├── instances/       # Конфиги без паролей
        ├── requirements.txt
        └── Dockerfile
```

## 🔄 Конвертация Home Assistant интеграций

### Шаг 1: Анализ HA интеграции

При получении папки с интеграцией найди:
- `__init__.py` - точка входа
- `config_flow.py` - UI конфигурация → основа для setup.py
- `const.py` - константы
- `entity.py`, `sensor.py`, `switch.py` - типы устройств
- Файлы с API логикой (`api.py`, `client.py`)

### Шаг 2: Извлечение core логики

```python
# ИЗ Home Assistant:
class XiaomiEntity(CoordinatorEntity):
    def __init__(self, coordinator, ...):
        super().__init__(coordinator)
        # 100+ строк HA специфичного кода

# В IoT2MQTT:
class Connector:
    def __init__(self, mqtt_client, config):
        self.device = Device(ip, token)  # Прямое подключение!
```

### Шаг 3: Удаляем HA слои

**Удаляем:**
- Entity классы
- Platform интеграцию
- Config entries
- Device/Entity registry
- Translations
- Services
- WebSocket API

**Оставляем:**
- Логику подключения к устройству
- Протокол общения
- Обработку ошибок
- Форматы данных

### Шаг 4: Создание setup.py

Преобразуй `config_flow.py` в CLI:

```python
# HA config_flow:
vol.Required("host"): str

# IoT2MQTT setup.py:
host = Prompt.ask("Device IP address")
```

### Шаг 5: Реализация connector.py

```python
class Connector:
    def __init__(self, mqtt_client, config):
        self.mqtt = mqtt_client
        self.config = config
        self.instance_id = config['instance_id']
        # Прямое подключение к устройству
        self.device = DeviceAPI(config['connection'])
    
    def start(self):
        """Запуск коннектора"""
        # Подписка на команды
        self.mqtt.subscribe(f"instances/{self.instance_id}/devices/+/cmd", 
                           self.handle_command)
        # Запуск основного цикла
        self.running = True
        threading.Thread(target=self._main_loop).start()
    
    def _main_loop(self):
        """Основной цикл опроса устройств"""
        while self.running:
            for device in self.config['devices']:
                if device['enabled']:
                    state = self.get_device_state(device)
                    self.publish_state(device['id'], state)
            time.sleep(self.config.get('update_interval', 10))
    
    def publish_state(self, device_id, state):
        """Публикация состояния с timestamp"""
        payload = {
            "timestamp": datetime.now().isoformat(),
            "device_id": device_id,
            "state": state
        }
        topic = f"instances/{self.instance_id}/devices/{device_id}/state"
        self.mqtt.publish(topic, payload, retain=True)
    
    def handle_command(self, topic, payload):
        """Обработка команд с timestamp ordering"""
        device_id = topic.split('/')[-2]
        
        # Проверяем timestamp для ordering
        cmd_time = payload.get('timestamp')
        if self.is_outdated(cmd_time):
            return
        
        # Применяем команду
        result = self.apply_command(device_id, payload['values'])
        
        # Отправляем ответ
        response_topic = f"instances/{self.instance_id}/devices/{device_id}/cmd/response"
        self.mqtt.publish(response_topic, {
            "cmd_id": payload.get('id'),
            "status": "success" if result else "error",
            "timestamp": datetime.now().isoformat()
        })
```

## 📝 Форматы данных

### Конфигурация инстанса (instances/{name}.json)

```json
{
  "instance_id": "xiaomi_home_cn",
  "instance_type": "account",
  "connector_type": "xiaomi",
  "connection": {
    "server": "cn",
    "username": "user@example.com"
    // Пароли в Docker secrets!
  },
  "devices": [
    {
      "device_id": "air_purifier_bedroom",
      "global_id": "xiaomi_home_cn_air_purifier_bedroom",
      "model": "zhimi.airpurifier.v7",
      "ip": "192.168.1.100",
      "enabled": true
    }
  ],
  "update_interval": 10
}
```

### Формат команды

```json
{
  "id": "cmd_unique_id",
  "timestamp": "2024-01-15T10:30:00.123Z",
  "values": {
    "power": true,
    "brightness": 75
  },
  "timeout": 5000
}
```

### Формат состояния

```json
{
  "timestamp": "2024-01-15T10:30:00.123Z",
  "device_id": "air_purifier_bedroom",
  "state": {
    "power": true,
    "mode": "auto",
    "aqi": 35,
    "temperature": 22.5
  },
  "link_quality": 100
}
```

## 🎨 UI/UX Guidelines для CLI

### Используй rich для красивого вывода

```python
from rich.console import Console
from rich.prompt import Prompt, Confirm
from rich.table import Table
from rich.panel import Panel

console = Console()

# Красивый заголовок
console.print(Panel.fit(
    "[bold cyan]IoT2MQTT Connector Setup[/bold cyan]",
    border_style="cyan"
))

# Интерактивный ввод
name = Prompt.ask("Instance name", default="home")

# Таблица устройств
table = Table(title="Discovered Devices")
table.add_column("ID", style="cyan")
table.add_column("Name", style="green")
table.add_column("Model")
```

### Копируй UI оригинальных приложений

Если в Mi Home:
1. Выбор региона
2. Email/Phone
3. Password
4. 2FA код
5. Список устройств

То в setup.py делай точно так же!

## 🐳 Docker правила

### Dockerfile шаблон

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Устанавливаем зависимости
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копируем код
COPY *.py ./

# Переменные окружения
ENV MODE=production
ENV PYTHONUNBUFFERED=1

# Точка входа
CMD ["python", "-u", "main.py"]
```

### docker-compose.yml для инстанса

```yaml
services:
  xiaomi_home_cn:
    build: ./connectors/xiaomi
    container_name: iot2mqtt_xiaomi_home_cn
    restart: unless-stopped
    volumes:
      - ./shared:/app/shared:ro              # Shared как read-only
      - ./connectors/xiaomi/instances:/app/instances:ro
    secrets:
      - xiaomi_home_cn_mqtt                  # MQTT credentials
      - xiaomi_home_cn_creds                 # Device credentials
    environment:
      - INSTANCE_NAME=home_cn
      - MODE=production                       # Без hot reload!
    networks:
      - iot2mqtt
```

## 🔒 Безопасность

### Правила работы с секретами

1. **НИКОГДА** не храни пароли в JSON файлах
2. Используй Docker secrets или environment variables
3. Каждый инстанс имеет свои MQTT credentials
4. Изолируй инстансы друг от друга
5. Используй принцип least privilege

### Структура secrets

```
secrets/
├── mqtt_admin.secret           # Admin доступ для bridge
└── instances/
    ├── xiaomi_home_cn_mqtt.secret    # MQTT для инстанса
    └── xiaomi_home_cn_creds.secret   # Credentials устройств
```

## 🚀 Процесс создания нового коннектора

### 1. Копирование шаблона

```bash
cp -r connectors/_template connectors/new_connector
```

### 2. Реализация connector.py

- Найди SDK или библиотеку для устройства
- Реализуй методы подключения
- Добавь обработку состояний
- Реализуй обработку команд

### 3. Создание setup.py

- Копируй UI оригинального приложения
- Используй rich для красивого вывода
- Сохраняй конфигурацию в instances/
- Генерируй Docker secrets

### 4. Тестирование

```python
# tests/test_new_connector.py
def test_connection():
    connector = Connector(mock_mqtt, test_config)
    assert connector.connect()

def test_state_publishing():
    connector.publish_state("test_device", {"power": True})
    assert mock_mqtt.published[0]['topic'] == "instances/test/devices/test_device/state"
```

## ⚡ Оптимизации производительности

### Батчинг телеметрии

```python
# Вместо отдельных публикаций
for device in devices:
    mqtt.publish(f"devices/{device}/telemetry", data)

# Используй батчинг
batch = []
for device in devices:
    batch.append({"device": device, "data": data})
mqtt.publish("telemetry/batch", batch)
```

### Кеширование состояний

```python
class Connector:
    def __init__(self):
        self.state_cache = {}
        self.cache_ttl = 60  # seconds
    
    def get_state(self, device_id):
        if self.is_cache_valid(device_id):
            return self.state_cache[device_id]
        
        state = self.fetch_state(device_id)
        self.state_cache[device_id] = {
            "state": state,
            "timestamp": time.time()
        }
        return state
```

## 🐛 Troubleshooting

### Проблема: Устройство не отвечает

1. Проверь сетевую доступность
2. Проверь credentials
3. Включи debug логирование
4. Проверь firewall правила

### Проблема: Дублирование команд

1. Проверь timestamp ordering
2. Убедись что command_id уникальный
3. Проверь что нет множественных подписок

### Проблема: Высокая задержка

1. Уменьши update_interval
2. Используй локальное подключение где возможно
3. Включи батчинг для телеметрии
4. Проверь QoS настройки MQTT

## 📚 Примеры коннекторов

### Облачный (Xiaomi)

```python
class Connector:
    def __init__(self, mqtt_client, config):
        self.cloud = MiCloud(
            username=os.environ['XIAOMI_USER'],
            password=os.environ['XIAOMI_PASS'],
            country=config['connection']['server']
        )
        self.devices = self.cloud.get_devices()
```

### Локальный (ESPHome)

```python
class Connector:
    def __init__(self, mqtt_client, config):
        self.api = APIClient(
            address=config['connection']['ip'],
            port=6053,
            password=os.environ.get('API_PASSWORD')
        )
```

### Гибридный (Yeelight)

```python
class Connector:
    def __init__(self, mqtt_client, config):
        if config.get('use_cloud'):
            self.client = YeelightCloud(token=os.environ['YEELIGHT_TOKEN'])
        else:
            self.client = YeelightLocal(ip=config['connection']['ip'])
```

## ✅ Чеклист качества коннектора

- [ ] Прямое подключение без лишних абстракций
- [ ] Поддержка timestamp ordering для команд
- [ ] Graceful shutdown по SIGTERM
- [ ] Автореконнект при потере связи
- [ ] Обработка ошибок с retry
- [ ] Логирование всех операций
- [ ] Кеширование где возможно
- [ ] Документация в README.md
- [ ] Тесты основных функций
- [ ] Docker secrets для паролей
- [ ] Оптимизированный Dockerfile

## 🎯 Best Practices

1. **KISS** - Keep It Simple, Stupid
2. **DRY** - Don't Repeat Yourself (используй shared/)
3. **YAGNI** - You Aren't Gonna Need It (не усложняй)
4. **Fail Fast** - быстро обнаруживай и сообщай об ошибках
5. **Log Everything** - логируй все важные операции
6. **Test Early** - тестируй как можно раньше
7. **Document Well** - документируй для будущих разработчиков

## 🤝 Для контрибьюторов

Если хочешь добавить новый коннектор:

1. Fork репозиторий
2. Создай ветку `feature/connector-name`
3. Скопируй `_template` и реализуй логику
4. Добавь документацию
5. Протестируй с реальными устройствами
6. Создай Pull Request

Мы ценим:
- Чистый, понятный код
- Следование архитектуре проекта
- Хорошую документацию
- Тесты

## 📞 Поддержка

- GitHub Issues: https://github.com/eduard256/IoT2mqtt/issues
- Discussions: https://github.com/eduard256/IoT2mqtt/discussions

---

*Этот документ - живой и будет обновляться по мере развития проекта.*