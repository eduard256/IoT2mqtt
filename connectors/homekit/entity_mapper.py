"""
HomeKit Entity Mapper
Maps HomeKit accessories and characteristics to IoT2mqtt device state
"""

import logging
from typing import Dict, Any, List, Optional, Set

logger = logging.getLogger(__name__)


# HomeKit Service Type UUIDs (from HAP spec)
class ServiceTypes:
    """HomeKit service type identifiers"""
    ACCESSORY_INFORMATION = "0000003E-0000-1000-8000-0026BB765291"
    LIGHTBULB = "00000043-0000-1000-8000-0026BB765291"
    SWITCH = "00000049-0000-1000-8000-0026BB765291"
    OUTLET = "00000047-0000-1000-8000-0026BB765291"
    THERMOSTAT = "0000004A-0000-1000-8000-0026BB765291"
    HEATER_COOLER = "000000BC-0000-1000-8000-0026BB765291"
    TEMPERATURE_SENSOR = "0000008A-0000-1000-8000-0026BB765291"
    HUMIDITY_SENSOR = "00000082-0000-1000-8000-0026BB765291"
    LIGHT_SENSOR = "00000084-0000-1000-8000-0026BB765291"
    AIR_QUALITY_SENSOR = "0000008D-0000-1000-8000-0026BB765291"
    MOTION_SENSOR = "00000085-0000-1000-8000-0026BB765291"
    CONTACT_SENSOR = "00000080-0000-1000-8000-0026BB765291"
    LEAK_SENSOR = "00000083-0000-1000-8000-0026BB765291"
    SMOKE_SENSOR = "00000087-0000-1000-8000-0026BB765291"
    CARBON_MONOXIDE_SENSOR = "0000007F-0000-1000-8000-0026BB765291"
    OCCUPANCY_SENSOR = "00000086-0000-1000-8000-0026BB765291"
    LOCK_MECHANISM = "00000045-0000-1000-8000-0026BB765291"
    DOOR = "00000081-0000-1000-8000-0026BB765291"
    WINDOW = "0000008B-0000-1000-8000-0026BB765291"
    WINDOW_COVERING = "0000008C-0000-1000-8000-0026BB765291"
    GARAGE_DOOR_OPENER = "00000041-0000-1000-8000-0026BB765291"
    FAN = "00000040-0000-1000-8000-0026BB765291"
    AIR_PURIFIER = "000000BB-0000-1000-8000-0026BB765291"
    BATTERY_SERVICE = "00000096-0000-1000-8000-0026BB765291"
    STATELESS_PROGRAMMABLE_SWITCH = "00000089-0000-1000-8000-0026BB765291"
    DOORBELL = "00000121-0000-1000-8000-0026BB765291"


