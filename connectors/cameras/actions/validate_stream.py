#!/usr/bin/env python3
"""
Validate Camera Stream
Deep validation of selected camera stream to ensure it's working properly
"""

import json
import sys
import subprocess
from typing import Any, Dict
from urllib.parse import urlparse


def parse_frame_rate(rate_str: str) -> float:
    """
    Безопасный парсинг r_frame_rate из ffprobe

    Форматы: "30/1", "25/1", "30000/1001"
    Возвращает: 30.0, 25.0, 29.97
    """
    try:
        if not rate_str or not isinstance(rate_str, str):
            return 0.0

        # Если нет дроби, пробуем прямую конвертацию
        if "/" not in rate_str:
            return float(rate_str)

        # Парсим дробь
        parts = rate_str.split("/", 1)  # Только первый разделитель
        numerator = int(parts[0])
        denominator = int(parts[1])

        if denominator == 0:
            return 0.0

        return round(numerator / denominator, 2)

    except (ValueError, IndexError, AttributeError):
        # Любая ошибка парсинга - возвращаем 0
        return 0.0


def load_payload() -> Dict[str, Any]:
    """Load input payload from stdin"""
    raw = sys.stdin.read().strip() or "{}"
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return {}

    if "input" in payload and isinstance(payload["input"], dict):
        return payload["input"]
    return payload


def validate_rtsp_stream(url: str, timeout: int = 10) -> Dict[str, Any]:
    """
    Validate RTSP stream using ffprobe

    Returns: {"ok": bool, "error": {...} or "result": {...}}
    """
    try:
        # Run ffprobe to get stream info
        result = subprocess.run(
            [
                "ffprobe",
                "-v", "error",
                "-rtsp_transport", "tcp",
                "-timeout", str(timeout * 1000000),  # microseconds
                "-print_format", "json",
                "-show_format",
                "-show_streams",
                url
            ],
            capture_output=True,
            timeout=timeout + 5,
            text=True
        )

        if result.returncode != 0:
            return {
                "ok": False,
                "error": {
                    "code": "stream_unreachable",
                    "message": f"Cannot connect to RTSP stream: {result.stderr}",
                    "retriable": True
                }
            }

        # Parse output
        try:
            stream_info = json.loads(result.stdout)
        except json.JSONDecodeError:
            return {
                "ok": False,
                "error": {
                    "code": "invalid_stream",
                    "message": "Stream format is not valid",
                    "retriable": False
                }
            }

        # Check if we have video streams
        streams = stream_info.get("streams", [])
        video_streams = [s for s in streams if s.get("codec_type") == "video"]

        if not video_streams:
            return {
                "ok": False,
                "error": {
                    "code": "no_video",
                    "message": "No video stream found",
                    "retriable": False
                }
            }

        # Extract useful info
        video_stream = video_streams[0]
        audio_streams = [s for s in streams if s.get("codec_type") == "audio"]

        return {
            "ok": True,
            "result": {
                "stream_type": "RTSP",
                "video_codec": video_stream.get("codec_name", "unknown"),
                "resolution": f"{video_stream.get('width', 0)}x{video_stream.get('height', 0)}",
                "fps": parse_frame_rate(video_stream.get("r_frame_rate", "0/1")),
                "has_audio": len(audio_streams) > 0,
                "audio_codec": audio_streams[0].get("codec_name") if audio_streams else None,
                "duration": stream_info.get("format", {}).get("duration"),
                "validated": True
            }
        }

    except subprocess.TimeoutExpired:
        return {
            "ok": False,
            "error": {
                "code": "timeout",
                "message": f"Stream validation timeout after {timeout} seconds",
                "retriable": True
            }
        }
    except FileNotFoundError:
        return {
            "ok": False,
            "error": {
                "code": "missing_dependency",
                "message": "ffprobe is not installed",
                "retriable": False
            }
        }
    except Exception as e:
        return {
            "ok": False,
            "error": {
                "code": "validation_error",
                "message": str(e),
                "retriable": True
            }
        }


