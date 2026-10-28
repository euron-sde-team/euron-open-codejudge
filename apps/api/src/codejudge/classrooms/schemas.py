"""Request and response models for classes, assignments and gradebooks."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import Field, model_validator

from codejudge.core.schemas import ApiModel

LatePolicy = Literal["accept", "penalty", "refuse"]
MemberRole = Literal["teacher", "student"]
AssignmentStatus = Literal["upcoming", "open", "late", "closed"]


class ClassCreate(ApiModel):
    name: str = Field(min_length=1, max_length=200)
    description: str = Field("", max_length=5000)


class ClassUpdate(ApiModel):
    name: str | None = Field(None, min_length=1, max_length=200)
    description: str | None = Field(None, max_length=5000)
    archived: bool | None = None


class ClassOut(ApiModel):
    id: uuid.UUID
    name: str
    description: str
    archived: bool
    # Only for teachers of the class and staff.
    join_code: str | None = None
    my_role: MemberRole | None = None
    students: int = 0
    teachers: int = 0
    assignments: int = 0
    created_at: datetime


class JoinRequest(ApiModel):
    code: str = Field(min_length=4, max_length=16)


class MemberOut(ApiModel):
    user_id: uuid.UUID
    name: str
    email: str
    role: MemberRole
    joined_at: datetime


class MemberAdd(ApiModel):
    email: str = Field(min_length=3, max_length=320)
    role: MemberRole = "student"


class AssignmentProblemIn(ApiModel):
    problem: str = Field(description="Problem id or slug")
    points: float = Field(100.0, ge=0, le=10_000)


class AssignmentCreate(ApiModel):
    title: str = Field(min_length=1, max_length=200)
    description_md: str = Field("", max_length=100_000)
    opens_at: datetime
    due_at: datetime
    late_policy: LatePolicy = "penalty"
    penalty_percent: int = Field(20, ge=0, le=100)
    problems: list[AssignmentProblemIn] = Field(min_length=1, max_length=50)

    @model_validator(mode="after")
    def _window(self) -> AssignmentCreate:
        if self.due_at <= self.opens_at:
            raise ValueError("due_at must be after opens_at")
        return self


class AssignmentUpdate(ApiModel):
    title: str | None = Field(None, min_length=1, max_length=200)
    description_md: str | None = Field(None, max_length=100_000)
    opens_at: datetime | None = None
    due_at: datetime | None = None
    late_policy: LatePolicy | None = None
    penalty_percent: int | None = Field(None, ge=0, le=100)
    problems: list[AssignmentProblemIn] | None = Field(None, min_length=1, max_length=50)


class ExtensionIn(ApiModel):
    user_id: uuid.UUID
    due_at: datetime


class AssignmentProblemOut(ApiModel):
    id: uuid.UUID
    slug: str
    title: str
    difficulty: str
    points: float
    # For a student: their best score on it (scaled to the points), if they tried.
    my_score: float | None = None
    my_verdict: str | None = None


class AssignmentOut(ApiModel):
    id: uuid.UUID
    class_id: uuid.UUID
    title: str
    description_md: str
    opens_at: datetime
    due_at: datetime
    # The due time that applies to the person asking (an extension moves it).
    my_due_at: datetime
    late_policy: LatePolicy
    penalty_percent: int
    status: AssignmentStatus
    total_points: float
    my_total: float | None = None
    problems: list[AssignmentProblemOut]


class GradeCell(ApiModel):
    problem_id: uuid.UUID
    score: float | None
    late: bool = False
    attempts: int = 0


class GradeRow(ApiModel):
    user_id: uuid.UUID
    name: str
    email: str
    total: float
    cells: list[GradeCell]


class Gradebook(ApiModel):
    assignment_id: uuid.UUID
    title: str
    problems: list[AssignmentProblemOut]
    total_points: float
    rows: list[GradeRow]
