"""Request and response models for contests."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import Field, model_validator

from codejudge.core.schemas import ApiModel

Format = Literal["icpc", "ioi"]
Phase = Literal["upcoming", "running", "ended"]
SLUG = r"^[a-z0-9][a-z0-9\-]{1,62}[a-z0-9]$"
LABEL = r"^[A-Z][0-9]?$"


class ContestBase(ApiModel):
    title: str = Field(min_length=1, max_length=200)
    description_md: str = Field("", max_length=50_000)
    format: Format = "icpc"
    starts_at: datetime
    ends_at: datetime
    freeze_at: datetime | None = None
    visibility: Literal["public", "private"] = "public"
    registration: Literal["open", "invite"] = "open"
    penalty_minutes: int = Field(20, ge=0, le=240)

    @model_validator(mode="after")
    def _window(self) -> ContestBase:
        for name in ("starts_at", "ends_at", "freeze_at"):
            value = getattr(self, name)
            if value is not None and value.tzinfo is None:
                raise ValueError(f"{name} needs a time zone (for example 2026-11-01T10:00:00Z)")
        if self.ends_at <= self.starts_at:
            raise ValueError("The contest must end after it starts")
        if self.freeze_at and not self.starts_at <= self.freeze_at <= self.ends_at:
            raise ValueError("The freeze must fall inside the contest")
        return self


class ContestCreate(ContestBase):
    slug: str = Field(pattern=SLUG)


class ContestUpdate(ApiModel):
    title: str | None = Field(None, min_length=1, max_length=200)
    description_md: str | None = Field(None, max_length=50_000)
    format: Format | None = None
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    freeze_at: datetime | None = None
    visibility: Literal["public", "private"] | None = None
    registration: Literal["open", "invite"] | None = None
    penalty_minutes: int | None = Field(None, ge=0, le=240)


class ContestProblemIn(ApiModel):
    problem: str = Field(description="Problem id or slug")
    label: str | None = Field(None, pattern=LABEL)
    points: float = Field(100.0, gt=0, le=10_000)


class ProblemOrder(ApiModel):
    labels: list[str] = Field(min_length=1, max_length=26)


class ContestProblemOut(ApiModel):
    label: str
    problem_id: uuid.UUID
    slug: str
    title: str
    points: float
    position: int


class ContestSummary(ApiModel):
    id: uuid.UUID
    slug: str
    title: str
    format: Format
    starts_at: datetime
    ends_at: datetime
    freeze_at: datetime | None
    visibility: str
    registration: str
    phase: Phase
    participants: int
    registered: bool = False


class ContestOut(ContestSummary):
    description_md: str
    penalty_minutes: int
    unfrozen: bool
    # Empty before the start for everyone but staff: the problem set is part of the contest.
    problems: list[ContestProblemOut]
    # Staff only.
    join_code: str | None = None


class JoinRequest(ApiModel):
    code: str = Field(min_length=4, max_length=16)


class CellOut(ApiModel):
    label: str
    solved: bool
    attempts: int
    pending: int
    minute: int | None
    score: float
    first: bool


class RowOut(ApiModel):
    rank: int
    user_id: uuid.UUID
    name: str
    solved: int
    penalty: int
    score: float
    cells: list[CellOut]


class Scoreboard(ApiModel):
    contest_id: uuid.UUID
    format: Format
    phase: Phase
    # True when this view hides results after the freeze.
    frozen: bool
    freeze_at: datetime | None
    problems: list[ContestProblemOut]
    rows: list[RowOut]


class MyStatus(ApiModel):
    registered: bool
    phase: Phase
    row: RowOut | None


class ClarificationIn(ApiModel):
    question: str = Field(min_length=1, max_length=4000)
    problem_label: str | None = Field(None, pattern=LABEL)


class Announcement(ApiModel):
    """Staff: an answer to a question, or (without a question id) a public announcement."""

    answer: str = Field(min_length=1, max_length=4000)
    public: bool = False


class ClarificationOut(ApiModel):
    id: uuid.UUID
    problem_label: str | None
    question: str
    answer: str | None
    public: bool
    mine: bool
    asked_by_name: str | None = None
    created_at: datetime
    answered_at: datetime | None
