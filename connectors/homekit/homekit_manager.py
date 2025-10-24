"""
HomeKit Manager - Wrapper around aiohomekit library
Handles pairing, discovery, and communication with HomeKit accessories
"""

import logging
import asyncio
from typing import Dict, Any, List, Optional, Callable
from datetime import datetime

try:
    from aiohomekit import Controller
    from aiohomekit.model import Accessory
    from aiohomekit.model.characteristics import CharacteristicsTypes
    from aiohomekit.exceptions import (
        AccessoryNotFoundError,
        AuthenticationError,
        EncryptionError,
        UnknownError
    )
except ImportError:
    raise ImportError("aiohomekit library not installed. Please add 'aiohomekit' to requirements.txt")

from zeroconf.asyncio import AsyncZeroconf

logger = logging.getLogger(__name__)


class HomeKitManager:
    """
    Manages HomeKit accessories using aiohomekit
    Handles connections, pairing, state management, and events
    """

    def __init__(
        self,
        config: Dict[str, Any],
        secrets: Dict[str, Any],
        on_state_change: Callable[[str, Dict[str, Any]], None]
    ):
        """
        Initialize HomeKit Manager

        Args:
            config: Connector configuration (devices list, settings)
            secrets: Pairing data from secrets file
            on_state_change: Callback when device state changes
        """
        self.config = config
        self.secrets = secrets
        self.on_state_change = on_state_change

        # aiohomekit controller
        self.controller = Controller()

        # Device connections {device_id: pairing}
        self.pairings = {}

        # Device state cache {device_id: state}
        self.device_states = {}

        # Device accessories {device_id: accessories_and_characteristics}
        self.device_accessories = {}

        # Characteristic mapping {device_id: {characteristic_name: (aid, iid)}}
        self.char_mapping = {}

        logger.info("HomeKit Manager initialized")

    async def initialize(self):
        """Initialize all device connections"""
        logger.info("Initializing HomeKit device connections...")

        devices = self.config.get('devices', [])
        pairing_data = self.secrets.get('pairings', {})

        if not devices:
            logger.warning("No devices configured")
            return

        for device_config in devices:
            device_id = device_config.get('device_id')

            if not device_config.get('enabled', True):
                logger.info(f"Device {device_id} is disabled, skipping")
                continue

            # Load pairing for this device
            if device_id not in pairing_data:
                logger.warning(f"No pairing data found for {device_id}, skipping")
                continue

            try:
                await self._connect_device(device_id, device_config, pairing_data[device_id])
            except Exception as e:
                logger.error(f"Failed to connect to device {device_id}: {e}")

    async def _connect_device(
        self,
        device_id: str,
        device_config: Dict[str, Any],
        pairing_data: Dict[str, Any]
    ):
        """Connect to a single HomeKit device"""
        logger.info(f"Connecting to device: {device_id}")

        try:
            # Load pairing into controller
            pairing = await self.controller.load_pairing(
                alias=device_id,
                pairing_data=pairing_data
            )

            # Get accessories and characteristics
            accessories = await pairing.list_accessories_and_characteristics()

            # Store pairing and accessories
            self.pairings[device_id] = pairing
            self.device_accessories[device_id] = accessories

            # Build characteristic mapping
            self.char_mapping[device_id] = self._build_char_mapping(accessories)

            # Subscribe to events
            await self._subscribe_events(device_id, pairing)

            # Get initial state
            initial_state = await self._get_full_state(device_id)
            self.device_states[device_id] = initial_state

            logger.info(f"Successfully connected to {device_id}")
            logger.debug(f"Device {device_id} characteristics: {list(self.char_mapping[device_id].keys())}")

        except AuthenticationError as e:
            logger.error(f"Authentication failed for {device_id}: {e}. Re-pairing required.")
            raise
        except AccessoryNotFoundError as e:
            logger.error(f"Device {device_id} not found: {e}. Check IP address.")
            raise
        except Exception as e:
            logger.error(f"Error connecting to {device_id}: {e}")
            raise

    def _build_char_mapping(self, accessories: List[Accessory]) -> Dict[str, tuple]:
        """
        Build mapping of characteristic names to (aid, iid)

        Returns:
            Dict mapping characteristic names to (aid, iid) tuples
        """
        mapping = {}

        for accessory in accessories:
            aid = accessory['aid']

            for service in accessory.get('services', []):
                for char in service.get('characteristics', []):
                    iid = char['iid']
                    char_type = char.get('type')
                    char_format = char.get('format')

                    # Map common HomeKit characteristics to friendly names
                    # Based on CharacteristicsTypes from aiohomekit
                    if char_type == CharacteristicsTypes.ON:
                        mapping['on'] = (aid, iid)
                    elif char_type == CharacteristicsTypes.BRIGHTNESS:
                        mapping['brightness'] = (aid, iid)
                    elif char_type == CharacteristicsTypes.HUE:
                        mapping['hue'] = (aid, iid)
                    elif char_type == CharacteristicsTypes.SATURATION:
                        mapping['saturation'] = (aid, iid)
                    elif char_type == CharacteristicsTypes.COLOR_TEMPERATURE:
                        mapping['color_temperature'] = (aid, iid)
                    elif char_type == CharacteristicsTypes.TEMPERATURE_CURRENT:
                        mapping['current_temperature'] = (aid, iid)
                    elif char_type == CharacteristicsTypes.TARGET_TEMPERATURE:
                        mapping['target_temperature'] = (aid, iid)
                    elif char_type == CharacteristicsTypes.TARGET_HEATING_COOLING:
                        mapping['target_mode'] = (aid, iid)
                    elif char_type == CharacteristicsTypes.CURRENT_HEATING_COOLING:
                        mapping['current_mode'] = (aid, iid)
                    elif char_type == CharacteristicsTypes.LOCK_TARGET_STATE:
                        mapping['lock_target'] = (aid, iid)
                    elif char_type == CharacteristicsTypes.LOCK_CURRENT_STATE:
                        mapping['lock_current'] = (aid, iid)
                    elif char_type == CharacteristicsTypes.POSITION_CURRENT:
                        mapping['position'] = (aid, iid)
                    elif char_type == CharacteristicsTypes.POSITION_TARGET:
                        mapping['target_position'] = (aid, iid)
                    elif char_type == CharacteristicsTypes.MOTION_DETECTED:
                        mapping['motion'] = (aid, iid)
                    elif char_type == CharacteristicsTypes.CONTACT_STATE:
                        mapping['contact'] = (aid, iid)
                    elif char_type == CharacteristicsTypes.CURRENT_HUMIDITY:
                        mapping['humidity'] = (aid, iid)
                    elif char_type == CharacteristicsTypes.BATTERY_LEVEL:
                        mapping['battery'] = (aid, iid)

                    # Store raw characteristic type as well
                    mapping[f"char_{aid}_{iid}"] = (aid, iid)

        return mapping

    async def _subscribe_events(self, device_id: str, pairing):
        """Subscribe to characteristic change events"""
        try:
            # Get all characteristic IIDs to subscribe
            characteristics = []
            for char_name, (aid, iid) in self.char_mapping[device_id].items():
                if not char_name.startswith('char_'):  # Only subscribe to named characteristics
                    characteristics.append((aid, iid))

            if characteristics:
                # Set up callback
                async def callback(data):
                    await self._handle_event(device_id, data)

                # Subscribe to changes
                await pairing.subscribe(characteristics, callback)
                logger.info(f"Subscribed to {len(characteristics)} characteristics for {device_id}")
        except Exception as e:
            logger.warning(f"Failed to subscribe to events for {device_id}: {e}")

    async def _handle_event(self, device_id: str, event_data: Dict[str, Any]):
        """Handle characteristic change event"""
        logger.debug(f"Event received for {device_id}: {event_data}")

        try:
            # Update state cache
            updated_state = await self._get_full_state(device_id)
            self.device_states[device_id] = updated_state

            # Notify via callback
            if self.on_state_change:
                self.on_state_change(device_id, updated_state)

        except Exception as e:
            logger.error(f"Error handling event for {device_id}: {e}")

    async def _get_full_state(self, device_id: str) -> Dict[str, Any]:
        """Get full device state"""
        if device_id not in self.pairings:
            return {'online': False, 'error': 'Not connected'}

        pairing = self.pairings[device_id]
        char_mapping = self.char_mapping[device_id]

        try:
            # Get all characteristics
            chars_to_read = [(aid, iid) for aid, iid in char_mapping.values()]
            values = await pairing.get_characteristics(chars_to_read)

            # Build state dict
            state = {
                'online': True,
                'last_update': datetime.now().isoformat()
            }

            # Map values to friendly names
            for char_name, (aid, iid) in char_mapping.items():
                if char_name.startswith('char_'):
                    continue  # Skip raw characteristic names

                key = f"{aid}.{iid}"
                if key in values:
                    char_data = values[key]
                    state[char_name] = char_data.get('value')

            return state

        except Exception as e:
            logger.error(f"Error getting state for {device_id}: {e}")
            return {
                'online': False,
                'error': str(e),
                'last_update': datetime.now().isoformat()
            }

    async def get_state(self, device_id: str) -> Optional[Dict[str, Any]]:
        """Get current state of a device"""
        if device_id not in self.pairings:
            logger.warning(f"Device {device_id} not connected")
            return None

        return await self._get_full_state(device_id)

    async def set_state(self, device_id: str, state: Dict[str, Any]) -> bool:
        """Set device state"""
        if device_id not in self.pairings:
            logger.warning(f"Device {device_id} not connected")
            return False

        pairing = self.pairings[device_id]
        char_mapping = self.char_mapping[device_id]

        try:
            # Build list of characteristics to set
            chars_to_set = []

            for key, value in state.items():
                if key in char_mapping:
                    aid, iid = char_mapping[key]
                    chars_to_set.append({
                        'aid': aid,
                        'iid': iid,
                        'value': value
                    })
                else:
                    logger.warning(f"Unknown characteristic '{key}' for device {device_id}")

            if not chars_to_set:
                logger.warning(f"No valid characteristics to set for {device_id}")
                return False

            # Set characteristics
            await pairing.put_characteristics(chars_to_set)
            logger.info(f"Set state for {device_id}: {state}")

            # Update cached state
            await asyncio.sleep(0.5)  # Give device time to update
            updated_state = await self._get_full_state(device_id)
            self.device_states[device_id] = updated_state

            # Notify
            if self.on_state_change:
                self.on_state_change(device_id, updated_state)

            return True

        except Exception as e:
            logger.error(f"Error setting state for {device_id}: {e}")
            return False

    async def discover_devices(self, timeout: int = 10) -> List[Dict[str, Any]]:
        """
        Discover HomeKit devices on the network using Zeroconf

        Args:
            timeout: Discovery timeout in seconds

        Returns:
            List of discovered devices
        """
        logger.info(f"Starting HomeKit device discovery (timeout: {timeout}s)...")

        try:
            discovered = []

            # Discover using aiohomekit
            async with AsyncZeroconf() as aiozc:
                discoveries = await self.controller.discover(timeout, aiozc=aiozc)

                for device in discoveries:
                    device_info = {
                        'device_id': device.name,
                        'name': device.name,
                        'model': device.model,
                        'category': device.category_name,
                        'status_flags': device.status_flags,
                        'config_num': device.config_num,
                        'state_num': device.state_num,
                        'pairing_id': device.id,
                        'ip': device.address,
                        'port': device.port
                    }
                    discovered.append(device_info)
                    logger.info(f"Discovered: {device.name} ({device.model}) at {device.address}:{device.port}")

            logger.info(f"Discovery completed. Found {len(discovered)} devices.")
            return discovered

        except Exception as e:
            logger.error(f"Error during device discovery: {e}")
            return []

    async def pair_device(
        self,
        device_id: str,
        pairing_id: str,
        pin: str,
        ip: str,
        port: int = None
    ) -> Optional[Dict[str, Any]]:
        """
        Pair with a HomeKit device

        Args:
            device_id: Internal device identifier
            pairing_id: HomeKit pairing ID
            pin: PIN code (format: xxx-xx-xxx)
            ip: Device IP address
            port: Device port (optional)

        Returns:
            Pairing data dict on success, None on failure
        """
        logger.info(f"Attempting to pair with device {device_id} (pairing_id: {pairing_id})")

        try:
            # Start pairing
            pairing = await self.controller.start_pairing(pairing_id, ip, port)

            # Finish pairing with PIN
            pairing_data = await pairing.finish_pairing(device_id, pin)

            logger.info(f"Successfully paired with {device_id}")
            logger.debug(f"Pairing data keys: {list(pairing_data.keys())}")

            return pairing_data

        except AuthenticationError as e:
            logger.error(f"Authentication failed during pairing: {e}. Check PIN code.")
            return None
        except Exception as e:
            logger.error(f"Error pairing with device {device_id}: {e}")
            return None

    async def disconnect_all(self):
        """Disconnect from all devices"""
        logger.info("Disconnecting from all HomeKit devices...")

        for device_id, pairing in self.pairings.items():
            try:
                await pairing.close()
                logger.info(f"Disconnected from {device_id}")
            except Exception as e:
                logger.error(f"Error disconnecting from {device_id}: {e}")

        self.pairings.clear()
        self.device_states.clear()
        self.char_mapping.clear()