def validate_http_stream(url: str, timeout: int = 10) -> Dict[str, Any]:
    """
    Validate HTTP/MJPEG stream using GET request with Basic Auth

    Returns: {"ok": bool, "error": {...} or "result": {...}}
    """
    try:
        # Extract credentials from URL query parameters
        # Support formats: ?user=X&pwd=Y, ?username=X&password=Y
        from urllib.parse import urlparse, parse_qs

        parsed = urlparse(url)
        query_params = parse_qs(parsed.query)

        username = None
        password = None

        # Check for credentials in query params
        if 'user' in query_params:
            username = query_params['user'][0]
        elif 'username' in query_params:
            username = query_params['username'][0]

        if 'pwd' in query_params:
            password = query_params['pwd'][0]
        elif 'password' in query_params:
            password = query_params['password'][0]

        # Build curl command with GET request and Basic Auth if credentials found
        cmd = ["curl", "-s", "-L"]  # Silent, follow redirects

        if username and password:
            # Use HTTP Basic Auth header
            cmd.extend(["-u", f"{username}:{password}"])

        cmd.extend([
            "--connect-timeout", str(timeout),
            "--max-time", str(timeout),
            url
        ])

        result = subprocess.run(
            cmd,
            capture_output=True,
            timeout=timeout + 5
        )

        if result.returncode != 0:
            return {
                "ok": False,
                "error": {
                    "code": "stream_unreachable",
                    "message": "Cannot connect to HTTP stream",
                    "retriable": True
                }
            }

        # Check for JPEG magic bytes (FF D8 FF E0 or FF D8 FF E1)
        if len(result.stdout) >= 4:
            magic_bytes = result.stdout[:4]
            if magic_bytes[:3] == b'\xff\xd8\xff':
                # Valid JPEG image
                return {
                    "ok": True,
                    "result": {
                        "stream_type": "JPEG",
                        "content_type": "image/jpeg",
                        "validated": True,
                        "size_bytes": len(result.stdout)
                    }
                }
            elif magic_bytes == b'--BoundaryString':
                # MJPEG multipart stream
                return {
                    "ok": True,
                    "result": {
                        "stream_type": "MJPEG",
                        "content_type": "multipart/x-mixed-replace",
                        "validated": True
                    }
                }

        # If we got data but it's not a recognized format
        return {
            "ok": False,
            "error": {
                "code": "invalid_stream",
                "message": "Response is not a valid JPEG or MJPEG stream",
                "retriable": False
            }
        }

    except subprocess.TimeoutExpired:
        return {
            "ok": False,
            "error": {
                "code": "timeout",
                "message": f"Stream validation timeout after {timeout} seconds",
                "retriable": True
            }
        }
    except FileNotFoundError:
        return {
            "ok": False,
            "error": {
                "code": "missing_dependency",
                "message": "curl is not installed",
                "retriable": False
            }
        }
    except Exception as e:
        return {
            "ok": False,
            "error": {
                "code": "validation_error",
                "message": str(e),
                "retriable": True
            }
        }


def main() -> None:
    payload = load_payload()

    stream_url = payload.get("stream_url") or payload.get("full_url")
    stream_type = payload.get("stream_type", "FFMPEG")
    username = payload.get("username", "")
    password = payload.get("password", "")

    if not stream_url:
        print(json.dumps({
            "ok": False,
            "error": {
                "code": "missing_parameter",
                "message": "stream_url is required",
                "retriable": False
            }
        }))
        return

    # Parse URL to determine protocol
    try:
        parsed = urlparse(stream_url)
        protocol = parsed.scheme.lower()
    except:
        protocol = "unknown"

    # For ONVIF streams: inject credentials if URL doesn't have them
    if stream_type == "ONVIF" and protocol == "rtsp":
        # Check if URL already has credentials
        if not parsed.username and not parsed.password:
            # URL has no credentials, but we have username/password - inject them
            if username and password:
                # Rebuild URL with credentials
                if parsed.port:
                    netloc_with_auth = f"{username}:{password}@{parsed.hostname}:{parsed.port}"
                else:
                    netloc_with_auth = f"{username}:{password}@{parsed.hostname}"

                parsed = parsed._replace(netloc=netloc_with_auth)
                stream_url = parsed.geturl()

    # Validate based on protocol
    if protocol == "rtsp" or stream_type == "FFMPEG":
        result = validate_rtsp_stream(stream_url)
    elif protocol in ["http", "https"]:
        result = validate_http_stream(stream_url)
    else:
        result = {
            "ok": False,
            "error": {
                "code": "unsupported_protocol",
                "message": f"Protocol '{protocol}' is not supported",
                "retriable": False
            }
        }

    print(json.dumps(result))


if __name__ == '__main__':
    main()
