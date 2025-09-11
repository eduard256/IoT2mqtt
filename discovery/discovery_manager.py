#!/usr/bin/env python3
"""
Discovery Manager Service
Автоматическое обнаружение устройств для всех интеграций
"""

import os
import sys
import json
import time
import asyncio
import docker
import logging
import signal
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any, Optional
from threading import Thread, Event
import paho.mqtt.client as mqtt

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class DiscoveryManager:
    """Менеджер автоматического обнаружения устройств"""
    
    def __init__(self, config_path: str = "/app/config.json"):
        self.config_path = Path(config_path)
        self.discovered_path = Path("/app/discovered.json")
        self.config = self._load_config()
        self.docker_client = docker.from_env()
        self.mqtt_client = None
        self.running = Event()
        self.discovery_thread = None
        self.cleanup_thread = None
        
        # Кэш для дедупликации
        self.discovered_cache = set()
        self.added_devices = set()
        
    def _load_config(self) -> Dict[str, Any]:
        """Загрузка конфигурации"""
        try:
            with open(self.config_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load config: {e}")
            return {
                "auto_discovery": {
                    "enabled": True,
                    "interval": 300,
                    "on_startup": True,
                    "integrations": []
                }
            }
    
    def _setup_mqtt(self):
        """Настройка MQTT клиента"""
        try:
            self.mqtt_client = mqtt.Client(client_id="iot2mqtt_discovery_manager")
            
            # Читаем настройки MQTT из .env
            mqtt_host = os.getenv("MQTT_HOST", "localhost")
            mqtt_port = int(os.getenv("MQTT_PORT", 1883))
            mqtt_user = os.getenv("MQTT_USERNAME", "")
            mqtt_pass = os.getenv("MQTT_PASSWORD", "")
            
            if mqtt_user and mqtt_pass:
                self.mqtt_client.username_pw_set(mqtt_user, mqtt_pass)
            
            self.mqtt_client.connect(mqtt_host, mqtt_port, 60)
            self.mqtt_client.loop_start()
            logger.info(f"Connected to MQTT broker at {mqtt_host}:{mqtt_port}")
        except Exception as e:
            logger.error(f"Failed to connect to MQTT: {e}")
    
    def _publish_discovered(self, devices: List[Dict[str, Any]]):
        """Публикация найденных устройств в MQTT"""
        if not self.mqtt_client:
            return
        
        try:
            base_topic = os.getenv("MQTT_BASE_TOPIC", "IoT2mqtt")
            topic = f"{base_topic}/v1/discovery/devices"
            
            payload = {
                "timestamp": datetime.now().isoformat(),
                "devices": devices,
                "total": len(devices)
            }
            
            self.mqtt_client.publish(topic, json.dumps(payload), retain=True)
            logger.info(f"Published {len(devices)} devices to MQTT")
        except Exception as e:
            logger.error(f"Failed to publish to MQTT: {e}")
    
    def _save_discovered(self, devices: List[Dict[str, Any]]):
        """Сохранение найденных устройств в файл"""
        try:
            # Загружаем существующие
            existing = self._load_discovered()
            
            # Объединяем с новыми (дедупликация по ID)
            device_map = {d["id"]: d for d in existing["devices"]}
            
            for device in devices:
                device_id = device["id"]
                device["discovered_at"] = datetime.now().isoformat()
                device["added"] = device_id in self.added_devices
                device_map[device_id] = device
            
            # Сохраняем
            data = {
                "last_scan": datetime.now().isoformat(),
                "devices": list(device_map.values())
            }
            
            with open(self.discovered_path, 'w') as f:
                json.dump(data, f, indent=2)
            
            logger.info(f"Saved {len(devices)} discovered devices")
        except Exception as e:
            logger.error(f"Failed to save discovered devices: {e}")
    
    def _load_discovered(self) -> Dict[str, Any]:
        """Загрузка сохраненных устройств"""
        if not self.discovered_path.exists():
            return {"devices": []}
        
        try:
            with open(self.discovered_path, 'r') as f:
                return json.load(f)
        except:
            return {"devices": []}
    
    async def _run_discovery_for_integration(self, integration: str) -> List[Dict[str, Any]]:
        """Запуск discovery для одной интеграции"""
        logger.info(f"Running discovery for {integration}")
        
        try:
            # Проверяем наличие манифеста
            manifest_path = Path(f"/app/connectors/{integration}/manifest.json")
            if not manifest_path.exists():
                logger.warning(f"No manifest found for {integration}")
                return []
            
            with open(manifest_path, 'r') as f:
                manifest = json.load(f)
            
            if not manifest.get("discovery", {}).get("supported", False):
                logger.info(f"Discovery not supported for {integration}")
                return []
            
            # Получаем настройки discovery
            discovery_config = manifest["discovery"]
            timeout = discovery_config.get("timeout", 30)
            network_mode = discovery_config.get("network_mode", "host")
            command = discovery_config.get("command", "python discovery.py")
            
            # Запускаем контейнер
            container = self.docker_client.containers.run(
                f"iot2mqtt/{integration}:latest",
                command=command,
                network_mode=network_mode,
                remove=False,
                detach=True,
                stdout=True,
                stderr=True,
                mem_limit=self.config["docker"].get("memory_limit", "50m"),
                cpu_shares=self.config["docker"].get("cpu_shares", 256),
                read_only=self.config["docker"].get("read_only", True),
                security_opt=["no-new-privileges"] if self.config["docker"].get("no_new_privileges", True) else []
            )
            
            # Ждем завершения с таймаутом
            start_time = time.time()
            while time.time() - start_time < timeout:
                container.reload()
                if container.status != "running":
                    break
                await asyncio.sleep(1)
            
            # Получаем результат
            logs = container.logs().decode('utf-8')
            container.remove(force=True)
            
            # Парсим JSON результат
            try:
                devices = json.loads(logs)
                if isinstance(devices, dict) and "error" in devices:
                    logger.error(f"Discovery error for {integration}: {devices['error']}")
                    return []
                
                logger.info(f"Found {len(devices)} devices for {integration}")
                return devices
            except json.JSONDecodeError:
                logger.error(f"Invalid JSON from {integration} discovery: {logs[:200]}")
                return []
                
        except docker.errors.ImageNotFound:
            logger.warning(f"Docker image not found for {integration}")
            return []
        except Exception as e:
            logger.error(f"Discovery failed for {integration}: {e}")
            return []
    
    async def _run_discovery_cycle(self):
        """Запуск полного цикла discovery"""
        logger.info("Starting discovery cycle")
        
        integrations = self.config["auto_discovery"]["integrations"]
        if not integrations:
            logger.warning("No integrations configured for discovery")
            return
        
        all_devices = []
        
        if self.config["auto_discovery"].get("parallel", True):
            # Параллельное выполнение
            tasks = [self._run_discovery_for_integration(i) for i in integrations]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            for result in results:
                if isinstance(result, list):
                    all_devices.extend(result)
        else:
            # Последовательное выполнение
            for integration in integrations:
                devices = await self._run_discovery_for_integration(integration)
                all_devices.extend(devices)
        
        # Сохраняем и публикуем результаты
        if all_devices:
            self._save_discovered(all_devices)
            self._publish_discovered(all_devices)
        
        logger.info(f"Discovery cycle completed. Found {len(all_devices)} devices total")
    
    def _discovery_worker(self):
        """Фоновый поток для периодического discovery"""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        # Задержка перед первым запуском
        if self.config["auto_discovery"].get("on_startup", True):
            startup_delay = self.config["auto_discovery"].get("startup_delay", 10)
            logger.info(f"Waiting {startup_delay} seconds before first discovery")
            time.sleep(startup_delay)
            
            # Первый запуск
            loop.run_until_complete(self._run_discovery_cycle())
        
        # Периодический запуск
        interval = self.config["auto_discovery"].get("interval", 300)
        
        while self.running.is_set():
            try:
                self.running.wait(interval)
                if self.running.is_set():
                    loop.run_until_complete(self._run_discovery_cycle())
            except Exception as e:
                logger.error(f"Error in discovery worker: {e}")
                time.sleep(60)  # Пауза при ошибке
    
    def _cleanup_worker(self):
        """Очистка устаревших устройств"""
        ttl = self.config["retention"].get("discovered_devices_ttl", 86400)
        cleanup_interval = self.config["retention"].get("cleanup_interval", 3600)
        
        while self.running.is_set():
            try:
                self.running.wait(cleanup_interval)
                if not self.running.is_set():
                    break
                
                # Загружаем устройства
                data = self._load_discovered()
                devices = data.get("devices", [])
                
                # Фильтруем устаревшие
                cutoff_time = datetime.now() - timedelta(seconds=ttl)
                filtered = []
                
                for device in devices:
                    discovered_at = device.get("discovered_at")
                    if discovered_at:
                        device_time = datetime.fromisoformat(discovered_at)
                        if device_time > cutoff_time or device.get("added", False):
                            filtered.append(device)
                    else:
                        filtered.append(device)
                
                # Сохраняем если были изменения
                if len(filtered) != len(devices):
                    data["devices"] = filtered
                    with open(self.discovered_path, 'w') as f:
                        json.dump(data, f, indent=2)
                    logger.info(f"Cleaned up {len(devices) - len(filtered)} old devices")
                    
            except Exception as e:
                logger.error(f"Error in cleanup worker: {e}")
    
    def start(self):
        """Запуск Discovery Manager"""
        logger.info("Starting Discovery Manager")
        
        # Настройка MQTT
        self._setup_mqtt()
        
        # Запуск потоков
        self.running.set()
        
        if self.config["auto_discovery"].get("enabled", True):
            self.discovery_thread = Thread(target=self._discovery_worker, daemon=True)
            self.discovery_thread.start()
            logger.info("Discovery worker started")
        
        self.cleanup_thread = Thread(target=self._cleanup_worker, daemon=True)
        self.cleanup_thread.start()
        logger.info("Cleanup worker started")
    
    def stop(self):
        """Остановка Discovery Manager"""
        logger.info("Stopping Discovery Manager")
        self.running.clear()
        
        if self.discovery_thread:
            self.discovery_thread.join(timeout=5)
        
        if self.cleanup_thread:
            self.cleanup_thread.join(timeout=5)
        
        if self.mqtt_client:
            self.mqtt_client.loop_stop()
            self.mqtt_client.disconnect()
        
        logger.info("Discovery Manager stopped")
    
    def run_single_discovery(self, integration: str) -> List[Dict[str, Any]]:
        """Запуск discovery для одной интеграции (для API)"""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        return loop.run_until_complete(self._run_discovery_for_integration(integration))


def signal_handler(signum, frame):
    """Обработчик сигналов для graceful shutdown"""
    logger.info(f"Received signal {signum}")
    if manager:
        manager.stop()
    sys.exit(0)


if __name__ == "__main__":
    # Обработка сигналов
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Запуск менеджера
    manager = DiscoveryManager()
    manager.start()
    
    # Ожидание
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        manager.stop()