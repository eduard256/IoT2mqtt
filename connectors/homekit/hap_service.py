#!/usr/bin/env python3
"""
HomeKit HAP Service - AsyncIO Process
Handles HomeKit protocol communication using aiohomekit
Provides REST API for connector.py to interact with HomeKit devices
"""

import os
import sys
import logging
import asyncio
from pathlib import Path
from typing import Dict, Any, List, Optional
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

try:
    from aiohomekit import Controller
    from aiohomekit.model import Accessory
    from aiohomekit.exceptions import AccessoryNotFoundError, AuthenticationError
except ImportError:
    # Will be available after pip install
    Controller = None

# Add shared to path
sys.path.insert(0, '/app/shared')
sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'shared'))

logger = logging.getLogger(__name__)


# Pydantic models for API requests/responses
class ConnectRequest(BaseModel):
    pairing_id: str
    pairing_data: Dict[str, Any]
    connection_type: str = "IP"  # IP, CoAP, BLE
    ip: Optional[str] = None
    port: Optional[int] = 55443


class CharacteristicRequest(BaseModel):
    aid: int  # Accessory ID
    iid: int  # Instance ID (characteristic ID)


class GetCharacteristicsRequest(BaseModel):
    pairing_id: str
    characteristics: List[CharacteristicRequest]


class SetCharacteristicRequest(BaseModel):
    aid: int
    iid: int
    value: Any


class SetCharacteristicsRequest(BaseModel):
    pairing_id: str
    characteristics: List[SetCharacteristicRequest]


# Global state
controller: Optional[Controller] = None
pairings: Dict[str, Any] = {}  # pairing_id -> pairing object
accessories_cache: Dict[str, List[Accessory]] = {}  # pairing_id -> accessories
event_subscribers: List[asyncio.Queue] = []  # SSE subscribers


