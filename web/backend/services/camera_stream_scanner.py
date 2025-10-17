"""
Camera Stream Scanner Service
Asynchronously tests camera stream URLs and broadcasts results via SSE
"""

import asyncio
import json
import logging
import subprocess
from typing import Dict, List, Any, AsyncGenerator
from urllib.parse import urlparse
from datetime import datetime

logger = logging.getLogger(__name__)


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
        """Internal method to perform stream scanning"""
        try:
            # Generate test URLs from entries
            test_urls = self._generate_test_urls(entries, address, username, password, channel)

            logger.info(f"Scanning {len(test_urls)} URLs for task {task_id}")

            # Test URLs in parallel (with concurrency limit)
            semaphore = asyncio.Semaphore(10)  # Max 10 concurrent tests

            async def test_with_semaphore(url_info):
                async with semaphore:
                    return await self._test_stream(url_info)

            # Create tasks for all URLs
            tasks = [test_with_semaphore(url_info) for url_info in test_urls]

            # Process results as they complete
            for coro in asyncio.as_completed(tasks):
                result = await coro

                if result["ok"]:
                    stream_data = result["stream"]

                    # Add to results
                    self.scan_results[task_id].append(stream_data)

                    # Send to queue for SSE
                    await self.scan_queues[task_id].put({
                        "type": "stream_found",
                        "data": json.dumps(stream_data)
                    })

            # Mark as complete
            self.scan_status[task_id] = "completed"
            await self.scan_queues[task_id].put({"type": "scan_complete"})

            logger.info(f"Scan {task_id} completed. Found {len(self.scan_results[task_id])} streams")

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

        try:
            if protocol == "rtsp" or stream_type == "FFMPEG":
                return await self._test_rtsp(url_info)
            elif protocol in ["http", "https"]:
                return await self._test_http(url_info)
            else:
                return {"ok": False, "stream": None}

        except Exception as e:
            logger.debug(f"Stream test failed for {url}: {e}")
            return {"ok": False, "stream": None}

    async def _test_rtsp(self, url_info: Dict[str, Any]) -> Dict[str, Any]:
        """Test RTSP stream using ffprobe"""
        url = url_info["url"]

        try:
            # Run ffprobe with timeout
            proc = await asyncio.create_subprocess_exec(
                "ffprobe",
                "-v", "error",
                "-rtsp_transport", "tcp",
                "-timeout", "5000000",  # 5 second timeout
                "-print_format", "json",
                "-show_streams",
                url,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=10)

            if proc.returncode == 0 and stdout:
                # Stream is accessible
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
            logger.debug(f"RTSP test timeout: {url}")
        except FileNotFoundError:
            logger.warning("ffprobe not found - RTSP testing disabled")
        except Exception as e:
            logger.debug(f"RTSP test error: {e}")

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
                "--connect-timeout", "5",
                "--max-time", "10",
                url,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=15)
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