# HomeKit Characteristic Type UUIDs
class CharacteristicTypes:
    """HomeKit characteristic type identifiers"""
    # Light
    ON = "00000025-0000-1000-8000-0026BB765291"
    BRIGHTNESS = "00000008-0000-1000-8000-0026BB765291"
    HUE = "00000013-0000-1000-8000-0026BB765291"
    SATURATION = "0000002F-0000-1000-8000-0026BB765291"
    COLOR_TEMPERATURE = "000000CE-0000-1000-8000-0026BB765291"

    # Temperature
    CURRENT_TEMPERATURE = "00000011-0000-1000-8000-0026BB765291"
    TARGET_TEMPERATURE = "00000035-0000-1000-8000-0026BB765291"
    TEMPERATURE_DISPLAY_UNITS = "00000036-0000-1000-8000-0026BB765291"

    # Humidity
    CURRENT_RELATIVE_HUMIDITY = "00000010-0000-1000-8000-0026BB765291"
    TARGET_RELATIVE_HUMIDITY = "00000034-0000-1000-8000-0026BB765291"

    # Climate
    CURRENT_HEATING_COOLING_STATE = "0000000F-0000-1000-8000-0026BB765291"
    TARGET_HEATING_COOLING_STATE = "00000033-0000-1000-8000-0026BB765291"
    HEATING_THRESHOLD_TEMPERATURE = "00000012-0000-1000-8000-0026BB765291"
    COOLING_THRESHOLD_TEMPERATURE = "0000000D-0000-1000-8000-0026BB765291"

    # Lock
    LOCK_CURRENT_STATE = "0000001D-0000-1000-8000-0026BB765291"
    LOCK_TARGET_STATE = "0000001E-0000-1000-8000-0026BB765291"

    # Door/Window
    CURRENT_DOOR_STATE = "0000000E-0000-1000-8000-0026BB765291"
    TARGET_DOOR_STATE = "00000032-0000-1000-8000-0026BB765291"
    CURRENT_POSITION = "0000006D-0000-1000-8000-0026BB765291"
    TARGET_POSITION = "0000007C-0000-1000-8000-0026BB765291"
    POSITION_STATE = "00000072-0000-1000-8000-0026BB765291"

    # Fan
    ACTIVE = "000000B0-0000-1000-8000-0026BB765291"
    ROTATION_SPEED = "00000029-0000-1000-8000-0026BB765291"
    ROTATION_DIRECTION = "00000028-0000-1000-8000-0026BB765291"
    SWING_MODE = "000000B6-0000-1000-8000-0026BB765291"

    # Sensors
    MOTION_DETECTED = "00000022-0000-1000-8000-0026BB765291"
    CONTACT_SENSOR_STATE = "0000006A-0000-1000-8000-0026BB765291"
    LEAK_DETECTED = "00000070-0000-1000-8000-0026BB765291"
    SMOKE_DETECTED = "00000076-0000-1000-8000-0026BB765291"
    CARBON_MONOXIDE_DETECTED = "00000069-0000-1000-8000-0026BB765291"
    OCCUPANCY_DETECTED = "00000071-0000-1000-8000-0026BB765291"
    CURRENT_AMBIENT_LIGHT_LEVEL = "0000006B-0000-1000-8000-0026BB765291"
    AIR_QUALITY = "00000095-0000-1000-8000-0026BB765291"

    # Battery
    BATTERY_LEVEL = "00000068-0000-1000-8000-0026BB765291"
    CHARGING_STATE = "0000008F-0000-1000-8000-0026BB765291"
    STATUS_LOW_BATTERY = "00000079-0000-1000-8000-0026BB765291"

    # Device Information
    MANUFACTURER = "00000020-0000-1000-8000-0026BB765291"
    MODEL = "00000021-0000-1000-8000-0026BB765291"
    SERIAL_NUMBER = "00000030-0000-1000-8000-0026BB765291"
    FIRMWARE_REVISION = "00000052-0000-1000-8000-0026BB765291"


# Service Type to Platform mapping
HOMEKIT_ACCESSORY_DISPATCH = {
    ServiceTypes.LIGHTBULB: "light",
    ServiceTypes.SWITCH: "switch",
    ServiceTypes.OUTLET: "switch",
    ServiceTypes.THERMOSTAT: "climate",
    ServiceTypes.HEATER_COOLER: "climate",
    ServiceTypes.TEMPERATURE_SENSOR: "sensor",
    ServiceTypes.HUMIDITY_SENSOR: "sensor",
    ServiceTypes.LIGHT_SENSOR: "sensor",
    ServiceTypes.AIR_QUALITY_SENSOR: "sensor",
    ServiceTypes.BATTERY_SERVICE: "sensor",
    ServiceTypes.MOTION_SENSOR: "binary_sensor",
    ServiceTypes.CONTACT_SENSOR: "binary_sensor",
    ServiceTypes.LEAK_SENSOR: "binary_sensor",
    ServiceTypes.SMOKE_SENSOR: "binary_sensor",
    ServiceTypes.CARBON_MONOXIDE_SENSOR: "binary_sensor",
    ServiceTypes.OCCUPANCY_SENSOR: "binary_sensor",
    ServiceTypes.LOCK_MECHANISM: "lock",
    ServiceTypes.DOOR: "cover",
    ServiceTypes.WINDOW: "cover",
    ServiceTypes.WINDOW_COVERING: "cover",
    ServiceTypes.GARAGE_DOOR_OPENER: "cover",
    ServiceTypes.FAN: "fan",
    ServiceTypes.AIR_PURIFIER: "fan",
}


