"""Request and response models for interview assessments and candidates."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import Field, model_validator

from codejudge.core.schemas import ApiModel, Email
from codejudge.problems.schemas import ProblemOut

InvitationStatus = Literal["invited", "started", "submitted", "expired", "revoked"]
EventKind = Literal["paste", "tab_hidden", "tab_visible"]


class AssessmentProblemIn(ApiModel):
    problem: str = Field(description="Problem id or slug")
    points: float = Field(100.0, ge=0, le=10_000)


class AssessmentCreate(ApiModel):
    title: str = Field(min_length=1, max_length=200)
    instructions_md: str = Field("", max_length=50_000)
    duration_minutes: int = Field(60, ge=1, le=24 * 60)
    opens_at: datetime | None = None
    closes_at: datetime | None = None
    problems: list[AssessmentProblemIn] = Field(min_length=1, max_length=20)

    @model_validator(mode="after")
    def _window(self) -> AssessmentCreate:
        if self.opens_at and self.closes_at and self.closes_at <= self.opens_at:
            raise ValueError("closes_at must be after opens_at")
        return self


class AssessmentUpdate(ApiModel):
    title: str | None = Field(None, min_length=1, max_length=200)
    instructions_md: str | None = Field(None, max_length=50_000)
    duration_minutes: int | None = Field(None, ge=1, le=24 * 60)
    opens_at: datetime | None = None
    closes_at: datetime | None = None
    problems: list[AssessmentProblemIn] | None = Field(None, min_length=1, max_length=20)


class AssessmentProblemOut(ApiModel):
    id: uuid.UUID
    slug: str
    title: str
    difficulty: str
    points: float


class InvitationCounts(ApiModel):
    invited: int = 0
    started: int = 0
    submitted: int = 0
    expired: int = 0
    revoked: int = 0


class AssessmentOut(ApiModel):
    id: uuid.UUID
    title: str
    instructions_md: str
    duration_minutes: int
    opens_at: datetime | None
    closes_at: datetime | None
    total_points: float
    problems: list[AssessmentProblemOut]
    invitations: InvitationCounts
    created_at: datetime


class InviteIn(ApiModel):
    email: Email
    name: str = Field("", max_length=200)


class InviteRequest(ApiModel):
    candidates: list[InviteIn] = Field(min_length=1, max_length=200)


class InvitationOut(ApiModel):
    id: uuid.UUID
    assessment_id: uuid.UUID
    email: str
    name: str
    status: InvitationStatus
    sent_at: datetime | None
    started_at: datetime | None
    deadline_at: datetime | None
    submitted_at: datetime | None
    score: float | None = None
    signals: int = 0
    created_at: datetime


class InviteResult(ApiModel):
    invitations: list[InvitationOut]
    # Emails the mail backend refused (the invitation exists; resend later).
    failed: list[str] = Field(default_factory=list)


# ── candidate side ───────────────────────────────────────────────────────────────────
class CandidateSessionIn(ApiModel):
    token: str = Field(min_length=20, max_length=200)


class CandidateProblem(ApiModel):
    points: float
    best_score: float | None
    best_verdict: str | None
    problem: ProblemOut


class CandidateView(ApiModel):
    """Everything a candidate's page needs, and nothing about anyone else."""

    invitation_id: uuid.UUID
    name: str
    title: str
    instructions_md: str
    status: InvitationStatus
    started_at: datetime | None
    deadline_at: datetime | None
    now: datetime
    seconds_left: int
    total_points: float
    problems: list[CandidateProblem]


class EventIn(ApiModel):
    kind: EventKind
    detail: dict[str, Any] = Field(default_factory=dict)


# ── report ───────────────────────────────────────────────────────────────────────────
class ReportSubmission(ApiModel):
    id: uuid.UUID
    problem_id: uuid.UUID
    problem_slug: str
    language: str
    verdict: str
    score: float
    max_score: float
    time_ms: int | None
    memory_kb: int | None
    source: str
    created_at: datetime


class ReportProblem(ApiModel):
    id: uuid.UUID
    slug: str
    title: str
    points: float
    earned: float
    best_verdict: str | None
    attempts: int


class ReportEvent(ApiModel):
    kind: str
    at: datetime
    detail: dict[str, Any]


class Report(ApiModel):
    invitation: InvitationOut
    assessment_title: str
    duration_minutes: int
    total_points: float
    total: float
    minutes_used: float | None
    problems: list[ReportProblem]
    submissions: list[ReportSubmission]
    events: list[ReportEvent]
    signals_note: str
