"""HTTP endpoints for the hints domain."""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(prefix="/api/v1", tags=["hints"])
