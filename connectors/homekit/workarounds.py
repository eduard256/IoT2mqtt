"""
HomeKit Device Workarounds
Device-specific fixes and workarounds from Home Assistant
"""

import logging
from typing import Dict, Any, List, Set

logger = logging.getLogger(__name__)


class DeviceWorkarounds:
    """
    Applies workarounds for buggy HomeKit devices

    Based on Home Assistant's homekit_controller component workarounds
    """

    def __init__(self):
        """Initialize workarounds manager"""
        self.applied_workarounds = {}  # device_id -> set of workaround names

    def detect_and_apply_workarounds(
        self,
        device_id: str,
        accessories: List[Dict[str, Any]],
        pairing_data: Dict[str, Any]
    ) -> Set[str]:
        """
        Detect and apply necessary workarounds for a device

        Args:
            device_id: Device identifier
            accessories: Accessories structure
            pairing_data: Pairing credentials

        Returns:
            Set of applied workaround names
        """
        workarounds = set()

        # Check for unreliable serial numbers
        if self._has_unreliable_serial(accessories):
            workarounds.add("unreliable_serial")
            logger.info(f"Device {device_id}: Applying unreliable_serial workaround")

        # Check for duplicate serial numbers
        if self._has_duplicate_serials(accessories):
            workarounds.add("duplicate_serials")
            logger.info(f"Device {device_id}: Applying duplicate_serials workaround")

        # Check for HW revision = serial bug
        if self._has_hw_revision_as_serial(accessories):
            workarounds.add("hw_revision_serial")
            logger.info(f"Device {device_id}: Applying hw_revision_serial workaround")

        # Check for broken config_num
        if self._has_broken_config_num(accessories):
            workarounds.add("broken_config_num")
            logger.info(f"Device {device_id}: Applying broken_config_num workaround")

        # Store applied workarounds
        self.applied_workarounds[device_id] = workarounds

        return workarounds

    def _has_unreliable_serial(self, accessories: List[Dict[str, Any]]) -> bool:
        """
        Check if device has unreliable serial number

        Some devices return empty or changing serial numbers

        Args:
            accessories: Accessories structure

        Returns:
            True if unreliable serial detected
        """
        for accessory in accessories:
            for service in accessory.get('services', []):
                # Look for ACCESSORY_INFORMATION service
                service_type = service.get('type', '').upper()
                if '0000003E' not in service_type:
                    continue

                for char in service.get('characteristics', []):
                    char_type = char.get('type', '').upper()

                    # Serial Number characteristic: 00000030
                    if '00000030' in char_type:
                        serial = char.get('value')

                        # Empty serial
                        if not serial or serial.strip() == '':
                            return True

                        # Generic placeholder serials
                        if serial in ['0', '00000000', 'Unknown', 'N/A', 'Default']:
                            return True

        return False

    def _has_duplicate_serials(self, accessories: List[Dict[str, Any]]) -> bool:
        """
        Check if multiple accessories have the same serial number

        Production bug in some manufacturers

        Args:
            accessories: Accessories structure

        Returns:
            True if duplicate serials detected
        """
        serials = []

        for accessory in accessories:
            for service in accessory.get('services', []):
                service_type = service.get('type', '').upper()
                if '0000003E' not in service_type:
                    continue

                for char in service.get('characteristics', []):
                    char_type = char.get('type', '').upper()

                    if '00000030' in char_type:
                        serial = char.get('value')
                        if serial:
                            serials.append(serial)

        # Check for duplicates
        return len(serials) != len(set(serials))

    def _has_hw_revision_as_serial(self, accessories: List[Dict[str, Any]]) -> bool:
        """
        Check if device uses hardware revision as serial number

        Some devices incorrectly set serial = hardware revision

        Args:
            accessories: Accessories structure

        Returns:
            True if HW revision = serial bug detected
        """
        for accessory in accessories:
            serial = None
            hw_revision = None

            for service in accessory.get('services', []):
                service_type = service.get('type', '').upper()
                if '0000003E' not in service_type:
                    continue

                for char in service.get('characteristics', []):
                    char_type = char.get('type', '').upper()

                    # Serial Number: 00000030
                    if '00000030' in char_type:
                        serial = char.get('value')

                    # Hardware Revision: 00000053
                    elif '00000053' in char_type:
                        hw_revision = char.get('value')

            # If serial == hw_revision, it's a bug
            if serial and hw_revision and serial == hw_revision:
                return True

        return False

    def _has_broken_config_num(self, accessories: List[Dict[str, Any]]) -> bool:
        """
        Check if device has broken config number tracking

        Some devices don't properly increment config_num on changes

        Args:
            accessories: Accessories structure

        Returns:
            True if broken config_num detected
        """
        # This is difficult to detect without history
        # For now, always return False
        # In practice, we'll handle this by always re-fetching accessories
        # if characteristics change unexpectedly
        return False

    def generate_unique_id(
        self,
        device_id: str,
        pairing_id: str,
        aid: int,
        iid: int,
        workarounds: Set[str]
    ) -> str:
        """
        Generate unique ID for entity with workarounds applied

        Args:
            device_id: Device identifier
            pairing_id: Pairing ID
            aid: Accessory ID
            iid: Instance ID (characteristic ID)
            workarounds: Set of applied workarounds

        Returns:
            Unique ID string
        """
        # If unreliable serial, use pairing_id as base
        if 'unreliable_serial' in workarounds:
            base = pairing_id.replace(':', '_')
        else:
            base = device_id

        # If duplicate serials, add AID suffix
        if 'duplicate_serials' in workarounds:
            return f"{base}_{aid}_{iid}"

        return f"{base}_{iid}"

    def should_skip_characteristic(
        self,
        device_id: str,
        char_type: str,
        workarounds: Set[str]
    ) -> bool:
        """
        Check if characteristic should be skipped due to workarounds

        Args:
            device_id: Device identifier
            char_type: Characteristic type UUID
            workarounds: Set of applied workarounds

        Returns:
            True if characteristic should be skipped
        """
        # Currently no characteristics are skipped
        # This is a placeholder for future workarounds
        return False

    def adjust_characteristic_value(
        self,
        device_id: str,
        char_type: str,
        value: Any,
        workarounds: Set[str]
    ) -> Any:
        """
        Adjust characteristic value if needed by workarounds

        Args:
            device_id: Device identifier
            char_type: Characteristic type UUID
            value: Original value
            workarounds: Set of applied workarounds

        Returns:
            Adjusted value
        """
        # Currently no value adjustments
        # Placeholder for future workarounds
        return value

    def get_config_num_from_accessories(
        self,
        accessories: List[Dict[str, Any]]
    ) -> int:
        """
        Extract config number from accessories

        Args:
            accessories: Accessories structure

        Returns:
            Config number (default 1 if not found)
        """
        # Config number is typically in the first accessory's info service
        # However, it's not stored in the characteristics, it's in the mDNS TXT record
        # For now, we'll track config_num separately in instance config
        return 1

    def compare_config_num(
        self,
        device_id: str,
        old_config_num: int,
        new_config_num: int
    ) -> bool:
        """
        Compare config numbers to detect accessory changes

        Args:
            device_id: Device identifier
            old_config_num: Previous config number
            new_config_num: Current config number

        Returns:
            True if config changed (need to re-fetch accessories)
        """
        if old_config_num != new_config_num:
            logger.info(f"Device {device_id}: config_num changed from {old_config_num} to {new_config_num}")
            return True

        return False

    def get_workarounds_for_device(self, device_id: str) -> Set[str]:
        """
        Get applied workarounds for a device

        Args:
            device_id: Device identifier

        Returns:
            Set of workaround names
        """
        return self.applied_workarounds.get(device_id, set())