@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI lifespan context manager"""
    global controller

    logger.info("Starting HAP service...")

    # Initialize aiohomekit Controller
    if Controller is None:
        logger.error("aiohomekit not installed!")
        raise RuntimeError("aiohomekit library not available")

    controller = Controller()
    logger.info("aiohomekit Controller initialized")

    yield

    # Cleanup
    logger.info("Shutting down HAP service...")
    if controller and pairings:
        for pairing_id in list(pairings.keys()):
            try:
                await _disconnect_pairing(pairing_id)
            except Exception as e:
                logger.error(f"Error disconnecting {pairing_id}: {e}")


app = FastAPI(
    title="HomeKit HAP Service",
    description="AsyncIO service for HomeKit protocol communication",
    version="1.0.0",
    lifespan=lifespan
)


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "connected_devices": len(pairings),
        "controller_initialized": controller is not None
    }


@app.post("/connect")
async def connect_device(request: ConnectRequest):
    """
    Connect to a HomeKit device using pairing data

    This loads the pairing into aiohomekit Controller and establishes connection
    """
    try:
        pairing_id = request.pairing_id

        logger.info(f"Connecting to device with pairing_id: {pairing_id}")

        # Check if already connected
        if pairing_id in pairings:
            logger.info(f"Device {pairing_id} already connected")
            return {"status": "already_connected", "pairing_id": pairing_id}

        # Load pairing into controller
        # aiohomekit expects pairing data format:
        # {
        #   "AccessoryPairingID": "XX:XX:XX:XX:XX:XX",
        #   "AccessoryLTPK": "base64_public_key",
        #   "iOSDevicePairingID": "YY:YY:YY:YY:YY:YY",
        #   "iOSDeviceLTSK": "base64_secret_key",
        #   "AccessoryIP": "192.168.1.100",
        #   "AccessoryPort": 55443,
        #   "Connection": "IP"  # or "CoAP" or "BLE"
        # }

        pairing_data = dict(request.pairing_data)

        # Override connection details if provided
        if request.ip:
            pairing_data["AccessoryIP"] = request.ip
        if request.port:
            pairing_data["AccessoryPort"] = request.port
        pairing_data["Connection"] = request.connection_type

        # Load pairing
        pairing = await controller.load_pairing(pairing_id, pairing_data)

        if not pairing:
            raise HTTPException(status_code=500, detail="Failed to load pairing")

        # Get accessories to verify connection
        accessories = await pairing.list_accessories_and_characteristics()
        accessories_cache[pairing_id] = accessories

        # Subscribe to characteristic changes (for push notifications)
        await _subscribe_to_events(pairing_id, pairing, accessories)

        # Store pairing
        pairings[pairing_id] = pairing

        logger.info(f"Successfully connected to device {pairing_id}, {len(accessories)} accessories found")

        return {
            "status": "connected",
            "pairing_id": pairing_id,
            "accessories_count": len(accessories)
        }

    except AccessoryNotFoundError as e:
        logger.error(f"Device not found: {e}")
        raise HTTPException(status_code=404, detail=f"HomeKit device not found: {str(e)}")
    except AuthenticationError as e:
        logger.error(f"Authentication failed: {e}")
        raise HTTPException(status_code=401, detail=f"Authentication failed: {str(e)}")
    except Exception as e:
        logger.error(f"Error connecting to device: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Connection error: {str(e)}")


@app.post("/disconnect")
async def disconnect_all():
    """Disconnect from all HomeKit devices"""
    try:
        disconnected = []
        for pairing_id in list(pairings.keys()):
            await _disconnect_pairing(pairing_id)
            disconnected.append(pairing_id)

        logger.info(f"Disconnected from {len(disconnected)} device(s)")
        return {"status": "disconnected", "devices": disconnected}

    except Exception as e:
        logger.error(f"Error disconnecting: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/accessories/{pairing_id}")
async def get_accessories(pairing_id: str):
    """Get cached accessories structure for a device"""
    if pairing_id not in accessories_cache:
        raise HTTPException(status_code=404, detail=f"No accessories cached for {pairing_id}")

    accessories = accessories_cache[pairing_id]

    # Convert to JSON-serializable format
    accessories_data = []
    for accessory in accessories:
        acc_data = {
            "aid": accessory.aid,
            "services": []
        }

        for service in accessory.services:
            svc_data = {
                "iid": service.iid,
                "type": service.type,
                "characteristics": []
            }

            for char in service.characteristics:
                char_data = {
                    "iid": char.iid,
                    "type": char.type,
                    "description": char.description,
                    "format": char.format,
                    "perms": char.perms,
                    "value": char.value
                }

                # Add optional fields
                if hasattr(char, 'minValue'):
                    char_data['minValue'] = char.minValue
                if hasattr(char, 'maxValue'):
                    char_data['maxValue'] = char.maxValue
                if hasattr(char, 'minStep'):
                    char_data['minStep'] = char.minStep
                if hasattr(char, 'unit'):
                    char_data['unit'] = char.unit
                if hasattr(char, 'valid_values'):
                    char_data['valid_values'] = char.valid_values

                svc_data['characteristics'].append(char_data)

            acc_data['services'].append(svc_data)

        accessories_data.append(acc_data)

    return {"pairing_id": pairing_id, "accessories": accessories_data}


@app.post("/characteristics/get")
async def get_characteristics(request: GetCharacteristicsRequest):
    """
    Get current values of characteristics

    Supports batch reading (up to 49 characteristics per request as per HAP spec)
    """
    try:
        pairing_id = request.pairing_id

        if pairing_id not in pairings:
            raise HTTPException(status_code=404, detail=f"Device {pairing_id} not connected")

        pairing = pairings[pairing_id]

        # Build list of (aid, iid) tuples
        characteristics = [(char.aid, char.iid) for char in request.characteristics]

        # Batch size limit
        if len(characteristics) > 49:
            logger.warning(f"Batch size {len(characteristics)} exceeds HAP limit of 49, splitting...")
            # TODO: Split into multiple requests

        # Get characteristics
        values = await pairing.get_characteristics(characteristics)

        # Format response
        result = {}
        for (aid, iid), value_data in values.items():
            key = f"{aid}.{iid}"
            result[key] = value_data.get('value')

        return result

    except Exception as e:
        logger.error(f"Error getting characteristics: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/characteristics/set")
async def set_characteristics(request: SetCharacteristicsRequest):
    """Set values of characteristics"""
    try:
        pairing_id = request.pairing_id

        if pairing_id not in pairings:
            raise HTTPException(status_code=404, detail=f"Device {pairing_id} not connected")

        pairing = pairings[pairing_id]

        # Build characteristics dict
        characteristics = {}
        for char in request.characteristics:
            characteristics[(char.aid, char.iid)] = char.value

        # Set characteristics
        await pairing.put_characteristics(characteristics)

        logger.info(f"Set {len(characteristics)} characteristic(s) for {pairing_id}")
        return {"status": "success", "count": len(characteristics)}

    except Exception as e:
        logger.error(f"Error setting characteristics: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/events")
async def events_stream(request: Request):
    """
    Server-Sent Events (SSE) stream for characteristic changes

    This endpoint streams real-time characteristic changes from subscribed devices
    """
    async def event_generator():
        queue = asyncio.Queue()
        event_subscribers.append(queue)

        try:
            yield "data: {\"status\": \"connected\"}\n\n"

            while True:
                # Check if client disconnected
                if await request.is_disconnected():
                    break

                try:
                    # Wait for event with timeout
                    event = await asyncio.wait_for(queue.get(), timeout=30.0)
                    yield f"data: {event}\n\n"
                except asyncio.TimeoutError:
                    # Send keepalive
                    yield ": keepalive\n\n"

        finally:
            event_subscribers.remove(queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
    )


async def _subscribe_to_events(pairing_id: str, pairing: Any, accessories: List[Accessory]):
    """
    Subscribe to characteristic changes for push notifications

    Args:
        pairing_id: Pairing identifier
        pairing: aiohomekit Pairing object
        accessories: List of accessories
    """
    try:
        # Find all characteristics with 'ev' (events) permission
        subscriptions = []

        for accessory in accessories:
            for service in accessory.services:
                for characteristic in service.characteristics:
                    if 'ev' in characteristic.perms:
                        subscriptions.append((accessory.aid, characteristic.iid))

        if not subscriptions:
            logger.info(f"No event-capable characteristics for {pairing_id}")
            return

        logger.info(f"Subscribing to {len(subscriptions)} characteristic(s) for {pairing_id}")

        # Register callback for characteristic changes
        def on_change(data):
            """Callback when characteristic changes"""
            asyncio.create_task(_handle_characteristic_change(pairing_id, data))

        # Subscribe
        await pairing.subscribe(subscriptions, on_change)

        logger.info(f"Successfully subscribed to events for {pairing_id}")

    except Exception as e:
        logger.error(f"Error subscribing to events for {pairing_id}: {e}")


async def _handle_characteristic_change(pairing_id: str, change_data: Dict[str, Any]):
    """
    Handle characteristic change event

    Args:
        pairing_id: Pairing identifier
        change_data: Change data from aiohomekit
    """
    try:
        # Extract aid, iid, value from change_data
        aid = change_data.get('aid')
        iid = change_data.get('iid')
        value = change_data.get('value')

        logger.debug(f"Characteristic changed: {pairing_id} aid={aid} iid={iid} value={value}")

        # Broadcast to all SSE subscribers
        event = {
            "pairing_id": pairing_id,
            "aid": aid,
            "iid": iid,
            "value": value
        }

        import json
        event_json = json.dumps(event)

        for queue in event_subscribers:
            try:
                await queue.put(event_json)
            except Exception as e:
                logger.error(f"Error pushing event to subscriber: {e}")

    except Exception as e:
        logger.error(f"Error handling characteristic change: {e}", exc_info=True)


async def _disconnect_pairing(pairing_id: str):
    """Disconnect a specific pairing"""
    if pairing_id in pairings:
        pairing = pairings[pairing_id]
        try:
            await pairing.close()
        except Exception as e:
            logger.error(f"Error closing pairing {pairing_id}: {e}")
        finally:
            del pairings[pairing_id]

    if pairing_id in accessories_cache:
        del accessories_cache[pairing_id]


def main():
    """Main entry point"""
    log_level = os.getenv('LOG_LEVEL', 'INFO')
    logging.basicConfig(
        level=getattr(logging, log_level),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    port = int(os.getenv('HAP_SERVICE_PORT', '8765'))

    logger.info(f"Starting HAP service on port {port}...")

    uvicorn.run(
        app,
        host="127.0.0.1",  # Only accessible from localhost (same container)
        port=port,
        log_level=log_level.lower(),
        access_log=True
    )


if __name__ == "__main__":
    main()
