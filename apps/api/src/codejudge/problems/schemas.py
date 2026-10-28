"""Request and response models for problems.

Responses to people who are not staff never carry hidden test content: ``ProblemOut``
exposes the samples only, and test listings with sizes and content are staff-only models.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import Field, field_validator

from codejudge.core.contract import CheckerSpec, GroupSpec
from codejudge.core.schemas import ApiModel

Difficulty = Literal["easy", "medium", "hard"]
Status = Literal["draft", "published"]
Visibility = Literal["public", "private"]
SLUG = r"^[a-z0-9][a-z0-9\-]{1,62}[a-z0-9]$"


class ProblemBase(ApiModel):
    title: str = Field(min_length=1, max_length=200)
    statement_md: str = Field("", max_length=200_000)
    difficulty: Difficulty = "medium"
    tags: list[str] = Field(default_factory=list, max_length=12)
    time_limit_ms: int = Field(2000, ge=100, le=60_000)
    memory_limit_mb: int = Field(256, ge=16, le=8192)
    output_limit_mb: int = Field(64, ge=1, le=1024)
    visibility: Visibility = "public"
    source: str | None = Field(None, max_length=200)
    license: str | None = Field(None, max_length=64)

    @field_validator("tags")
    @classmethod
    def _tags(cls, v: list[str]) -> list[str]:
        out = []
        for tag in v:
            t = tag.strip().lower()[:40]
            if t and t not in out:
                out.append(t)
        return out


class ProblemCreate(ProblemBase):
    slug: str = Field(pattern=SLUG)
    checker: CheckerSpec = CheckerSpec()


class ProblemUpdate(ApiModel):
    title: str | None = Field(None, min_length=1, max_length=200)
    slug: str | None = Field(None, pattern=SLUG)
    statement_md: str | None = Field(None, max_length=200_000)
    difficulty: Difficulty | None = None
    tags: list[str] | None = Field(None, max_length=12)
    time_limit_ms: int | None = Field(None, ge=100, le=60_000)
    memory_limit_mb: int | None = Field(None, ge=16, le=8192)
    output_limit_mb: int | None = Field(None, ge=1, le=1024)
    visibility: Visibility | None = None
    source: str | None = Field(None, max_length=200)
    license: str | None = Field(None, max_length=64)


class Sample(ApiModel):
    name: str
    input: str
    output: str


class LanguageOut(ApiModel):
    id: str
    name: str
    monaco: str
    template: str
    time_limit_ms: int | None = None


class ProblemSummary(ApiModel):
    id: uuid.UUID
    slug: str
    title: str
    difficulty: Difficulty
    tags: list[str]
    status: Status
    visibility: Visibility
    submissions_count: int
    accepted_count: int
    solvers_count: int
    acceptance: float | None = Field(None, description="Accepted submissions over judged ones")
    # For the signed-in user: "solved", "attempted" or null.
    mine: Literal["solved", "attempted"] | None = None
    updated_at: datetime


class ProblemOut(ProblemSummary):
    statement_md: str
    time_limit_ms: int
    memory_limit_mb: int
    output_limit_mb: int
    checker: Literal["exact", "tokens", "float", "custom"]
    max_score: float
    groups: list[GroupSpec]
    samples: list[Sample]
    languages: list[LanguageOut]
    source: str | None
    license: str | None
    version: int | None


# ── staff only ───────────────────────────────────────────────────────────────────────
class TestIn(ApiModel):
    """A test written in the problem editor (large tests come as a package upload)."""

    name: str = Field(pattern=r"^(sample|secret)/[A-Za-z0-9_\-/]{1,100}$")
    input: str = Field(max_length=5_000_000)
    answer: str = Field(max_length=5_000_000)


class VersionCreate(ApiModel):
    tests: list[TestIn] = Field(min_length=1, max_length=500)
    # Points per hidden group; groups not listed share what is left equally.
    groups: list[GroupSpec] = Field(default_factory=list, max_length=50)
    checker: CheckerSpec | None = None
    checker_source: str | None = Field(None, max_length=200_000)
    note: str | None = Field(None, max_length=200)


class TestMeta(ApiModel):
    name: str
    group: str
    sample: bool
    input_bytes: int
    answer_bytes: int


class VersionOut(ApiModel):
    id: uuid.UUID
    number: int
    package_sha256: str
    package_bytes: int
    tests: list[TestMeta]
    groups: list[GroupSpec]
    checker: CheckerSpec
    max_score: float
    note: str | None
    current: bool
    created_at: datetime


class ReferenceIn(ApiModel):
    name: str = Field(min_length=1, max_length=100)
    language: str
    source: str = Field(min_length=1, max_length=128_000)
    expected: Literal["AC", "WA", "TLE", "MLE", "RE"] = "AC"


class ReferenceOut(ApiModel):
    id: uuid.UUID
    name: str
    language: str
    expected: str
    source: str
    last_submission_id: uuid.UUID | None
    last_verdict: str | None = None
    last_status: str | None = None
    matches: bool | None = None


class ProblemAdmin(ProblemOut):
    """What staff see in the problem editor."""

    checker_spec: CheckerSpec
    versions: list[VersionOut]
    references: list[ReferenceOut]
    publishable: bool
    publish_blockers: list[str]


class ImportResult(ApiModel):
    problem: ProblemSummary
    tests: int
    groups: int
    references: int
    warnings: list[str]
