#!/usr/bin/env python3
"""
Yeelight Discovery Script
Простой скрипт для обнаружения устройств Yeelight в сети
"""

import json
import sys
import socket
import logging
from typing import List, Dict, Any

# Отключаем логирование чтобы не портить JSON вывод
logging.disable(logging.CRITICAL)

def discover_yeelight_devices(timeout: int = 10) -> List[Dict[str, Any]]:
    """
    Обнаружение устройств Yeelight в локальной сети
    
    Args:
        timeout: Время поиска в секундах
    
    Returns:
        Список найденных устройств
    """
    devices = []
    
    try:
        # Импортируем библиотеку Yeelight
        from yeelight import discover_bulbs
        
        # Запускаем поиск
        bulbs = discover_bulbs(timeout=timeout)
        
        # Обрабатываем найденные устройства
        for bulb in bulbs:
            try:
                ip = bulb.get('ip', '')
                port = bulb.get('port', 55443)
                capabilities = bulb.get('capabilities', {})
                
                # Формируем информацию об устройстве
                device = {
                    "id": f"yeelight_{ip.replace('.', '_')}",
                    "name": capabilities.get('name', f"Yeelight {ip}"),
                    "ip": ip,
                    "port": port,
                    "model": capabilities.get('model', 'unknown'),
                    "fw_ver": capabilities.get('fw_ver', 'unknown'),
                    "support": capabilities.get('support', []),
                    "integration": "yeelight",
                    "manufacturer": "Yeelight",
                    "capabilities": parse_capabilities(capabilities)
                }
                
                # Определяем тип устройства
                device["device_type"] = detect_device_type(device["model"], device["support"])
                
                devices.append(device)
                
            except Exception as e:
                # Пропускаем проблемные устройства
                continue
                
    except ImportError:
        # Библиотека yeelight не установлена
        return {"error": "yeelight library not installed"}
    except Exception as e:
        # Другие ошибки
        return {"error": str(e)}
    
    return devices


def parse_capabilities(caps: Dict[str, Any]) -> Dict[str, Any]:
    """
    Парсинг возможностей устройства
    
    Args:
        caps: Словарь capabilities от устройства
    
    Returns:
        Обработанные capabilities
    """
    support = caps.get('support', [])
    
    capabilities = {
        "power": True,  # Все устройства поддерживают включение/выключение
        "brightness": "set_bright" in support,
        "color_temp": "set_ct_abx" in support,
        "rgb": "set_rgb" in support,
        "hsv": "set_hsv" in support,
        "color_flow": "start_cf" in support,
        "night_light": "set_scene" in support,
        "timer": "cron_add" in support,
        "adjust": "set_adjust" in support,
        "music_mode": "set_music" in support
    }
    
    # Для ceiling lights
    if "bg_set_power" in support:
        capabilities["background_light"] = True
        capabilities["background_rgb"] = "bg_set_rgb" in support
        capabilities["background_brightness"] = "bg_set_bright" in support
    
    # Ranges
    if capabilities["brightness"]:
        capabilities["brightness_range"] = {"min": 1, "max": 100}
    
    if capabilities["color_temp"]:
        capabilities["color_temp_range"] = {"min": 1700, "max": 6500}
    
    return capabilities


def detect_device_type(model: str, support: List[str]) -> str:
    """
    Определение типа устройства по модели и поддерживаемым функциям
    
    Args:
        model: Модель устройства
        support: Список поддерживаемых функций
    
    Returns:
        Тип устройства
    """
    model_lower = model.lower()
    
    # По модели
    if "mono" in model_lower:
        return "mono"
    elif "color" in model_lower:
        return "color"
    elif "strip" in model_lower or "stripe" in model_lower:
        return "stripe"
    elif "ceiling" in model_lower:
        return "ceiling"
    elif "lamp" in model_lower or "bslamp" in model_lower:
        return "bslamp"
    elif "desklamp" in model_lower:
        return "desklamp"
    
    # По функциям
    if "bg_set_power" in support:
        return "ceiling"  # Ceiling lights имеют background light
    elif "set_rgb" in support:
        return "color"  # RGB поддержка = color bulb
    elif "set_ct_abx" in support:
        return "mono"  # Только цветовая температура = mono
    
    return "unknown"


def validate_device(ip: str, port: int = 55443) -> bool:
    """
    Проверка доступности устройства
    
    Args:
        ip: IP адрес устройства
        port: Порт устройства
    
    Returns:
        True если устройство доступно
    """
    try:
        # Пробуем подключиться
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(2)
        result = sock.connect_ex((ip, port))
        sock.close()
        return result == 0
    except:
        return False


def main():
    """Главная функция для запуска из командной строки"""
    import os
    
    # Получаем таймаут из переменной окружения или используем по умолчанию
    timeout = int(os.environ.get("DISCOVERY_TIMEOUT", "10"))
    
    # Запускаем discovery
    devices = discover_yeelight_devices(timeout)
    
    # Выводим результат в JSON
    if isinstance(devices, dict) and "error" in devices:
        # Ошибка - выводим и выходим с кодом 1
        print(json.dumps(devices))
        sys.exit(1)
    else:
        # Успех - выводим найденные устройства
        print(json.dumps(devices))
        sys.exit(0)


if __name__ == "__main__":
    main()