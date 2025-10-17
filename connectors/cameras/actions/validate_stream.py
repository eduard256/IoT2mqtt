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
                "fps": eval(video_stream.get("r_frame_rate", "0/1").split("/")[0]) if "/" in video_stream.get("r_frame_rate", "") else 0,
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
    Validate HTTP/MJPEG stream

    Returns: {"ok": bool, "error": {...} or "result": {...}}
    """
    try:
        # Try to fetch first few bytes
        result = subprocess.run(
            [
                "curl",
                "-s",
                "-I",  # HEAD request
                "-L",  # Follow redirects
                "--connect-timeout", str(timeout),
                "--max-time", str(timeout),
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
                    "message": "Cannot connect to HTTP stream",
                    "retriable": True
                }
            }

        # Check status code
        headers = result.stdout
        if "200 OK" not in headers and "200" not in headers.split("\n")[0]:
            return {
                "ok": False,
                "error": {
                    "code": "http_error",
                    "message": "HTTP stream returned error status",
                    "retriable": True
                }
            }

        # Check content type
        content_type = ""
        for line in headers.split("\n"):
            if line.lower().startswith("content-type:"):
                content_type = line.split(":", 1)[1].strip().lower()
                break

        # Determine stream type
        if "multipart" in content_type or "mjpeg" in content_type:
            stream_type = "MJPEG"
        elif "image" in content_type:
            stream_type = "JPEG"
        else:
            stream_type = "HTTP"

        return {
            "ok": True,
            "result": {
                "stream_type": stream_type,
                "content_type": content_type,
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
