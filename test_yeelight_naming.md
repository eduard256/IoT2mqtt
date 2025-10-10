# Yeelight Naming Fix - Test Scenarios

## ✅ ФИНАЛЬНАЯ ПРАВИЛЬНАЯ ЛОГИКА:

### Ключевая концепция:
- **Device Name (friendly_name)** → используется для **device_id** (нормализуется)
- **Instance ID** → уникальный идентификатор инстанса коннектора (auto: `{integration}_{Random6}`)
  - Формат random: 6 символов, mixed-case + цифры (например: `7K9mX2`, `A3k9M2`)

### Auto Discovery Flow:
1. **Device Name** - имя устройства (например "Main Eduard Monitor Strip")
2. **Instance ID** - опционально, auto-generation = `yeelight_{Random6}` (например `yeelight_7K9mX2`)
3. **Device ID** = нормализованное Device Name = `main-eduard-monitor-strip`

### Manual Entry Flow:
1. **Device Name** - имя устройства (например "Main Eduard Monitor Strip")
2. **Instance ID** - опционально, auto-generation = `yeelight_{Random6}` (например `yeelight_7K9mX2`)
3. **Device ID** = нормализованное Device Name = `main-eduard-monitor-strip`

## Примеры:

### Пример 1: Auto Discovery
- Вводим Device Name: "Main Eduard Monitor Strip"
- Instance ID: оставляем пустым (auto)
- Результат:
  - instance_id: `yeelight_7K9mX2` (случайный mixed-case суффикс)
  - device_id: `main-eduard-monitor-strip` (нормализовано из Device Name)
  - device name: "Main Eduard Monitor Strip"
  - **MQTT путь**: `IoT2mqtt/v1/instances/yeelight_7K9mX2/devices/main-eduard-monitor-strip`

### Пример 2: Manual Entry
- Вводим Device Name: "Main Eduard Monitor Strip"
- IP: "10.0.20.43"
- Instance ID: оставляем пустым (auto)
- Результат:
  - instance_id: `yeelight_A3k9M2` (случайный mixed-case суффикс)
  - device_id: `main-eduard-monitor-strip` (нормализовано из Device Name)
  - device name: "Main Eduard Monitor Strip"
  - **MQTT путь**: `IoT2mqtt/v1/instances/yeelight_A3k9M2/devices/main-eduard-monitor-strip`

## Изменения в setup.json:

### Auto Discovery (lines 61-164):
- ✅ Поля переставлены: Friendly Name первым, Instance ID вторым (advanced)
- ✅ Instance ID теперь опциональный с placeholder "auto"
- ✅ Description обновлено: "Leave empty to auto-generate from friendly name and IP address"
- ✅ Device name теперь берётся из form.instance_details.friendly_name (line 158)
- ✅ Summary обновлён: показывает Device Name, IP Address, Instance ID

### Manual Entry (lines 167-303):
- ✅ Поля переставлены: Friendly Name первым, Instance ID третьим (advanced)
- ✅ Instance ID опциональный с placeholder "auto"
- ✅ Device ID генерируется как "yeelight_{{ form.device_form.ip }}" (line 295)
- ✅ Device name берётся из form.device_form.friendly_name (line 298)
- ✅ Summary обновлён: показывает Device Name, IP Address, Instance ID

## Проверка:

Теперь когда вы добавите Yeelight устройство с именем "Monitor":
- Instance назовётся "monitor" (или auto-generated)
- Устройство назовётся "Monitor"
- MQTT путь будет: `IoT2mqtt/v1/instances/monitor/devices/{device_id}`

Где {device_id} это:
- ID устройства для auto discovery
- "yeelight_IP" для manual entry
