"""
Test Runner Service
Handles all connection tests and discovery operations
"""

import os
import socket
import asyncio
import subprocess
import json
from typing import Dict, Any, List, Optional
from datetime import datetime
import logging

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = FastAPI(title="IoT2MQTT Test Runner", version="1.0.0")

# Enable CORS for web container
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class TCPTestRequest(BaseModel):
    """TCP connection test request"""
    ip: str
    port: int
    timeout: int = 5


class DiscoveryRequest(BaseModel):
    """Discovery request for an integration"""
    integration: str
    timeout: int = 30


class BatchTestRequest(BaseModel):
    """Batch test request"""
    devices: List[TCPTestRequest]


class TestResult(BaseModel):
    """Test result response"""
    success: bool
    code: Optional[int] = None
    error: Optional[str] = None
    details: Optional[Dict[str, Any]] = None
    timestamp: str = datetime.now().isoformat()


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "service": "IoT2MQTT Test Runner",
        "status": "running",
        "endpoints": [
            "/test/tcp",
            "/test/batch",
            "/test/yeelight",
            "/discovery/{integration}",
            "/health"
        ]
    }


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}


@app.post("/test/tcp", response_model=TestResult)
async def test_tcp_connection(request: TCPTestRequest):
    """Test TCP connection to a device"""
    logger.info(f"Testing TCP connection to {request.ip}:{request.port}")
    
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(request.timeout)
        result = sock.connect_ex((request.ip, request.port))
        sock.close()
        
        success = result == 0
        logger.info(f"TCP test to {request.ip}:{request.port} - {'SUCCESS' if success else f'FAILED (code {result})'}")
        
        return TestResult(
            success=success,
            code=result,
            details={
                "ip": request.ip,
                "port": request.port,
                "reachable": success
            }
        )
    except Exception as e:
        logger.error(f"TCP test error: {e}")
        return TestResult(
            success=False,
            error=str(e),
            details={"ip": request.ip, "port": request.port}
        )


@app.post("/test/batch", response_model=List[TestResult])
async def test_batch_connections(request: BatchTestRequest):
    """Test multiple TCP connections in parallel"""
    logger.info(f"Batch testing {len(request.devices)} devices")
    
    async def test_single(device: TCPTestRequest) -> TestResult:
        """Test single device asynchronously"""
        return await test_tcp_connection(device)
    
    # Run all tests in parallel
    tasks = [test_single(device) for device in request.devices]
    results = await asyncio.gather(*tasks)
    
    return results


@app.post("/test/yeelight", response_model=TestResult)
async def test_yeelight_device(ip: str, port: int = 55443):
    """Test Yeelight device specifically"""
    logger.info(f"Testing Yeelight device at {ip}:{port}")
    
    try:
        # First test TCP connection
        tcp_result = await test_tcp_connection(TCPTestRequest(ip=ip, port=port))
        
        if not tcp_result.success:
            return tcp_result
        
        # Try to import and use yeelight library if available
        try:
            from yeelight import Bulb

            bulb = Bulb(ip, port)

            # Try to get properties
            props = bulb.get_properties()
            
            if props:
                logger.info(f"Yeelight device found: {props}")
                return TestResult(
                    success=True,
                    details={
                        "ip": ip,
                        "port": port,
                        "properties": props,
                        "model": props.get("model", "unknown"),
                        "power": props.get("power", "unknown")
                    }
                )
            else:
                return TestResult(
                    success=False,
                    error="Device responded but no properties returned",
                    details={"ip": ip, "port": port}
                )
                
        except ImportError:
            # If yeelight library not available, just use TCP test
            logger.warning("Yeelight library not installed, using TCP test only")
            return tcp_result
            
    except Exception as e:
        logger.error(f"Yeelight test error: {e}")
        return TestResult(
            success=False,
            error=str(e),
            details={"ip": ip, "port": port}
        )


