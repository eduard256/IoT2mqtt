"""
Connectors API endpoints
"""

from fastapi import APIRouter, Depends, HTTPException
from typing import Optional, List

router = APIRouter(prefix="/api/connectors", tags=["Connectors"])

# Note: The actual endpoints are currently in main.py
# This module exists to satisfy imports