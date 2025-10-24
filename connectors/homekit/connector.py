"""
HomeKit Connector Implementation
Controls HomeKit accessories and exposes them via MQTT
"""

import asyncio
import threading
import logging
import time
from typing import Dict, Any, List, Optional
from datetime import datetime

# Import base connector from shared
import sys
from pathlib import Path
sys.path.insert(0, '/app/shared')
from base_connector import BaseConnector

# Import HomeKit manager
from homekit_manager import HomeKitManager

logger = logging.getLogger(__name__)


class Connector(BaseConnector):
    """
    HomeKit connector implementation

    Connects to HomeKit accessories and exposes them via MQTT.
    Uses hybrid asyncio + threading architecture to bridge
    aiohomekit (asyncio) with BaseConnector (threading).
    """

    def __init__(self, config_path: str = None, instance_name: str = None):
        """Initialize connector"""
        super().__init__(config_path, instance_name)

        # Asyncio event loop (runs in separate thread)
        self.loop = None
        self.asyncio_thread = None

        # HomeKit manager (runs in asyncio context)
        self.homekit_manager = None

        # Thread synchronization
        self.loop_ready = threading.Event()

        logger.info(f"HomeKit Connector initialized for {self.instance_id}")

    def initialize_connection(self):
        """
        Initialize connection to HomeKit devices

        Creates asyncio event loop in background thread and
        initializes HomeKit manager with device pairings.
        """
        logger.info("Initializing connection to HomeKit devices...")

        # Load secrets (pairing data)
        self._load_secrets(self.config)

        if not self.secrets:
            logger.warning("No pairing data found in secrets")
            # Don't fail - devices might be added later
            self.secrets = {'pairings': {}}

        # Start asyncio event loop in background thread
        self._start_asyncio_loop()

        # Wait for loop to be ready
        if not self.loop_ready.wait(timeout=10):
            raise RuntimeError("Failed to start asyncio event loop")

        # Initialize HomeKit manager in asyncio context
        try:
            future = asyncio.run_coroutine_threadsafe(
                self._async_initialize(),
                self.loop
            )
            future.result(timeout=30)
            logger.info("HomeKit manager initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize HomeKit manager: {e}")
            raise

    def _start_asyncio_loop(self):
        """Start asyncio event loop in background thread"""
        def run_loop():
            logger.info("Starting asyncio event loop thread...")
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)
            self.loop_ready.set()
            self.loop.run_forever()
            logger.info("Asyncio event loop stopped")

        self.asyncio_thread = threading.Thread(
            target=run_loop,
            name="HomeKit-AsyncIO",
            daemon=True
        )
        self.asyncio_thread.start()

    async def _async_initialize(self):
        """Initialize HomeKit manager (runs in asyncio context)"""
        logger.info("Initializing HomeKit manager...")

        self.homekit_manager = HomeKitManager(
            config=self.config,
            secrets=self.secrets,
            on_state_change=self._on_homekit_state_change
        )

        # Connect to all configured devices
        await self.homekit_manager.initialize()

        logger.info("HomeKit manager initialization complete")

    def cleanup_connection(self):
        """
        Clean up HomeKit connections when stopping
        """
        logger.info("Cleaning up HomeKit connections...")

        if self.homekit_manager and self.loop:
            try:
                # Disconnect all devices
                future = asyncio.run_coroutine_threadsafe(
                    self.homekit_manager.disconnect_all(),
                    self.loop
                )
                future.result(timeout=10)
            except Exception as e:
                logger.error(f"Error disconnecting devices: {e}")

        # Stop asyncio loop
        if self.loop:
            try:
                self.loop.call_soon_threadsafe(self.loop.stop)
                logger.info("Stopped asyncio event loop")
            except Exception as e:
                logger.error(f"Error stopping asyncio loop: {e}")

        # Wait for thread to finish
        if self.asyncio_thread and self.asyncio_thread.is_alive():
            self.asyncio_thread.join(timeout=5)

        logger.info("HomeKit connections cleaned up")

    def get_device_state(self, device_id: str, device_config: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Get current state of a HomeKit device

        This is called periodically by BaseConnector polling loop.
        We use cached state from event updates when possible.
        """
        if not self.homekit_manager or not self.loop:
            logger.warning(f"HomeKit manager not initialized")
            return None

        try:
            # Try to get cached state first (from events)
            if device_id in self.homekit_manager.device_states:
                cached_state = self.homekit_manager.device_states[device_id]
                logger.debug(f"Returning cached state for {device_id}")
                return cached_state

            # If no cached state, query device
            logger.debug(f"Querying device state for {device_id}")
            future = asyncio.run_coroutine_threadsafe(
                self.homekit_manager.get_state(device_id),
                self.loop
            )
            state = future.result(timeout=5)
            return state

        except asyncio.TimeoutError:
            logger.error(f"Timeout getting state for {device_id}")
            return {
                'online': False,
                'error': 'Timeout',
                'last_update': datetime.now().isoformat()
            }
        except Exception as e:
            logger.error(f"Error getting state for {device_id}: {e}")
            return {
                'online': False,
                'error': str(e),
                'last_update': datetime.now().isoformat()
            }

    def set_device_state(
        self,
        device_id: str,
        device_config: Dict[str, Any],
        state: Dict[str, Any]
    ) -> bool:
        """
        Set HomeKit device state

        Called when MQTT command is received.
        Executes async set_state in asyncio context.
        """
        logger.info(f"Setting state for {device_id}: {state}")

        if not self.homekit_manager or not self.loop:
            logger.warning(f"HomeKit manager not initialized")
            return False

        try:
            # Execute set_state in asyncio context
            future = asyncio.run_coroutine_threadsafe(
                self.homekit_manager.set_state(device_id, state),
                self.loop
            )
            result = future.result(timeout=10)

            if result:
                logger.info(f"Successfully set state for {device_id}")
                # State will be published via event callback
                return True
            else:
                logger.error(f"Failed to set state for {device_id}")
                self.mqtt.publish_error(
                    device_id,
                    "COMMAND_FAILED",
                    "Failed to set device state",
                    severity="error"
                )
                return False

        except asyncio.TimeoutError:
            logger.error(f"Timeout setting state for {device_id}")
            self.mqtt.publish_error(
                device_id,
                "COMMAND_TIMEOUT",
                "Command timed out",
                severity="error"
            )
            return False
        except Exception as e:
            logger.error(f"Error setting state for {device_id}: {e}")
            self.mqtt.publish_error(
                device_id,
                "COMMAND_ERROR",
                str(e),
                severity="error"
            )
            return False

    def _on_homekit_state_change(self, device_id: str, new_state: Dict[str, Any]):
        """
        Callback when HomeKit device state changes (from events)

        This is called from asyncio thread when characteristic changes.
        We need to publish to MQTT (which is thread-safe).
        """
        logger.debug(f"State change event for {device_id}")

        try:
            # Publish state update to MQTT
            self.mqtt.publish_state(device_id, new_state)
            logger.debug(f"Published state update for {device_id} to MQTT")
        except Exception as e:
            logger.error(f"Error publishing state change for {device_id}: {e}")

    # === Optional: Discovery support ===

    def discover_devices(self) -> List[Dict[str, Any]]:
        """
        Discover HomeKit devices on the network

        Optional method called by setup flow or manually.
        Not called by BaseConnector polling loop.
        """
        if not self.homekit_manager or not self.loop:
            logger.warning("HomeKit manager not initialized for discovery")
            return []

        try:
            logger.info("Starting HomeKit device discovery...")
            future = asyncio.run_coroutine_threadsafe(
                self.homekit_manager.discover_devices(timeout=10),
                self.loop
            )
            discovered = future.result(timeout=15)

            if discovered:
                logger.info(f"Discovered {len(discovered)} HomeKit devices")
                # Optionally publish to MQTT
                # self.mqtt.publish_discovered(discovered)
            else:
                logger.info("No HomeKit devices discovered")

            return discovered

        except Exception as e:
            logger.error(f"Error during device discovery: {e}")
            return []

    # === Custom HomeKit methods ===

    def pair_device(
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
        if not self.homekit_manager or not self.loop:
            logger.error("HomeKit manager not initialized for pairing")
            return None

        try:
            logger.info(f"Pairing with device {device_id}...")
            future = asyncio.run_coroutine_threadsafe(
                self.homekit_manager.pair_device(
                    device_id=device_id,
                    pairing_id=pairing_id,
                    pin=pin,
                    ip=ip,
                    port=port
                ),
                self.loop
            )
            pairing_data = future.result(timeout=30)

            if pairing_data:
                logger.info(f"Successfully paired with {device_id}")
                return pairing_data
            else:
                logger.error(f"Failed to pair with {device_id}")
                return None

        except Exception as e:
            logger.error(f"Error pairing with device {device_id}: {e}")
            return None

    def validate_pairing(self, device_id: str) -> bool:
        """
        Validate that pairing exists and is valid for a device

        Args:
            device_id: Device identifier

        Returns:
            True if pairing is valid, False otherwise
        """
        if not self.homekit_manager:
            return False

        # Check if device is connected
        if device_id in self.homekit_manager.pairings:
            logger.info(f"Pairing for {device_id} is valid")
            return True
        else:
            logger.warning(f"No valid pairing for {device_id}")
            return False
