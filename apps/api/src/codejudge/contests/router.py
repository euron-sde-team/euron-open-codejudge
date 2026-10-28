"""HTTP endpoints for the contests domain."""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(prefix="/api/v1", tags=["contests"])
