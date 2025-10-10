# Yeelight Naming Fix - Test Scenarios

## Исправленная логика:

### Auto Discovery Flow:
1. **Friendly Name** - имя устройства (например "Monitor")
2. **Instance ID** - опционально, auto-generation из friendly_name + IP
3. **Device Name** = Friendly Name
4. **Device ID** = из discovery (device_id с устройства)

### Manual Entry Flow:
1. **Friendly Name** - имя устройства (например "Monitor")
2. **Instance ID** - опционально, auto-generation из friendly_name + IP
3. **Device Name** = Friendly Name
4. **Device ID** = "yeelight_{IP}"

## Примеры:

### Пример 1: Auto Discovery
- Вводим Friendly Name: "Monitor"
- Instance ID: оставляем пустым (auto)
- Результат:
  - instance_id: "monitor" (или "monitor_192_168_1_100" если auto)
  - device name: "Monitor"
  - device_id: "0x00000000DEADBEEF" (из устройства)
  - MQTT путь: `IoT2mqtt/v1/instances/monitor/devices/0x00000000DEADBEEF`

### Пример 2: Manual Entry
- Вводим Friendly Name: "Monitor"
- IP: "192.168.1.100"
- Instance ID: оставляем пустым (auto)
- Результат:
  - instance_id: "monitor" (или "monitor_192_168_1_100" если auto)
  - device name: "Monitor"
  - device_id: "yeelight_192.168.1.100"
  - MQTT путь: `IoT2mqtt/v1/instances/monitor/devices/yeelight_192.168.1.100`

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
