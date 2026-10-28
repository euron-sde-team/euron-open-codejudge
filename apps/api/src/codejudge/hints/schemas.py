"""Request and response models for AI hints."""

from __future__ import annotations

import uuid
from typing import Literal

from pydantic import Field

from codejudge.core.schemas import ApiModel

HintContext = Literal["practice", "assignment", "contest", "assessment"]


class HintRequestIn(ApiModel):
    problem: str = Field(description="Problem id or slug")
    language: str = Field(max_length=32)
    source: str = Field("", max_length=200_000)
    submission_id: uuid.UUID | None = Field(
        None, description="The submission to explain; your latest one for the problem if omitted"
    )
    question: str | None = Field(None, max_length=1000)
    context: HintContext = "practice"
    context_id: uuid.UUID | None = None


class HintOut(ApiModel):
    hint: str
    model: str
    used: int
    limit: int
    remaining: int


class HintStatus(ApiModel):
    """Whether hints can be asked for here, and why not when they cannot."""

    available: bool
    reason: str | None = None
    used: int = 0
    limit: int = 0
    remaining: int = 0
