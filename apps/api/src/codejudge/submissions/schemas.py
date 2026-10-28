"""Request and response models for submissions and runs."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import Field

from codejudge.core.schemas import ApiModel

Context = Literal["practice", "contest", "assignment", "assessment"]


class SubmissionCreate(ApiModel):
    problem: str = Field(description="Problem id or slug")
    language: str
    source: str = Field(max_length=200_000)
    context: Context = "practice"
    context_id: uuid.UUID | None = None


class RunCreate(ApiModel):
    problem: str
    language: str
    source: str = Field(max_length=200_000)
    # None: run on the problem's samples. A string: run on this input instead.
    input: str | None = Field(None, max_length=1_000_000)
    context: Context = "practice"
    context_id: uuid.UUID | None = None


class TestOut(ApiModel):
    name: str
    group: str
    verdict: str
    time_ms: int
    memory_kb: int
    # Samples only.
    output: str | None = None
    message: str | None = None


class SubmissionOut(ApiModel):
    id: uuid.UUID
    problem_id: uuid.UUID
    problem_slug: str | None
    problem_title: str | None
    user_id: uuid.UUID | None
    language: str
    context: str
    context_id: uuid.UUID | None
    status: Literal["queued", "judging", "done"]
    verdict: str
    score: float
    max_score: float
    time_ms: int | None
    memory_kb: int | None
    late: bool
    progress: str | None
    created_at: datetime
    judged_at: datetime | None
    compile_output: str | None = None
    source: str | None = None
    tests: list[TestOut] = Field(default_factory=list)
    groups: list[dict[str, Any]] = Field(default_factory=list)
    run_input: str | None = None
    run_output: str | None = None
    error: str | None = None
    worker: str | None = None
    user_name: str | None = None


class RejudgeRequest(ApiModel):
    ids: list[uuid.UUID] = Field(min_length=1, max_length=5000)
    latest_version: bool = False


class RejudgeResult(ApiModel):
    queued: int


class QueueStatus(ApiModel):
    waiting: int
    in_progress: int
    workers: int
