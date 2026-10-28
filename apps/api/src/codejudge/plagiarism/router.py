"""HTTP endpoints for the plagiarism domain."""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(prefix="/api/v1", tags=["plagiarism"])
