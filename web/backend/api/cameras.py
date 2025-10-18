"""
Camera API Endpoints
Provides search and stream scanning functionality
"""

import logging
import uuid
from typing import Dict, Any
from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ValidationError

from services.camera_index_service import CameraIndexService
from services.camera_stream_scanner import CameraStreamScanner

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/cameras", tags=["Cameras"])

camera_index = CameraIndexService()
stream_scanner = CameraStreamScanner()


class StreamScanRequest(BaseModel):
    """Request to start stream scanning"""
    model: str
    brand: str
    address: str
    username: str = ""
    password: str = ""
    channel: int = 0


# Add custom exception handler for validation errors
@router.post("/scan-streams-debug")
async def debug_stream_scan_request(request: Request) -> Dict[str, Any]:
    """
    Debug endpoint to see raw request data before Pydantic validation
    """
    try:
        body = await request.body()
        logger.info("=" * 80)
        logger.info("DEBUG: RAW REQUEST DATA")
        logger.info(f"Raw body bytes: {body}")
        logger.info(f"Raw body decoded: {body.decode('utf-8')}")

        import json
        try:
            json_data = json.loads(body)
            logger.info(f"Parsed JSON data: {json.dumps(json_data, indent=2)}")
            logger.info(f"JSON keys: {list(json_data.keys())}")
            for key, value in json_data.items():
                logger.info(f"  {key}: '{value}' (type: {type(value).__name__})")
        except Exception as e:
            logger.error(f"Failed to parse JSON: {e}")

        logger.info("=" * 80)

        return {"ok": True, "message": "Check server logs for details"}
    except Exception as e:
        logger.error(f"Debug endpoint error: {e}")
        return {"ok": False, "error": str(e)}


@router.get("/search")
async def search_cameras(
    q: str = Query(..., min_length=2, description="Search query"),
    limit: int = Query(50, le=100, description="Max results")
) -> Dict[str, Any]:
    """
    Search for camera models across all brands

    Returns list of matching models with format:
    {"brand": "Hikvision", "model": "2CD2032-I", "display": "Hikvision: 2CD2032-I"}
    """
    try:
        results = camera_index.search(q, limit)
        return {
            "ok": True,
            "results": results,
            "count": len(results)
        }
    except Exception as e:
        logger.error(f"Camera search failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/scan-streams")
async def start_stream_scan(request: StreamScanRequest) -> Dict[str, Any]:
    """
    Start asynchronous stream scanning

    Returns task_id for monitoring progress via SSE endpoint
    """
    try:
        logger.info("=" * 80)
        logger.info("STREAM SCAN REQUEST RECEIVED")
        logger.info(f"Request model type: {type(request)}")
        logger.info(f"Request brand: '{request.brand}' (type: {type(request.brand)})")
        logger.info(f"Request model: '{request.model}' (type: {type(request.model)})")
        logger.info(f"Request address: '{request.address}' (type: {type(request.address)})")
        logger.info(f"Request username: '{request.username}' (type: {type(request.username)})")
        logger.info(f"Request password: {'***' if request.password else '(empty)'}")
        logger.info(f"Request channel: {request.channel} (type: {type(request.channel)})")
        logger.info("=" * 80)

        task_id = str(uuid.uuid4())

        # Get URL patterns for this model
        logger.info(f"Calling camera_index.get_entries(brand='{request.brand}', model='{request.model}')")
        entries = camera_index.get_entries(request.brand, request.model)
        logger.info(f"camera_index.get_entries returned {len(entries) if entries else 0} entries")

        if not entries:
            logger.warning(f"No stream patterns found for brand='{request.brand}', model='{request.model}'")
            return {
                "ok": False,
                "error": "No stream patterns found for this model"
            }

        logger.info(f"Starting stream scanner with task_id={task_id}")
        # Start background scanning task
        await stream_scanner.start_scan(
            task_id=task_id,
            entries=entries,
            address=request.address,
            username=request.username,
            password=request.password,
            channel=request.channel
        )

        logger.info(f"Stream scan started successfully: task_id={task_id}, patterns={len(entries)}")
        return {
            "ok": True,
            "task_id": task_id,
            "message": f"Scanning {len(entries)} stream patterns..."
        }

    except Exception as e:
        logger.error("=" * 80)
        logger.error(f"FAILED TO START STREAM SCAN - Exception: {type(e).__name__}")
        logger.error(f"Error message: {str(e)}")
        logger.error(f"Exception details: {repr(e)}")
        import traceback
        logger.error(f"Traceback:\n{traceback.format_exc()}")
        logger.error("=" * 80)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/scan-streams/{task_id}/stream")
async def stream_scan_results(task_id: str):
    """
    Server-Sent Events endpoint for real-time scan results

    Streams found camera streams as they are discovered
    """
    try:
        async def event_generator():
            """Generate SSE events for scan progress"""
            async for event in stream_scanner.get_results_stream(task_id):
                if event["type"] == "stream_found":
                    stream_data = event["data"]
                    yield f"data: {stream_data}\n\n"
                elif event["type"] == "scan_complete":
                    yield 'data: {"type": "done"}\n\n'
                    break
                elif event["type"] == "error":
                    yield f'data: {{"type": "error", "message": "{event["message"]}"}}\n\n'
                    break

        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no"  # Disable nginx buffering
            }
        )

    except Exception as e:
        logger.error(f"SSE stream error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/scan-streams/{task_id}/status")
async def get_scan_status(task_id: str) -> Dict[str, Any]:
    """
    Get current status of a scan task (alternative to SSE)

    Returns:
        - status: "running", "completed", "error"
        - found_streams: list of discovered streams
        - progress: percentage complete
    """
    try:
        status = stream_scanner.get_status(task_id)
        return {"ok": True, **status}
    except Exception as e:
        logger.error(f"Failed to get scan status: {e}")
        raise HTTPException(status_code=404, detail="Scan task not found")
