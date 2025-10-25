"""
HomeKit Characteristics Command Mapping
Maps IoT2mqtt commands to HomeKit characteristic writes
"""

import logging
from typing import Dict, Any, List, Tuple, Optional

from entity_mapper import CharacteristicTypes

logger = logging.getLogger(__name__)


class CharacteristicCommandMapper:
    """Maps IoT2mqtt commands to HomeKit characteristic writes"""

    def __init__(self):
        """Initialize command mapper"""
        pass

    def map_command_to_characteristics(
        self,
        command: Dict[str, Any],
        accessories: List[Dict[str, Any]],
        platform: str = None
    ) -> List[Dict[str, Any]]:
        """
        Map IoT2mqtt command to HomeKit characteristics

        Args:
            command: Command dictionary from MQTT
            accessories: Accessories structure
            platform: Optional platform hint (light, switch, etc.)

        Returns:
            List of characteristics to write: [{"aid": 1, "iid": 11, "value": true}, ...]
        """
        characteristics_to_write = []

        # Build characteristic lookup by type
        char_by_type = self._build_type_lookup(accessories)

        # Process each command field
        for field, value in command.items():
            char_writes = self._map_field_to_characteristics(
                field, value, char_by_type, platform
            )
            characteristics_to_write.extend(char_writes)

        return characteristics_to_write

    def _build_type_lookup(
        self,
        accessories: List[Dict[str, Any]]
    ) -> Dict[str, List[Tuple[int, int]]]:
        """
        Build lookup of characteristic type to (aid, iid) list

        Args:
            accessories: Accessories structure

        Returns:
            Dict of {char_type_uuid: [(aid, iid), ...]}
        """
        lookup = {}

        for accessory in accessories:
            aid = accessory.get('aid')
            for service in accessory.get('services', []):
                for char in service.get('characteristics', []):
                    iid = char.get('iid')
                    char_type = char.get('type', '').upper()
                    perms = char.get('perms', [])

                    # Only include writable characteristics
                    if 'pw' not in perms:
                        continue

                    if char_type not in lookup:
                        lookup[char_type] = []

                    lookup[char_type].append((aid, iid))

        return lookup

    def _map_field_to_characteristics(
        self,
        field: str,
        value: Any,
        char_by_type: Dict[str, List[Tuple[int, int]]],
        platform: str = None
    ) -> List[Dict[str, Any]]:
        """
        Map single command field to characteristics

        Args:
            field: Field name (e.g., "power", "brightness")
            value: Field value
            char_by_type: Characteristic type lookup
            platform: Platform hint

        Returns:
            List of characteristic writes
        """
        writes = []

        # Light commands
        if field == "power" and platform in ["light", "switch", "fan", None]:
            aids_iids = char_by_type.get(CharacteristicTypes.ON.upper(), [])
            for aid, iid in aids_iids:
                writes.append({"aid": aid, "iid": iid, "value": bool(value)})

        elif field == "brightness" and platform in ["light", None]:
            aids_iids = char_by_type.get(CharacteristicTypes.BRIGHTNESS.upper(), [])
            for aid, iid in aids_iids:
                writes.append({"aid": aid, "iid": iid, "value": int(value)})

        elif field == "hue" and platform in ["light", None]:
            aids_iids = char_by_type.get(CharacteristicTypes.HUE.upper(), [])
            for aid, iid in aids_iids:
                writes.append({"aid": aid, "iid": iid, "value": float(value)})

        elif field == "saturation" and platform in ["light", None]:
            aids_iids = char_by_type.get(CharacteristicTypes.SATURATION.upper(), [])
            for aid, iid in aids_iids:
                writes.append({"aid": aid, "iid": iid, "value": float(value)})

        elif field == "color_temp" and platform in ["light", None]:
            aids_iids = char_by_type.get(CharacteristicTypes.COLOR_TEMPERATURE.upper(), [])
            for aid, iid in aids_iids:
                writes.append({"aid": aid, "iid": iid, "value": int(value)})

        # Climate commands
        elif field == "target_temperature" and platform in ["climate", None]:
            aids_iids = char_by_type.get(CharacteristicTypes.TARGET_TEMPERATURE.upper(), [])
            for aid, iid in aids_iids:
                writes.append({"aid": aid, "iid": iid, "value": float(value)})

        elif field == "target_humidity" and platform in ["climate", None]:
            aids_iids = char_by_type.get(CharacteristicTypes.TARGET_RELATIVE_HUMIDITY.upper(), [])
            for aid, iid in aids_iids:
                writes.append({"aid": aid, "iid": iid, "value": float(value)})

        elif field == "hvac_mode" and platform in ["climate", None]:
            # Map mode string to HomeKit value
            mode_map = {"off": 0, "heat": 1, "cool": 2, "auto": 3}
            hap_value = mode_map.get(value, 0)

            aids_iids = char_by_type.get(CharacteristicTypes.TARGET_HEATING_COOLING_STATE.upper(), [])
            for aid, iid in aids_iids:
                writes.append({"aid": aid, "iid": iid, "value": hap_value})

        # Lock commands
        elif field == "lock" and platform in ["lock", None]:
            # True = lock, False = unlock
            # HomeKit: 0=Unsecured, 1=Secured
            hap_value = 1 if value else 0

            aids_iids = char_by_type.get(CharacteristicTypes.LOCK_TARGET_STATE.upper(), [])
            for aid, iid in aids_iids:
                writes.append({"aid": aid, "iid": iid, "value": hap_value})

        # Cover commands
        elif field == "position" and platform in ["cover", None]:
            aids_iids = char_by_type.get(CharacteristicTypes.TARGET_POSITION.upper(), [])
            for aid, iid in aids_iids:
                writes.append({"aid": aid, "iid": iid, "value": int(value)})

        elif field in ["open", "close", "stop"] and platform in ["cover", None]:
            # Special commands for covers
            if field == "open":
                target_position = 100
            elif field == "close":
                target_position = 0
            else:  # stop
                # For stop, we need to use HOLD_POSITION if available
                # Otherwise, set to current position (no-op)
                target_position = None

            if target_position is not None:
                aids_iids = char_by_type.get(CharacteristicTypes.TARGET_POSITION.upper(), [])
                for aid, iid in aids_iids:
                    writes.append({"aid": aid, "iid": iid, "value": target_position})

        # Fan commands
        elif field == "active" and platform in ["fan", None]:
            aids_iids = char_by_type.get(CharacteristicTypes.ACTIVE.upper(), [])
            for aid, iid in aids_iids:
                writes.append({"aid": aid, "iid": iid, "value": bool(value)})

        elif field == "speed" and platform in ["fan", None]:
            aids_iids = char_by_type.get(CharacteristicTypes.ROTATION_SPEED.upper(), [])
            for aid, iid in aids_iids:
                writes.append({"aid": aid, "iid": iid, "value": int(value)})

        elif field == "direction" and platform in ["fan", None]:
            # "forward" = 0, "reverse" = 1
            hap_value = 1 if value == "reverse" else 0

            aids_iids = char_by_type.get(CharacteristicTypes.ROTATION_DIRECTION.upper(), [])
            for aid, iid in aids_iids:
                writes.append({"aid": aid, "iid": iid, "value": hap_value})

        elif field == "swing" and platform in ["fan", None]:
            aids_iids = char_by_type.get(CharacteristicTypes.SWING_MODE.upper(), [])
            for aid, iid in aids_iids:
                writes.append({"aid": aid, "iid": iid, "value": bool(value)})

        return writes

    def get_readable_characteristics(
        self,
        accessories: List[Dict[str, Any]]
    ) -> List[Tuple[int, int]]:
        """
        Get all readable characteristics (aid, iid) from accessories

        Args:
            accessories: Accessories structure

        Returns:
            List of (aid, iid) tuples for readable characteristics
        """
        readable = []

        for accessory in accessories:
            aid = accessory.get('aid')
            for service in accessory.get('services', []):
                for char in service.get('characteristics', []):
                    iid = char.get('iid')
                    perms = char.get('perms', [])

                    # Only include readable characteristics
                    if 'pr' in perms:
                        readable.append((aid, iid))

        return readable

    def get_writable_characteristics(
        self,
        accessories: List[Dict[str, Any]]
    ) -> List[Tuple[int, int]]:
        """
        Get all writable characteristics (aid, iid) from accessories

        Args:
            accessories: Accessories structure

        Returns:
            List of (aid, iid) tuples for writable characteristics
        """
        writable = []

        for accessory in accessories:
            aid = accessory.get('aid')
            for service in accessory.get('services', []):
                for char in service.get('characteristics', []):
                    iid = char.get('iid')
                    perms = char.get('perms', [])

                    # Only include writable characteristics
                    if 'pw' in perms:
                        writable.append((aid, iid))

        return writable

    def get_event_characteristics(
        self,
        accessories: List[Dict[str, Any]]
    ) -> List[Tuple[int, int]]:
        """
        Get all event-capable characteristics (aid, iid) from accessories

        Args:
            accessories: Accessories structure

        Returns:
            List of (aid, iid) tuples for event characteristics
        """
        event_chars = []

        for accessory in accessories:
            aid = accessory.get('aid')
            for service in accessory.get('services', []):
                for char in service.get('characteristics', []):
                    iid = char.get('iid')
                    perms = char.get('perms', [])

                    # Only include event-capable characteristics
                    if 'ev' in perms:
                        event_chars.append((aid, iid))

        return event_chars
