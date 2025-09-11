#!/usr/bin/env python3
"""
Тесты для Discovery Manager
"""

import unittest
import json
import tempfile
import os
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock, call
from datetime import datetime, timedelta
import asyncio

# Импортируем тестируемый модуль
import sys
sys.path.insert(0, str(Path(__file__).parent))
from discovery_manager import DiscoveryManager


class TestDiscoveryManager(unittest.TestCase):
    """Тесты для Discovery Manager"""
    
    def setUp(self):
        """Подготовка к тестам"""
        # Создаем временные файлы
        self.config_file = tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False)
        self.discovered_file = tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False)
        
        # Тестовая конфигурация
        self.test_config = {
            "auto_discovery": {
                "enabled": True,
                "interval": 300,
                "on_startup": True,
                "startup_delay": 1,
                "integrations": ["yeelight", "test_integration"],
                "parallel": True,
                "timeout_per_integration": 30
            },
            "retention": {
                "discovered_devices_ttl": 86400,
                "cleanup_interval": 3600
            },
            "docker": {
                "network_mode": "host",
                "memory_limit": "50m",
                "cpu_shares": 256,
                "read_only": True,
                "no_new_privileges": True
            }
        }
        
        # Записываем конфигурацию
        json.dump(self.test_config, self.config_file)
        self.config_file.close()
        
        # Пустой файл discovered
        json.dump({"devices": []}, self.discovered_file)
        self.discovered_file.close()
        
        # Создаем менеджер с тестовыми путями
        with patch('discovery_manager.docker.from_env'):
            self.manager = DiscoveryManager(self.config_file.name)
            self.manager.discovered_path = Path(self.discovered_file.name)
    
    def tearDown(self):
        """Очистка после тестов"""
        os.unlink(self.config_file.name)
        os.unlink(self.discovered_file.name)
    
    def test_load_config(self):
        """Тест загрузки конфигурации"""
        self.assertEqual(self.manager.config, self.test_config)
        self.assertTrue(self.manager.config["auto_discovery"]["enabled"])
        self.assertEqual(len(self.manager.config["auto_discovery"]["integrations"]), 2)
    
    def test_save_discovered(self):
        """Тест сохранения найденных устройств"""
        test_devices = [
            {
                "id": "yeelight_192_168_1_100",
                "name": "Test Bulb",
                "ip": "192.168.1.100",
                "integration": "yeelight"
            },
            {
                "id": "test_device_1",
                "name": "Test Device",
                "ip": "192.168.1.101",
                "integration": "test_integration"
            }
        ]
        
        self.manager._save_discovered(test_devices)
        
        # Проверяем сохранение
        with open(self.discovered_file.name, 'r') as f:
            saved_data = json.load(f)
        
        self.assertEqual(len(saved_data["devices"]), 2)
        self.assertIsNotNone(saved_data["last_scan"])
        self.assertEqual(saved_data["devices"][0]["id"], "yeelight_192_168_1_100")
        self.assertIn("discovered_at", saved_data["devices"][0])
    
    def test_load_discovered(self):
        """Тест загрузки сохраненных устройств"""
        test_data = {
            "last_scan": datetime.now().isoformat(),
            "devices": [
                {
                    "id": "test_device",
                    "name": "Test",
                    "discovered_at": datetime.now().isoformat(),
                    "added": False
                }
            ]
        }
        
        with open(self.discovered_file.name, 'w') as f:
            json.dump(test_data, f)
        
        loaded = self.manager._load_discovered()
        self.assertEqual(len(loaded["devices"]), 1)
        self.assertEqual(loaded["devices"][0]["id"], "test_device")
    
    @patch('discovery_manager.mqtt.Client')
    def test_setup_mqtt(self, mock_mqtt_client):
        """Тест настройки MQTT клиента"""
        mock_client = MagicMock()
        mock_mqtt_client.return_value = mock_client
        
        with patch.dict(os.environ, {
            'MQTT_HOST': 'test_host',
            'MQTT_PORT': '1883',
            'MQTT_USERNAME': 'test_user',
            'MQTT_PASSWORD': 'test_pass'
        }):
            self.manager._setup_mqtt()
        
        mock_client.username_pw_set.assert_called_once_with('test_user', 'test_pass')
        mock_client.connect.assert_called_once_with('test_host', 1883, 60)
        mock_client.loop_start.assert_called_once()
    
    @patch('discovery_manager.mqtt.Client')
    def test_publish_discovered(self, mock_mqtt_client):
        """Тест публикации в MQTT"""
        mock_client = MagicMock()
        self.manager.mqtt_client = mock_client
        
        test_devices = [
            {"id": "device1", "name": "Device 1"},
            {"id": "device2", "name": "Device 2"}
        ]
        
        with patch.dict(os.environ, {'MQTT_BASE_TOPIC': 'TestTopic'}):
            self.manager._publish_discovered(test_devices)
        
        # Проверяем вызов publish
        mock_client.publish.assert_called_once()
        args = mock_client.publish.call_args[0]
        self.assertEqual(args[0], "TestTopic/v1/discovery/devices")
        
        # Проверяем payload
        payload = json.loads(args[1])
        self.assertEqual(payload["total"], 2)
        self.assertEqual(len(payload["devices"]), 2)
        self.assertIn("timestamp", payload)
    
    @patch('discovery_manager.docker')
    async def test_run_discovery_for_integration(self, mock_docker):
        """Тест запуска discovery для одной интеграции"""
        # Мокаем манифест
        manifest = {
            "discovery": {
                "supported": True,
                "timeout": 10,
                "network_mode": "host",
                "command": "python discovery.py"
            }
        }
        
        # Мокаем контейнер
        mock_container = MagicMock()
        mock_container.status = "exited"
        mock_container.logs.return_value = b'[{"id": "device1", "name": "Test Device"}]'
        
        self.manager.docker_client.containers.run.return_value = mock_container
        
        with patch('builtins.open', create=True) as mock_open:
            mock_open.return_value.__enter__.return_value.read.return_value = json.dumps(manifest)
            with patch('pathlib.Path.exists', return_value=True):
                devices = await self.manager._run_discovery_for_integration("test_integration")
        
        self.assertEqual(len(devices), 1)
        self.assertEqual(devices[0]["id"], "device1")
        mock_container.remove.assert_called_once_with(force=True)
    
    def test_cleanup_old_devices(self):
        """Тест очистки устаревших устройств"""
        # Создаем устройства с разными временными метками
        old_time = (datetime.now() - timedelta(days=2)).isoformat()
        recent_time = datetime.now().isoformat()
        
        test_data = {
            "devices": [
                {
                    "id": "old_device",
                    "discovered_at": old_time,
                    "added": False
                },
                {
                    "id": "recent_device",
                    "discovered_at": recent_time,
                    "added": False
                },
                {
                    "id": "added_device",
                    "discovered_at": old_time,
                    "added": True  # Добавленные не удаляются
                }
            ]
        }
        
        with open(self.discovered_file.name, 'w') as f:
            json.dump(test_data, f)
        
        # Запускаем очистку с TTL = 1 день
        self.manager.config["retention"]["discovered_devices_ttl"] = 86400
        self.manager.running.set()
        
        # Симулируем работу cleanup_worker
        data = self.manager._load_discovered()
        devices = data.get("devices", [])
        
        cutoff_time = datetime.now() - timedelta(seconds=86400)
        filtered = []
        
        for device in devices:
            discovered_at = device.get("discovered_at")
            if discovered_at:
                device_time = datetime.fromisoformat(discovered_at)
                if device_time > cutoff_time or device.get("added", False):
                    filtered.append(device)
        
        # Проверяем результат
        self.assertEqual(len(filtered), 2)  # recent_device и added_device
        device_ids = [d["id"] for d in filtered]
        self.assertIn("recent_device", device_ids)
        self.assertIn("added_device", device_ids)
        self.assertNotIn("old_device", device_ids)
    
    def test_deduplication(self):
        """Тест дедупликации устройств"""
        # Сохраняем первую партию
        first_batch = [
            {"id": "device1", "name": "Device 1", "ip": "192.168.1.1"},
            {"id": "device2", "name": "Device 2", "ip": "192.168.1.2"}
        ]
        self.manager._save_discovered(first_batch)
        
        # Сохраняем вторую партию с дубликатом
        second_batch = [
            {"id": "device1", "name": "Device 1 Updated", "ip": "192.168.1.1"},  # Обновленное
            {"id": "device3", "name": "Device 3", "ip": "192.168.1.3"}  # Новое
        ]
        self.manager._save_discovered(second_batch)
        
        # Проверяем результат
        with open(self.discovered_file.name, 'r') as f:
            saved_data = json.load(f)
        
        self.assertEqual(len(saved_data["devices"]), 3)  # Всего 3 уникальных устройства
        
        # Проверяем что device1 обновлен
        device1 = next(d for d in saved_data["devices"] if d["id"] == "device1")
        self.assertEqual(device1["name"], "Device 1 Updated")
    
    @patch('discovery_manager.Thread')
    def test_start_stop(self, mock_thread):
        """Тест запуска и остановки менеджера"""
        mock_discovery_thread = MagicMock()
        mock_cleanup_thread = MagicMock()
        mock_thread.side_effect = [mock_discovery_thread, mock_cleanup_thread]
        
        with patch.object(self.manager, '_setup_mqtt'):
            self.manager.start()
        
        self.assertTrue(self.manager.running.is_set())
        self.assertEqual(mock_thread.call_count, 2)
        mock_discovery_thread.start.assert_called_once()
        mock_cleanup_thread.start.assert_called_once()
        
        # Тест остановки
        self.manager.discovery_thread = mock_discovery_thread
        self.manager.cleanup_thread = mock_cleanup_thread
        self.manager.stop()
        
        self.assertFalse(self.manager.running.is_set())
        mock_discovery_thread.join.assert_called_once_with(timeout=5)
        mock_cleanup_thread.join.assert_called_once_with(timeout=5)


