"""
Camera Stream Scanner Service
Asynchronously tests camera stream URLs and broadcasts results via SSE
"""

import asyncio
import json
import logging
import subprocess
from typing import Dict, List, Any, AsyncGenerator, Optional
from urllib.parse import urlparse
from datetime import datetime
import time

logger = logging.getLogger(__name__)

# Try to import ONVIF library (optional dependency)
try:
    from onvif import ONVIFCamera
    ONVIF_AVAILABLE = True
    logger.info("ONVIF library loaded successfully")
except ImportError:
    ONVIF_AVAILABLE = False
    logger.warning("ONVIF library not available - install with: pip install onvif-zeep")


class CameraStreamScanner:
    """Manages asynchronous camera stream scanning tasks"""

    def __init__(self):
        self.active_scans: Dict[str, asyncio.Task] = {}
        self.scan_results: Dict[str, List[Dict[str, Any]]] = {}
        self.scan_status: Dict[str, str] = {}  # "running", "completed", "error"
        self.scan_queues: Dict[str, asyncio.Queue] = {}

    async def start_scan(
        self,
        task_id: str,
        entries: List[Dict[str, Any]],
        address: str,
        username: str = "",
        password: str = "",
        channel: int = 0
    ):
        """
        Start asynchronous scan of camera streams

        Args:
            task_id: Unique task identifier
            entries: List of URL pattern entries from database
            address: Camera IP/hostname
            username: Camera username
            password: Camera password
            channel: Camera channel (for DVRs)
        """
        if task_id in self.active_scans:
            logger.warning(f"Scan {task_id} already running")
            return

        # Create queue for results
        self.scan_queues[task_id] = asyncio.Queue()
        self.scan_results[task_id] = []
        self.scan_status[task_id] = "running"

        # Start scanning task
        task = asyncio.create_task(
            self._scan_streams(task_id, entries, address, username, password, channel)
        )
        self.active_scans[task_id] = task

    async def _scan_streams(
        self,
        task_id: str,
        entries: List[Dict[str, Any]],
        address: str,
        username: str,
        password: str,
        channel: int
    ):
        """
        Internal method to perform stream scanning

        Combines ONVIF discovery with pattern-based URL testing.
        Stops when 7+ streams found or 5 minutes elapsed.
        """
        start_time = time.time()
        max_duration = 300  # 5 minutes (was 2 minutes)
        max_streams = 7     # Stop after finding 7 streams

        try:
            # Try ONVIF discovery first (runs in parallel with URL generation)
            logger.info(f"Starting scan for task {task_id}")

            # Start ONVIF discovery in background
            onvif_task = asyncio.create_task(
                self._try_onvif_discovery(address, username, password)
            )

            # Generate test URLs from entries while ONVIF discovery runs
            test_urls = self._generate_test_urls(entries, address, username, password, channel)

            logger.info(f"Generated {len(test_urls)} test URLs for task {task_id}")

            # Wait for ONVIF discovery (with timeout)
            try:
                onvif_streams = await asyncio.wait_for(onvif_task, timeout=25.0)

                if onvif_streams:
                    logger.info(f"ONVIF discovered {len(onvif_streams)} stream(s)")

                    # Process ONVIF streams first
                    for stream_data in onvif_streams:
                        self.scan_results[task_id].append(stream_data)
                        await self.scan_queues[task_id].put({
                            "type": "stream_found",
                            "data": json.dumps(stream_data)
                        })

                    # Check if we already have enough streams
                    if len(self.scan_results[task_id]) >= max_streams:
                        logger.info(f"Found {len(self.scan_results[task_id])} streams via ONVIF, stopping scan")
                        self.scan_status[task_id] = "completed"
                        await self.scan_queues[task_id].put({"type": "scan_complete"})
                        return

            except asyncio.TimeoutError:
                logger.debug(f"ONVIF discovery timeout for task {task_id}, continuing with pattern testing")
            except Exception as e:
                logger.debug(f"ONVIF discovery error for task {task_id}: {e}")

            # Test URLs in parallel (with concurrency limit)
            semaphore = asyncio.Semaphore(12)  # Max 12 concurrent tests (was 10)

            async def test_with_semaphore(url_info):
                async with semaphore:
                    return await self._test_stream(url_info)

            # Create tasks for all URLs
            tasks = [asyncio.create_task(test_with_semaphore(url_info)) for url_info in test_urls]
            logger.info(f"Created {len(tasks)} test tasks for parallel testing")

            # Process results as they complete
            pending_tasks = set(tasks)
            logger.info(f"Starting result processing loop with {len(pending_tasks)} pending tasks")

            if not pending_tasks:
                logger.warning(f"No pending tasks to process! All {len(test_urls)} URLs skipped or failed immediately")

            while pending_tasks:
                # Check stop conditions
                elapsed = time.time() - start_time
                found_count = len(self.scan_results[task_id])

                if found_count >= max_streams:
                    logger.info(f"Stop condition: found {found_count} streams (>= {max_streams}), stopping scan")
                    break

                if elapsed >= max_duration:
                    logger.info(f"Stop condition: timeout {elapsed:.1f}s (>= {max_duration}s), stopping scan")
                    break

                logger.debug(f"Loop iteration: {len(pending_tasks)} pending, {found_count} found, {elapsed:.1f}s elapsed")

                # Wait for next result with timeout
                done, pending_tasks = await asyncio.wait(
                    pending_tasks,
                    return_when=asyncio.FIRST_COMPLETED,
                    timeout=1.0
                )

                logger.debug(f"asyncio.wait returned: {len(done)} done, {len(pending_tasks)} still pending")

                # Process completed tasks
                for completed_task in done:
                    try:
                        result = await completed_task

                        if result["ok"]:
                            stream_data = result["stream"]

                            # Check for duplicates (same URL)
                            existing_urls = [s.get("url") for s in self.scan_results[task_id]]
                            if stream_data.get("url") not in existing_urls:
                                # Add to results
                                self.scan_results[task_id].append(stream_data)

                                # Send to queue for SSE
                                await self.scan_queues[task_id].put({
                                    "type": "stream_found",
                                    "data": json.dumps(stream_data)
                                })

                                logger.info(f"Found stream {len(self.scan_results[task_id])}: {stream_data.get('notes', 'Unknown')}")
                    except Exception as e:
                        logger.debug(f"Error processing task result: {e}")

            # Cancel remaining tasks if we stopped early
            if pending_tasks:
                logger.info(f"Loop ended early: cancelling {len(pending_tasks)} remaining tasks")
                for task in pending_tasks:
                    task.cancel()

                # Wait for cancellations to complete
                await asyncio.gather(*pending_tasks, return_exceptions=True)
            else:
                logger.info(f"All tasks completed naturally (no pending tasks left)")

            # Mark as complete
            self.scan_status[task_id] = "completed"
            await self.scan_queues[task_id].put({"type": "scan_complete"})

            elapsed = time.time() - start_time
            logger.info(f"Scan {task_id} completed in {elapsed:.1f}s. Found {len(self.scan_results[task_id])} streams")

        except Exception as e:
            logger.error(f"Scan {task_id} failed: {e}")
            self.scan_status[task_id] = "error"
            await self.scan_queues[task_id].put({
                "type": "error",
                "message": str(e)
            })

        finally:
            # Cleanup
            if task_id in self.active_scans:
                del self.active_scans[task_id]

    def _generate_test_urls(
        self,
        entries: List[Dict[str, Any]],
        address: str,
        username: str,
        password: str,
        channel: int
    ) -> List[Dict[str, Any]]:
        """
        Generate test URLs from database entries

        Returns list of dicts with: {url, type, protocol, port, notes}
        """
        test_urls = []

        # Parse address to extract IP and port
        parsed = urlparse(address if '://' in address else f'http://{address}')
        host = parsed.hostname or address
        default_port = parsed.port

        for entry in entries:
            protocol = entry.get("protocol", "rtsp")
            port = entry.get("port", 0)

            # Use default port if entry port is 0
            if port == 0:
                if protocol == "rtsp":
                    port = default_port or 554
                elif protocol == "http":
                    port = default_port or 80
                elif protocol == "https":
                    port = default_port or 443

            url_path = entry.get("url", "")

            # Replace template variables
            url_path = url_path.replace("{username}", username or "")
            url_path = url_path.replace("{password}", password or "")
            url_path = url_path.replace("{ip}", host)
            url_path = url_path.replace("{port}", str(port))
            url_path = url_path.replace("{channel}", str(channel))
            url_path = url_path.replace("[USERNAME]", username or "")
            url_path = url_path.replace("[PASSWORD]", password or "")
            url_path = url_path.replace("[AUTH]", f"{username}:{password}" if username else "")

            # Build full URL
            if protocol in ["rtsp", "http", "https"]:
                if username and password:
                    full_url = f"{protocol}://{username}:{password}@{host}:{port}/{url_path.lstrip('/')}"
                else:
                    full_url = f"{protocol}://{host}:{port}/{url_path.lstrip('/')}"
            else:
                full_url = f"{protocol}://{host}:{port}/{url_path.lstrip('/')}"

            test_urls.append({
                "url": full_url,
                "type": entry.get("type", "FFMPEG"),
                "protocol": protocol,
                "port": port,
                "notes": entry.get("notes", ""),
                "priority": self._get_priority(entry.get("type", "FFMPEG"))
            })

        # Sort by priority (ONVIF first, then FFMPEG/RTSP, etc.)
        test_urls.sort(key=lambda x: x["priority"])

        return test_urls

    async def _try_onvif_discovery(
        self,
        address: str,
        username: str,
        password: str,
        port: int = 80
    ) -> List[Dict[str, Any]]:
        """
        Try ONVIF device discovery to get exact stream URLs

        Args:
            address: Camera IP address
            username: Camera username
            password: Camera password
            port: ONVIF port (default 80)

        Returns:
            List of discovered stream entries (empty if ONVIF not supported)
        """
        if not ONVIF_AVAILABLE:
            logger.debug("ONVIF library not available, skipping ONVIF discovery")
            return []

        discovered_streams = []

        try:
            # Parse address to get clean IP
            parsed = urlparse(address if '://' in address else f'http://{address}')
            host = parsed.hostname or address

            logger.info(f"Attempting ONVIF discovery on {host}:{port}")

            # Create ONVIF camera instance
            # Run in executor to avoid blocking async loop
            def create_onvif_camera():
                try:
                    mycam = ONVIFCamera(
                        host,
                        port,
                        username,
                        password,
                        wsdl_dir='/usr/local/lib/python3.11/site-packages/wsdl'  # Adjust path as needed
                    )
                    return mycam
                except Exception as e:
                    logger.debug(f"Failed to create ONVIF camera: {e}")
                    return None

            # Run ONVIF operations with timeout
            mycam = await asyncio.wait_for(
                asyncio.get_event_loop().run_in_executor(None, create_onvif_camera),
                timeout=15.0
            )

            if not mycam:
                logger.debug(f"ONVIF not supported on {host}")
                return []

            # Get media service
            def get_media_profiles():
                try:
                    media_service = mycam.create_media_service()
                    profiles = media_service.GetProfiles()
                    return profiles
                except Exception as e:
                    logger.debug(f"Failed to get media profiles: {e}")
                    return []

            profiles = await asyncio.wait_for(
                asyncio.get_event_loop().run_in_executor(None, get_media_profiles),
                timeout=15.0
            )

            if not profiles:
                logger.debug(f"No ONVIF media profiles found on {host}")
                return []

            logger.info(f"Found {len(profiles)} ONVIF media profile(s) on {host}")

            # Extract stream URIs from profiles
            for idx, profile in enumerate(profiles):
                try:
                    def get_stream_uri(prof):
                        try:
                            media_service = mycam.create_media_service()
                            obj = media_service.create_type('GetStreamUri')
                            obj.ProfileToken = prof.token
                            obj.StreamSetup = {
                                'Stream': 'RTP-Unicast',
                                'Transport': {'Protocol': 'RTSP'}
                            }
                            uri_response = media_service.GetStreamUri(obj)
                            return uri_response.Uri
                        except Exception as e:
                            logger.debug(f"Failed to get stream URI: {e}")
                            return None

                    stream_uri = await asyncio.wait_for(
                        asyncio.get_event_loop().run_in_executor(None, lambda: get_stream_uri(profile)),
                        timeout=10.0
                    )

                    if stream_uri:
                        # Parse ONVIF stream URI
                        parsed_uri = urlparse(stream_uri)

                        # Build clean URL without embedded credentials
                        clean_path = parsed_uri.path
                        if parsed_uri.query:
                            clean_path += f"?{parsed_uri.query}"

                        discovered_streams.append({
                            "type": "ONVIF",
                            "protocol": "rtsp",
                            "port": parsed_uri.port or 554,
                            "url": clean_path,
                            "full_url": stream_uri,
                            "notes": f"ONVIF Profile {idx + 1}: {profile.Name if hasattr(profile, 'Name') else f'Stream {idx + 1}'}"
                        })

                        logger.info(f"ONVIF stream {idx + 1}: {stream_uri}")

                except asyncio.TimeoutError:
                    logger.debug(f"Timeout getting stream URI for profile {idx}")
                    continue
                except Exception as e:
                    logger.debug(f"Error processing profile {idx}: {e}")
                    continue

            if discovered_streams:
                logger.info(f"ONVIF discovery successful: found {len(discovered_streams)} stream(s)")
            else:
                logger.debug(f"ONVIF discovery found no usable streams on {host}")

        except asyncio.TimeoutError:
            logger.debug(f"ONVIF discovery timeout for {host}")
        except Exception as e:
            logger.debug(f"ONVIF discovery failed for {host}: {e}")

        return discovered_streams

    def _get_priority(self, stream_type: str) -> int:
        """Get priority for stream type (lower = higher priority)"""
        priorities = {
            "ONVIF": 1,
            "FFMPEG": 2,
            "MJPEG": 3,
            "JPEG": 4,
            "VLC": 5
        }
        return priorities.get(stream_type, 99)

    async def _test_stream(self, url_info: Dict[str, Any]) -> Dict[str, Any]:
        """
        Test a single stream URL

        Returns: {"ok": bool, "stream": {...} or None}
        """
        url = url_info["url"]
        stream_type = url_info["type"]
        protocol = url_info["protocol"]

        logger.debug(f"Testing stream: {protocol}://{url[:50]}... (type={stream_type})")

        try:
            if protocol == "rtsp" or stream_type == "FFMPEG":
                result = await self._test_rtsp(url_info)
                logger.debug(f"RTSP test result for {url[:50]}...: ok={result['ok']}")
                return result
            elif protocol in ["http", "https"]:
                result = await self._test_http(url_info)
                logger.debug(f"HTTP test result for {url[:50]}...: ok={result['ok']}")
                return result
            else:
                logger.warning(f"Unknown protocol '{protocol}' for {url[:50]}...")
                return {"ok": False, "stream": None}

        except Exception as e:
            logger.error(f"Stream test exception for {url[:50]}...: {e}")
            return {"ok": False, "stream": None}

    async def _test_rtsp(self, url_info: Dict[str, Any]) -> Dict[str, Any]:
        """Test RTSP stream using ffprobe"""
        url = url_info["url"]

        logger.debug(f"Starting ffprobe test for: {url[:50]}...")

        try:
            # Run ffprobe with timeout
            proc = await asyncio.create_subprocess_exec(
                "ffprobe",
                "-v", "error",
                "-rtsp_transport", "tcp",
                "-timeout", "25000000",  # 25 second timeout (was 5 sec)
                "-print_format", "json",
                "-show_streams",
                url,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=25)

            logger.debug(f"ffprobe returncode={proc.returncode} for {url[:50]}...")

            if proc.returncode == 0 and stdout:
                # Stream is accessible
                logger.info(f"✓ RTSP stream accessible: {url[:50]}...")
                return {
                    "ok": True,
                    "stream": {
                        "type": url_info["type"],
                        "protocol": url_info["protocol"],
                        "url": self._mask_credentials(url),
                        "full_url": url,  # Keep for validation
                        "port": url_info["port"],
                        "notes": url_info.get("notes", "")
                    }
                }

        except asyncio.TimeoutError:
            logger.debug(f"✗ RTSP test timeout (25s): {url[:50]}...")
        except FileNotFoundError:
            logger.error("ffprobe not found - RTSP testing disabled!")
        except Exception as e:
            logger.debug(f"✗ RTSP test error for {url[:50]}...: {e}")

        return {"ok": False, "stream": None}

    async def _test_http(self, url_info: Dict[str, Any]) -> Dict[str, Any]:
        """Test HTTP/MJPEG stream"""
        url = url_info["url"]

        try:
            # Simple HEAD request to check if URL is accessible
            proc = await asyncio.create_subprocess_exec(
                "curl",
                "-I",  # HEAD request
                "-s",  # Silent
                "-o", "/dev/null",
                "-w", "%{http_code}",
                "--connect-timeout", "10",
                "--max-time", "25",
                url,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=25)
            status_code = stdout.decode().strip()

            if status_code.startswith("200"):
                return {
                    "ok": True,
                    "stream": {
                        "type": url_info["type"],
                        "protocol": url_info["protocol"],
                        "url": self._mask_credentials(url),
                        "full_url": url,
                        "port": url_info["port"],
                        "notes": url_info.get("notes", "")
                    }
                }

        except asyncio.TimeoutError:
            logger.debug(f"HTTP test timeout: {url}")
        except Exception as e:
            logger.debug(f"HTTP test error: {e}")

        return {"ok": False, "stream": None}

    def _mask_credentials(self, url: str) -> str:
        """Mask username and password in URL"""
        try:
            parsed = urlparse(url)
            if parsed.username or parsed.password:
                # Replace credentials with ***
                masked = parsed._replace(
                    netloc=f"***:***@{parsed.hostname}:{parsed.port}" if parsed.port
                    else f"***:***@{parsed.hostname}"
                )
                return masked.geturl()
            return url
        except:
            return url

    async def get_results_stream(self, task_id: str) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Get SSE event stream for scan results

        Yields events: {"type": "stream_found", "data": {...}} or {"type": "scan_complete"}
        """
        if task_id not in self.scan_queues:
            yield {"type": "error", "message": "Scan not found"}
            return

        queue = self.scan_queues[task_id]

        while True:
            try:
                # Wait for next result (with timeout)
                event = await asyncio.wait_for(queue.get(), timeout=300)  # 5 min max

                yield event

                if event["type"] in ["scan_complete", "error"]:
                    break

            except asyncio.TimeoutError:
                yield {"type": "error", "message": "Scan timeout"}
                break

        # Cleanup
        if task_id in self.scan_queues:
            del self.scan_queues[task_id]
        if task_id in self.scan_results:
            # Keep results for a bit longer for status API
            pass

    def get_status(self, task_id: str) -> Dict[str, Any]:
        """Get current status of a scan"""
        if task_id not in self.scan_status:
            raise ValueError(f"Task {task_id} not found")

        return {
            "task_id": task_id,
            "status": self.scan_status[task_id],
            "found_streams": self.scan_results.get(task_id, []),
            "count": len(self.scan_results.get(task_id, []))
        }