@app.post("/test/mqtt", response_model=TestResult)
async def test_mqtt_connection(host: str, port: int = 1883, username: Optional[str] = None):
    """Test MQTT broker connection"""
    logger.info(f"Testing MQTT connection to {host}:{port}")
    
    try:
        # First test TCP
        tcp_result = await test_tcp_connection(TCPTestRequest(ip=host, port=port))
        
        if not tcp_result.success:
            return tcp_result
        
        # Try MQTT specific test if paho-mqtt is available
        try:
            import paho.mqtt.client as mqtt
            
            connected = False
            
            def on_connect(client, userdata, flags, rc):
                nonlocal connected
                connected = (rc == 0)
            
            client = mqtt.Client()
            client.on_connect = on_connect
            
            if username:
                client.username_pw_set(username, os.environ.get("MQTT_PASSWORD", ""))
            
            client.connect(host, port, 60)
            client.loop_start()
            
            # Wait for connection
            await asyncio.sleep(2)
            client.loop_stop()
            client.disconnect()
            
            return TestResult(
                success=connected,
                details={
                    "host": host,
                    "port": port,
                    "mqtt_connected": connected
                }
            )
            
        except ImportError:
            logger.warning("paho-mqtt not installed, using TCP test only")
            return tcp_result
            
    except Exception as e:
        logger.error(f"MQTT test error: {e}")
    return TestResult(
        success=False,
        error=str(e),
        details={"host": host, "port": port}
    )