class TestDiscoveryIntegration(unittest.TestCase):
    """Интеграционные тесты"""
    
    @patch('discovery_manager.docker.from_env')
    @patch('discovery_manager.mqtt.Client')
    def test_full_discovery_cycle(self, mock_mqtt, mock_docker):
        """Тест полного цикла discovery"""
        # Подготовка
        config_file = tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False)
        discovered_file = tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False)
        
        config = {
            "auto_discovery": {
                "enabled": True,
                "interval": 5,
                "on_startup": True,
                "startup_delay": 0,
                "integrations": ["yeelight"],
                "parallel": False
            },
            "retention": {
                "discovered_devices_ttl": 10,
                "cleanup_interval": 5
            },
            "docker": {}
        }
        
        json.dump(config, config_file)
        config_file.close()
        json.dump({"devices": []}, discovered_file)
        discovered_file.close()
        
        try:
            # Создаем менеджер
            manager = DiscoveryManager(config_file.name)
            manager.discovered_path = Path(discovered_file.name)
            
            # Мокаем Docker
            mock_container = MagicMock()
            mock_container.status = "exited"
            mock_container.logs.return_value = b'[{"id": "test_device", "name": "Test"}]'
            mock_docker.return_value.containers.run.return_value = mock_container
            
            # Мокаем манифест
            with patch('pathlib.Path.exists', return_value=True):
                with patch('builtins.open', create=True) as mock_open:
                    manifest = {
                        "discovery": {
                            "supported": True,
                            "timeout": 1,
                            "command": "test"
                        }
                    }
                    mock_open.return_value.__enter__.return_value.read.return_value = json.dumps(manifest)
                    
                    # Запускаем discovery
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    loop.run_until_complete(manager._run_discovery_cycle())
            
            # Проверяем результат
            with open(discovered_file.name, 'r') as f:
                result = json.load(f)
            
            self.assertEqual(len(result["devices"]), 1)
            self.assertEqual(result["devices"][0]["id"], "test_device")
            
        finally:
            os.unlink(config_file.name)
            os.unlink(discovered_file.name)


if __name__ == '__main__':
    unittest.main()