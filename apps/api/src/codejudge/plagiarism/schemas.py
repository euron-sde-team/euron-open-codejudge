"""Request and response models for plagiarism checks."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import Field

from codejudge.core.schemas import ApiModel

Scope = Literal["problem", "contest", "assignment"]


class PlagiarismRunCreate(ApiModel):
    scope: Scope
    scope_id: str = Field(
        description="Problem id or slug, contest id or assignment id", max_length=64
    )
    threshold: float = Field(0.5, ge=0.1, le=1.0)


class RunOut(ApiModel):
    id: uuid.UUID
    scope: Scope
    scope_id: uuid.UUID
    # The problem, contest or assignment title, for lists (None if it was deleted).
    scope_title: str | None = None
    threshold: float
    status: Literal["queued", "running", "done", "failed"]
    documents: int
    comparisons: int
    flagged: int
    error: str | None
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None


class Side(ApiModel):
    submission_id: uuid.UUID
    author: str
    user_id: uuid.UUID | None
    verdict: str
    score: float
    created_at: datetime
    coverage: float
    ranges: list[tuple[int, int]]


class PairOut(ApiModel):
    id: uuid.UUID
    problem_id: uuid.UUID
    problem_slug: str
    problem_title: str
    language: str
    similarity: float
    a: Side
    b: Side


class RunDetail(RunOut):
    pairs: list[PairOut]


class PairDetail(PairOut):
    run_id: uuid.UUID
    source_a: str
    source_b: str