@app.post("/discovery/{integration}")
async def run_discovery(integration: str, background_tasks: BackgroundTasks):
    """Run discovery for a specific integration"""
    logger.info(f"Starting discovery for {integration}")
    
    try:
        # Check if integration exists
        connector_path = f"/app/connectors/{integration}"
        if not os.path.exists(connector_path):
            raise HTTPException(status_code=404, detail=f"Integration {integration} not found")
        
        # Check if discovery script exists
        discovery_script = f"{connector_path}/discovery.py"
        if not os.path.exists(discovery_script):
            raise HTTPException(status_code=400, detail=f"No discovery script for {integration}")
        
        # Run discovery in background
        background_tasks.add_task(execute_discovery, integration, discovery_script)
        
        return {
            "status": "started",
            "message": f"Discovery started for {integration}",
            "check_endpoint": f"/discovery/{integration}/status"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Discovery error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


async def execute_discovery(integration: str, script_path: str):
    """Execute discovery script"""
    logger.info(f"Executing discovery for {integration}")
    
    try:
        # Run the discovery script
        result = subprocess.run(
            ["python", script_path],
            capture_output=True,
            text=True,
            timeout=30,
            cwd=os.path.dirname(script_path)
        )
        
        if result.returncode == 0:
            # Parse the output as JSON
            try:
                devices = json.loads(result.stdout)
                logger.info(f"Discovery completed for {integration}: {len(devices)} devices found")
                
                # Save results
                save_discovery_results(integration, devices)
                
            except json.JSONDecodeError:
                logger.error(f"Invalid JSON from {integration} discovery: {result.stdout}")
        else:
            logger.error(f"Discovery failed for {integration}: {result.stderr}")
            
    except subprocess.TimeoutExpired:
        logger.error(f"Discovery timeout for {integration}")
    except Exception as e:
        logger.error(f"Discovery execution error: {e}")


def save_discovery_results(integration: str, devices: List[Dict]):
    """Save discovery results to file"""
    results_file = f"/tmp/discovery_{integration}.json"
    
    with open(results_file, 'w') as f:
        json.dump({
            "integration": integration,
            "devices": devices,
            "timestamp": datetime.now().isoformat()
        }, f, indent=2)
    
    logger.info(f"Discovery results saved to {results_file}")


@app.get("/discovery/{integration}/status")
async def get_discovery_status(integration: str):
    """Get discovery status for an integration"""
    results_file = f"/tmp/discovery_{integration}.json"
    
    if os.path.exists(results_file):
        with open(results_file, 'r') as f:
            data = json.load(f)
        return {
            "status": "completed",
            "devices": data.get("devices", []),
            "timestamp": data.get("timestamp")
        }
    else:
        return {
            "status": "pending",
            "devices": [],
            "message": "Discovery in progress or not started"
        }


# === Tools Executor ===

def _load_setup(integration: str) -> Dict[str, Any]:
    setup_path = f"/app/connectors/{integration}/setup.json"
    if not os.path.exists(setup_path):
        raise HTTPException(status_code=404, detail=f"setup.json not found for {integration}")
    with open(setup_path, 'r') as f:
        return json.load(f)


def _mask_secrets(text: str, secrets: List[str], input_payload: Dict[str, Any]) -> str:
    if not text:
        return text
    try:
        for key in secrets or []:
            val = input_payload.get(key)
            if isinstance(val, str) and val:
                text = text.replace(val, "******")
    except Exception:
        pass
    return text


@app.post("/actions/{integration}/execute")
async def execute_action(integration: str, body: Dict[str, Any]):
    """Execute a declared tool from connector setup.json in a subprocess.
    Body: { "tool": str, "input": dict }
    Returns tool stdout JSON as-is, or {ok:false,error} on failure.
    """
    tool_id = body.get("tool")
    input_payload = body.get("input", {})
    if not tool_id:
        raise HTTPException(status_code=400, detail="Missing 'tool' field")

    setup = _load_setup(integration)
    tools = setup.get("tools", {})
    tool = tools.get(tool_id)
    if not tool:
        raise HTTPException(status_code=404, detail=f"Tool '{tool_id}' not found for {integration}")

    entry = tool.get("entry")
    if not entry:
        raise HTTPException(status_code=400, detail=f"Tool '{tool_id}' has no entry")

    timeout = int(tool.get("timeout", 30))
    connector_path = f"/app/connectors/{integration}"
    script_path = os.path.join(connector_path, entry)
    if not os.path.exists(script_path):
        raise HTTPException(status_code=404, detail=f"Entry script not found: {entry}")

    payload = {"tool": tool_id, "input": input_payload}

    try:
        proc = subprocess.run(
            ["python", script_path],
            input=json.dumps(payload),
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=connector_path
        )

        stderr = proc.stderr or ""
        stderr = _mask_secrets(stderr, tool.get("secrets", []), input_payload)

        if proc.returncode != 0:
            logger.error(f"Tool {integration}/{tool_id} failed: {stderr}")
            return {"ok": False, "error": {"code": "tool_failed", "message": stderr.strip() or "non-zero exit code", "retriable": False}}

        # Parse stdout
        try:
            result = json.loads(proc.stdout or "{}")
        except json.JSONDecodeError:
            logger.error(f"Tool {integration}/{tool_id} returned invalid JSON")
            return {"ok": False, "error": {"code": "invalid_output", "message": "Tool returned invalid JSON", "retriable": False}}

        # Best-effort mask inside message
        if isinstance(result, dict) and not result.get("ok", True):
            err = result.get("error", {})
            if isinstance(err, dict) and isinstance(err.get("message"), str):
                err["message"] = _mask_secrets(err["message"], tool.get("secrets", []), input_payload)
        return result

    except subprocess.TimeoutExpired:
        logger.error(f"Tool {integration}/{tool_id} timeout")
        return {"ok": False, "error": {"code": "timeout", "message": f"Tool '{tool_id}' timed out", "retriable": True}}
    except Exception as e:
        logger.error(f"Tool {integration}/{tool_id} exception: {e}")
        return {"ok": False, "error": {"code": "executor_error", "message": str(e), "retriable": False}}


if __name__ == "__main__":
    port = int(os.environ.get("TEST_RUNNER_PORT", 8001))
    logger.info(f"Starting Test Runner on port {port}")
    uvicorn.run(app, host="0.0.0.0", port=port)