class EntityMapper:
    """Maps HomeKit accessories to IoT2mqtt device state"""

    def __init__(self):
        """Initialize entity mapper"""
        pass

    def map_characteristics_to_state(
        self,
        characteristics: Dict[str, Any],
        accessories: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Map characteristic values to IoT2mqtt state

        Args:
            characteristics: Dict of {aid.iid: value}
            accessories: Accessories structure

        Returns:
            IoT2mqtt state dictionary
        """
        state = {"online": True}

        # Build reverse lookup: (aid, iid) -> characteristic metadata
        char_lookup = self._build_characteristic_lookup(accessories)

        # Process each characteristic value
        for key, value in characteristics.items():
            aid_iid = key.split('.')
            if len(aid_iid) != 2:
                continue

            try:
                aid = int(aid_iid[0])
                iid = int(aid_iid[1])
            except ValueError:
                continue

            char_meta = char_lookup.get((aid, iid))
            if not char_meta:
                continue

            char_type = char_meta.get('type', '').upper()

            # Map characteristic to state field
            self._map_characteristic_value(state, char_type, value, char_meta)

        return state

    def _build_characteristic_lookup(
        self,
        accessories: List[Dict[str, Any]]
    ) -> Dict[tuple, Dict[str, Any]]:
        """
        Build lookup dict for characteristics

        Args:
            accessories: Accessories structure

        Returns:
            Dict of {(aid, iid): characteristic_metadata}
        """
        lookup = {}

        for accessory in accessories:
            aid = accessory.get('aid')
            for service in accessory.get('services', []):
                for char in service.get('characteristics', []):
                    iid = char.get('iid')
                    if aid is not None and iid is not None:
                        lookup[(aid, iid)] = char

        return lookup

    def _map_characteristic_value(
        self,
        state: Dict[str, Any],
        char_type: str,
        value: Any,
        char_meta: Dict[str, Any]
    ):
        """
        Map single characteristic value to state

        Args:
            state: State dictionary to update
            char_type: Characteristic type UUID
            value: Characteristic value
            char_meta: Characteristic metadata
        """
        # Light characteristics
        if CharacteristicTypes.ON.upper() in char_type:
            state['power'] = bool(value)

        elif CharacteristicTypes.BRIGHTNESS.upper() in char_type:
            state['brightness'] = int(value) if value is not None else 0

        elif CharacteristicTypes.HUE.upper() in char_type:
            state['hue'] = float(value) if value is not None else 0

        elif CharacteristicTypes.SATURATION.upper() in char_type:
            state['saturation'] = float(value) if value is not None else 0

        elif CharacteristicTypes.COLOR_TEMPERATURE.upper() in char_type:
            state['color_temp'] = int(value) if value is not None else 0

        # Temperature
        elif CharacteristicTypes.CURRENT_TEMPERATURE.upper() in char_type:
            state['current_temperature'] = float(value) if value is not None else 0

        elif CharacteristicTypes.TARGET_TEMPERATURE.upper() in char_type:
            state['target_temperature'] = float(value) if value is not None else 0

        # Humidity
        elif CharacteristicTypes.CURRENT_RELATIVE_HUMIDITY.upper() in char_type:
            state['current_humidity'] = float(value) if value is not None else 0

        elif CharacteristicTypes.TARGET_RELATIVE_HUMIDITY.upper() in char_type:
            state['target_humidity'] = float(value) if value is not None else 0

        # Climate
        elif CharacteristicTypes.CURRENT_HEATING_COOLING_STATE.upper() in char_type:
            # 0=Off, 1=Heat, 2=Cool
            mode_map = {0: "off", 1: "heat", 2: "cool"}
            state['hvac_action'] = mode_map.get(value, "off")

        elif CharacteristicTypes.TARGET_HEATING_COOLING_STATE.upper() in char_type:
            # 0=Off, 1=Heat, 2=Cool, 3=Auto
            mode_map = {0: "off", 1: "heat", 2: "cool", 3: "auto"}
            state['hvac_mode'] = mode_map.get(value, "off")

        # Lock
        elif CharacteristicTypes.LOCK_CURRENT_STATE.upper() in char_type:
            # 0=Unsecured, 1=Secured, 2=Jammed, 3=Unknown
            state['locked'] = (value == 1)
            state['jammed'] = (value == 2)

        elif CharacteristicTypes.LOCK_TARGET_STATE.upper() in char_type:
            state['lock_target'] = (value == 1)

        # Position (covers)
        elif CharacteristicTypes.CURRENT_POSITION.upper() in char_type:
            state['position'] = int(value) if value is not None else 0

        elif CharacteristicTypes.TARGET_POSITION.upper() in char_type:
            state['target_position'] = int(value) if value is not None else 0

        elif CharacteristicTypes.POSITION_STATE.upper() in char_type:
            # 0=Going to min, 1=Going to max, 2=Stopped
            state_map = {0: "closing", 1: "opening", 2: "stopped"}
            state['position_state'] = state_map.get(value, "stopped")

        # Fan
        elif CharacteristicTypes.ACTIVE.upper() in char_type:
            state['active'] = bool(value)

        elif CharacteristicTypes.ROTATION_SPEED.upper() in char_type:
            state['speed'] = int(value) if value is not None else 0

        elif CharacteristicTypes.ROTATION_DIRECTION.upper() in char_type:
            # 0=Clockwise, 1=Counter-clockwise
            state['direction'] = "reverse" if value == 1 else "forward"

        elif CharacteristicTypes.SWING_MODE.upper() in char_type:
            state['swing'] = bool(value)

        # Binary sensors
        elif CharacteristicTypes.MOTION_DETECTED.upper() in char_type:
            state['motion'] = bool(value)

        elif CharacteristicTypes.CONTACT_SENSOR_STATE.upper() in char_type:
            # 0=Detected (contact), 1=Not detected (no contact)
            state['contact'] = (value == 0)

        elif CharacteristicTypes.LEAK_DETECTED.upper() in char_type:
            state['leak'] = bool(value)

        elif CharacteristicTypes.SMOKE_DETECTED.upper() in char_type:
            # 0=Not detected, 1=Detected
            state['smoke'] = (value == 1)

        elif CharacteristicTypes.CARBON_MONOXIDE_DETECTED.upper() in char_type:
            # 0=Normal, 1=Abnormal
            state['carbon_monoxide'] = (value == 1)

        elif CharacteristicTypes.OCCUPANCY_DETECTED.upper() in char_type:
            state['occupancy'] = bool(value)

        # Sensors
        elif CharacteristicTypes.CURRENT_AMBIENT_LIGHT_LEVEL.upper() in char_type:
            state['illuminance'] = float(value) if value is not None else 0

        elif CharacteristicTypes.AIR_QUALITY.upper() in char_type:
            # 0=Unknown, 1=Excellent, 2=Good, 3=Fair, 4=Inferior, 5=Poor
            quality_map = {0: "unknown", 1: "excellent", 2: "good", 3: "fair", 4: "inferior", 5: "poor"}
            state['air_quality'] = quality_map.get(value, "unknown")

        # Battery
        elif CharacteristicTypes.BATTERY_LEVEL.upper() in char_type:
            state['battery_level'] = int(value) if value is not None else 0

        elif CharacteristicTypes.CHARGING_STATE.upper() in char_type:
            # 0=Not charging, 1=Charging, 2=Not chargeable
            state['charging'] = (value == 1)

        elif CharacteristicTypes.STATUS_LOW_BATTERY.upper() in char_type:
            state['low_battery'] = bool(value)

    def get_platform_for_service(self, service_type: str) -> Optional[str]:
        """
        Get IoT2mqtt platform for HomeKit service type

        Args:
            service_type: HomeKit service type UUID

        Returns:
            Platform name or None
        """
        service_type_upper = service_type.upper()

        for hap_service, platform in HOMEKIT_ACCESSORY_DISPATCH.items():
            if hap_service.upper() == service_type_upper:
                return platform

        return None

    def get_platforms_for_accessory(
        self,
        accessory: Dict[str, Any]
    ) -> Set[str]:
        """
        Get all platforms for an accessory

        Args:
            accessory: Accessory structure

        Returns:
            Set of platform names
        """
        platforms = set()

        for service in accessory.get('services', []):
            service_type = service.get('type', '')
            platform = self.get_platform_for_service(service_type)
            if platform and platform != 'accessory_information':
                platforms.add(platform)

        return platforms
