"""
Xiaomi MiIO Connector for IoT2MQTT
Complete integration for all Xiaomi MiIO devices
"""

__version__ = "1.0.0"
__author__ = "IoT2MQTT"

from .connector import Connector
from .device_registry import DeviceRegistry, get_device_class
from .command_translator import CommandTranslator
from .coordinators import DeviceCoordinator, VacuumCoordinator
from .discovery import XiaomiDiscovery
from .cloud_client import MiCloudClient

__all__ = [
    'Connector',
    'DeviceRegistry',
    'get_device_class',
    'CommandTranslator',
    'DeviceCoordinator',
    'VacuumCoordinator',
    'XiaomiDiscovery',
    'MiCloudClient'
]