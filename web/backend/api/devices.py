"""
Devices API endpoints
"""

from fastapi import APIRouter, Depends, HTTPException
from typing import Optional, List

router = APIRouter(prefix="/api/devices", tags=["Devices"])

# Note: The actual endpoints are currently in main.py
# This module exists to satisfy imports