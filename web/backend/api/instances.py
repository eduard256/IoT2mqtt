"""
Instances API endpoints
"""

from fastapi import APIRouter, Depends, HTTPException
from typing import Optional, List

router = APIRouter(prefix="/api/instances", tags=["Instances"])

# Note: The actual endpoints are currently in main.py
# This module exists to satisfy imports