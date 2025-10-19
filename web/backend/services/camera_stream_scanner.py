"""
Camera Stream Scanner Service
Synchronously tests camera stream URLs and broadcasts results via SSE
"""

import json
import logging
import subprocess
import threading
import time
from queue import Queue, Empty
from typing import Dict, List, Any, Optional
from urllib.parse import urlparse
from pathlib import Path

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
    """Manages synchronous camera stream scanning tasks in background threads"""

    def __init__(self):
        self.scan_threads: Dict[str, threading.Thread] = {}
        self.scan_results: Dict[str, List[Dict[str, Any]]] = {}
        self.scan_status: Dict[str, str] = {}  # "running", "completed", "error"
        self.scan_queues: Dict[str, Queue] = {}

    def start_scan(
        self,
        task_id: str,
        entries: List[Dict[str, Any]],
        address: str,
        username: str = "",
        password: str = "",
        channel: int = 0
    ):
        """
        Start synchronous scan of camera streams in background thread

        Args:
            task_id: Unique task identifier
            entries: List of URL pattern entries from database
            address: Camera IP/hostname
            username: Camera username
            password: Camera password
            channel: Camera channel (for DVRs)
        """
        if task_id in self.scan_threads:
            logger.warning(f"Scan {task_id} already running")
            return

        # Create queue for results
        self.scan_queues[task_id] = Queue()
        self.scan_results[task_id] = []
        self.scan_status[task_id] = "running"

        # Start scanning thread
        thread = threading.Thread(
            target=self._scan_streams,
            args=(task_id, entries, address, username, password, channel),
            daemon=True
        )
        thread.start()
        self.scan_threads[task_id] = thread

    def _scan_streams(
        self,
        task_id: str,
        entries: List[Dict[str, Any]],
        address: str,
        username: str,
        password: str,
        channel: int
    ):
        """
        Internal method to perform stream scanning (runs in background thread)

        Scanning phases:
        1. ONVIF discovery (if available)
        2. Database patterns (if entries provided)
        3. Popular patterns (if not enough streams found)

        Stops when 7+ streams found or 5 minutes elapsed.
        """
        start_time = time.time()
        max_duration = 300  # 5 minutes
        max_streams = 7     # Stop after finding 7 streams

        try:
            logger.info(f"Starting scan for task {task_id}")

            # Phase 1: Try ONVIF discovery first
            logger.info(f"Phase 1: ONVIF discovery")
            onvif_streams = self._try_onvif_discovery(address, username, password)

            if onvif_streams:
                logger.info(f"ONVIF discovered {len(onvif_streams)} stream(s)")
                for stream_data in onvif_streams:
                    self.scan_results[task_id].append(stream_data)
                    self.scan_queues[task_id].put({
                        "type": "stream_found",
                        "data": json.dumps(stream_data)
                    })

                # Check if we already have enough streams
                if len(self.scan_results[task_id]) >= max_streams:
                    logger.info(f"Found {len(self.scan_results[task_id])} streams via ONVIF, stopping scan")
                    self.scan_status[task_id] = "completed"
                    self.scan_queues[task_id].put({"type": "scan_complete"})
                    return

            # Phase 2: Test database patterns
            if entries:
                logger.info(f"Phase 2: Testing {len(entries)} database patterns")
                test_urls = self._generate_test_urls(entries, address, username, password, channel)

                for url_info in test_urls:
                    # Check stop conditions
                    if self._should_stop(start_time, max_duration, len(self.scan_results[task_id]), max_streams):
                        logger.info("Stop condition met during database patterns phase")
                        break

                    result = self._test_stream(url_info)
                    if result["ok"]:
                        stream_data = result["stream"]
                        # Check for duplicates
                        existing_urls = [s.get("url") for s in self.scan_results[task_id]]
                        if stream_data.get("url") not in existing_urls:
                            self.scan_results[task_id].append(stream_data)
                            self.scan_queues[task_id].put({
                                "type": "stream_found",
                                "data": json.dumps(stream_data)
                            })
                            logger.info(f"Found stream {len(self.scan_results[task_id])}: {stream_data.get('notes', 'Unknown')}")

            # Phase 3: Test popular patterns (if not enough streams found)
            if len(self.scan_results[task_id]) < max_streams:
                elapsed = time.time() - start_time
                if elapsed < max_duration:
                    logger.info(f"Phase 3: Testing popular patterns (found {len(self.scan_results[task_id])} so far)")
                    popular_patterns = self._load_popular_patterns()
                    popular_urls = self._generate_test_urls(popular_patterns, address, username, password, channel)

                    for url_info in popular_urls:
                        # Check stop conditions
                        if self._should_stop(start_time, max_duration, len(self.scan_results[task_id]), max_streams):
                            logger.info("Stop condition met during popular patterns phase")
                            break

                        result = self._test_stream(url_info)
                        if result["ok"]:
                            stream_data = result["stream"]
                            # Check for duplicates
                            existing_urls = [s.get("url") for s in self.scan_results[task_id]]
                            if stream_data.get("url") not in existing_urls:
                                self.scan_results[task_id].append(stream_data)
                                self.scan_queues[task_id].put({
                                    "type": "stream_found",
                                    "data": json.dumps(stream_data)
                                })
                                logger.info(f"Found stream {len(self.scan_results[task_id])}: {stream_data.get('notes', 'Unknown')}")

            # Mark as complete
            self.scan_status[task_id] = "completed"
            self.scan_queues[task_id].put({"type": "scan_complete"})

            elapsed = time.time() - start_time
            logger.info(f"Scan {task_id} completed in {elapsed:.1f}s. Found {len(self.scan_results[task_id])} streams")

        except Exception as e:
            logger.error(f"Scan {task_id} failed: {e}", exc_info=True)
            self.scan_status[task_id] = "error"
            self.scan_queues[task_id].put({
                "type": "error",
                "message": str(e)
            })

        finally:
            # Cleanup
            if task_id in self.scan_threads:
                del self.scan_threads[task_id]

    def _should_stop(self, start_time: float, max_duration: float, found_count: int, max_streams: int) -> bool:
        """Check if scanning should stop"""
        elapsed = time.time() - start_time
        if found_count >= max_streams:
            logger.debug(f"Stop: found {found_count} >= {max_streams} streams")
            return True
        if elapsed >= max_duration:
            logger.debug(f"Stop: timeout {elapsed:.1f}s >= {max_duration}s")
            return True
        return False

    def _load_popular_patterns(self) -> List[Dict[str, Any]]:
        """Load popular stream patterns from JSON file"""
        patterns_file = Path(__file__).parent.parent.parent.parent / "connectors" / "cameras" / "data" / "popular_stream_patterns.json"

        if not patterns_file.exists():
            logger.warning(f"Popular patterns file not found: {patterns_file}")
            return []

        try:
            with open(patterns_file, 'r', encoding='utf-8') as f:
                patterns = json.load(f)
            logger.info(f"Loaded {len(patterns)} popular patterns")
            return patterns
        except Exception as e:
            logger.error(f"Failed to load popular patterns: {e}")
            return []

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

        Returns list of dicts with: {url, type, protocol, port, notes, username, password}
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
            # Curly brace format: {placeholder}
            url_path = url_path.replace("{username}", username or "")
            url_path = url_path.replace("{password}", password or "")
            url_path = url_path.replace("{ip}", host)
            url_path = url_path.replace("{port}", str(port))
            url_path = url_path.replace("{channel}", str(channel))

            # Bracket format: [PLACEHOLDER]
            url_path = url_path.replace("[USERNAME]", username or "")
            url_path = url_path.replace("[PASSWORD]", password or "")
            url_path = url_path.replace("[PASWORD]", password or "")  # Handle typo in database
            url_path = url_path.replace("[AUTH]", f"{username}:{password}" if username else "")
            url_path = url_path.replace("[CHANNEL]", str(channel))
            url_path = url_path.replace("[WIDTH]", "640")  # Default width
            url_path = url_path.replace("[HEIGHT]", "480")  # Default height
            url_path = url_path.replace("[TOKEN]", "")  # Tokens usually obtained separately

            # Ensure path starts with /
            if url_path and not url_path.startswith('/'):
                url_path = '/' + url_path

            # Build URL WITHOUT credentials (for HTTP) and WITHOUT standard ports
            # Standard ports: HTTP=80, HTTPS=443, RTSP=554
            is_standard_port = (
                (protocol == "http" and port == 80) or
                (protocol == "https" and port == 443) or
                (protocol == "rtsp" and port == 554)
            )

            if protocol in ["http", "https"]:
                # HTTP/HTTPS: NO credentials in URL (will use Basic Auth header)
                if is_standard_port:
                    full_url = f"{protocol}://{host}{url_path}"
                else:
                    full_url = f"{protocol}://{host}:{port}{url_path}"
            elif protocol == "rtsp":
                # RTSP: credentials IN URL
                if username and password:
                    if is_standard_port:
                        full_url = f"{protocol}://{username}:{password}@{host}{url_path}"
                    else:
                        full_url = f"{protocol}://{username}:{password}@{host}:{port}{url_path}"
                else:
                    if is_standard_port:
                        full_url = f"{protocol}://{host}{url_path}"
                    else:
                        full_url = f"{protocol}://{host}:{port}{url_path}"
            else:
                # Other protocols
                if is_standard_port:
                    full_url = f"{protocol}://{host}{url_path}"
                else:
                    full_url = f"{protocol}://{host}:{port}{url_path}"

            test_urls.append({
                "url": full_url,
                "type": entry.get("type", "FFMPEG"),
                "protocol": protocol,
                "port": port,
                "notes": entry.get("notes", ""),
                "username": username,
                "password": password,
                "priority": self._get_priority(entry.get("type", "FFMPEG"))
            })

        # Sort by priority (ONVIF first, then FFMPEG/RTSP, etc.)
        test_urls.sort(key=lambda x: x["priority"])

        # Log all generated URLs for debugging
        logger.info(f"Generated {len(test_urls)} test URLs:")
        for i, url_info in enumerate(test_urls[:10], 1):  # Log first 10 only
            # Mask credentials in log
            display_url = self._mask_credentials(url_info["url"])
            logger.info(f"  {i}. [{url_info['type']}] {display_url[:150]}")
        if len(test_urls) > 10:
            logger.info(f"  ... and {len(test_urls) - 10} more")

        return test_urls

    def _try_onvif_discovery(
        self,
        address: str,
        username: str,
        password: str,
        port: int = 80,
        timeout: int = 20
    ) -> List[Dict[str, Any]]:
        """
        Try ONVIF device discovery to get exact stream URLs (synchronous)

        Args:
            address: Camera IP address
            username: Camera username
            password: Camera password
            port: ONVIF port (default 80)
            timeout: Timeout in seconds

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

            # Create ONVIF camera instance (synchronous)
            try:
                mycam = ONVIFCamera(
                    host,
                    port,
                    username,
                    password,
                    wsdl_dir='/usr/local/lib/python3.11/site-packages/wsdl'
                )
            except Exception as e:
                logger.debug(f"Failed to create ONVIF camera: {e}")
                return []

            # Get media service
            try:
                media_service = mycam.create_media_service()
                profiles = media_service.GetProfiles()
            except Exception as e:
                logger.debug(f"Failed to get media profiles: {e}")
                return []

            if not profiles:
                logger.debug(f"No ONVIF media profiles found on {host}")
                return []

            logger.info(f"Found {len(profiles)} ONVIF media profile(s) on {host}")

            # Extract stream URIs from profiles
            for idx, profile in enumerate(profiles):
                try:
                    obj = media_service.create_type('GetStreamUri')
                    obj.ProfileToken = profile.token
                    obj.StreamSetup = {
                        'Stream': 'RTP-Unicast',
                        'Transport': {'Protocol': 'RTSP'}
                    }
                    uri_response = media_service.GetStreamUri(obj)
                    stream_uri = uri_response.Uri

                    if stream_uri:
                        # Parse ONVIF stream URI
                        parsed_uri = urlparse(stream_uri)

                        # Build clean URL without embedded credentials
                        clean_path = parsed_uri.path
                        if parsed_uri.query:
                            clean_path += f"?{parsed_uri.query}"

                        # Mask credentials for display
                        masked_url = self._mask_credentials(stream_uri)

                        discovered_streams.append({
                            "type": "ONVIF",
                            "protocol": "rtsp",
                            "port": parsed_uri.port or 554,
                            "url": masked_url,
                            "full_url": stream_uri,
                            "notes": f"ONVIF Profile {idx + 1}: {profile.Name if hasattr(profile, 'Name') else f'Stream {idx + 1}'}"
                        })

                        logger.info(f"ONVIF stream {idx + 1}: {masked_url}")

                except Exception as e:
                    logger.debug(f"Error processing profile {idx}: {e}")
                    continue

            if discovered_streams:
                logger.info(f"ONVIF discovery successful: found {len(discovered_streams)} stream(s)")
            else:
                logger.debug(f"ONVIF discovery found no usable streams on {host}")

        except Exception as e:
            logger.debug(f"ONVIF discovery failed for {address}: {e}")

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

    def _test_stream(self, url_info: Dict[str, Any]) -> Dict[str, Any]:
        """
        Test a single stream URL (synchronous)

        Returns: {"ok": bool, "stream": {...} or None}
        """
        url = url_info["url"]
        stream_type = url_info["type"]
        protocol = url_info["protocol"]

        logger.debug(f"Testing stream: {url[:80]}... (type={stream_type}, protocol={protocol})")

        try:
            if protocol == "rtsp" or stream_type == "FFMPEG":
                result = self._test_rtsp(url_info)
                logger.debug(f"RTSP test result for {url[:50]}...: ok={result['ok']}")
                return result
            elif protocol in ["http", "https"]:
                result = self._test_http(url_info)
                logger.debug(f"HTTP test result for {url[:50]}...: ok={result['ok']}")
                return result
            else:
                logger.warning(f"Unknown protocol '{protocol}' for {url[:50]}...")
                return {"ok": False, "stream": None}

        except Exception as e:
            logger.error(f"Stream test exception for {url[:50]}...: {e}")
            return {"ok": False, "stream": None}

    def _test_rtsp(self, url_info: Dict[str, Any]) -> Dict[str, Any]:
        """Test RTSP stream using ffprobe (synchronous)"""
        url = url_info["url"]
        masked_url = self._mask_credentials(url)

        logger.info(f"Testing RTSP: {masked_url[:150]}")

        try:
            # Run ffprobe with timeout
            result = subprocess.run(
                [
                    "ffprobe",
                    "-v", "error",
                    "-rtsp_transport", "tcp",
                    "-timeout", "8000000",  # 8 second timeout
                    "-print_format", "json",
                    "-show_streams",
                    url
                ],
                capture_output=True,
                timeout=10
            )

            # Check if stream is accessible
            if result.returncode == 0 and result.stdout:
                logger.info(f"✓ RTSP stream accessible: {masked_url[:150]}")
                return {
                    "ok": True,
                    "stream": {
                        "type": url_info["type"],
                        "protocol": url_info["protocol"],
                        "url": masked_url,
                        "full_url": url,
                        "port": url_info["port"],
                        "notes": url_info.get("notes", "")
                    }
                }
            else:
                error_msg = result.stderr.decode().strip() if result.stderr else "No error output"
                logger.info(f"✗ RTSP test failed (code={result.returncode}): {masked_url[:100]}")
                if error_msg and error_msg != "No error output":
                    logger.debug(f"  ffprobe error: {error_msg[:200]}")

        except subprocess.TimeoutExpired:
            logger.info(f"✗ RTSP test timeout (10s): {masked_url[:100]}")
        except FileNotFoundError:
            logger.error("ffprobe not found - RTSP testing disabled!")
        except Exception as e:
            logger.warning(f"✗ RTSP test exception for {masked_url[:100]}: {e}")

        return {"ok": False, "stream": None}

    def _test_http(self, url_info: Dict[str, Any]) -> Dict[str, Any]:
        """
        Test HTTP/JPEG stream using GET request with Basic Auth (synchronous)

        Uses GET instead of HEAD and validates JPEG magic bytes
        """
        url = url_info["url"]
        username = url_info.get("username", "")
        password = url_info.get("password", "")

        try:
            # Use GET request with Basic Auth header
            cmd = [
                "curl",
                "-s",  # Silent
                "--connect-timeout", "3",
                "--max-time", "8",
            ]

            # Add Basic Auth if credentials provided
            if username and password:
                cmd.extend(["-u", f"{username}:{password}"])

            cmd.append(url)

            result = subprocess.run(cmd, capture_output=True, timeout=10)

            # Log response
            masked_url = self._mask_credentials(url)

            # Check for JPEG magic bytes (FF D8 FF)
            if result.returncode == 0 and len(result.stdout) >= 4:
                # JPEG starts with FF D8 FF
                if result.stdout[:3] == b'\xff\xd8\xff':
                    logger.info(f"✓ HTTP stream accessible (JPEG validated): {masked_url[:100]}")
                    return {
                        "ok": True,
                        "stream": {
                            "type": url_info["type"],
                            "protocol": url_info["protocol"],
                            "url": masked_url,
                            "full_url": url,
                            "port": url_info["port"],
                            "notes": url_info.get("notes", "")
                        }
                    }
                else:
                    logger.debug(f"✗ HTTP response not a valid JPEG: {masked_url[:100]}")
            else:
                logger.debug(f"✗ HTTP stream failed (code {result.returncode}): {masked_url[:100]}")

        except subprocess.TimeoutExpired:
            logger.info(f"✗ HTTP test timeout (10s): {self._mask_credentials(url)[:100]}")
        except Exception as e:
            logger.warning(f"✗ HTTP test error for {self._mask_credentials(url)[:100]}: {e}")

        return {"ok": False, "stream": None}

    def _mask_credentials(self, url: str) -> str:
        """Mask username and password in URL"""
        try:
            parsed = urlparse(url)
            if parsed.username or parsed.password:
                # Replace credentials with ***
                if parsed.port:
                    masked = parsed._replace(
                        netloc=f"***:***@{parsed.hostname}:{parsed.port}"
                    )
                else:
                    masked = parsed._replace(
                        netloc=f"***:***@{parsed.hostname}"
                    )
                return masked.geturl()
            return url
        except:
            return url

    def get_results_stream(self, task_id: str):
        """
        Get SSE event stream for scan results (generator for FastAPI StreamingResponse)

        Yields events: {"type": "stream_found", "data": {...}} or {"type": "scan_complete"}
        """
        if task_id not in self.scan_queues:
            yield {"type": "error", "message": "Scan not found"}
            return

        queue = self.scan_queues[task_id]

        while True:
            try:
                # Wait for next result with timeout
                event = queue.get(timeout=300)  # 5 min max

                yield event

                if event["type"] in ["scan_complete", "error"]:
                    break

            except Empty:
                yield {"type": "error", "message": "Scan timeout"}
                break

        # Cleanup
        if task_id in self.scan_queues:
            del self.scan_queues[task_id]

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
