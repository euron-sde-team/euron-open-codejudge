"""HTTP endpoints for analytics: staff see everything, a student sees their own progress."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Query

from codejudge.analytics import service
from codejudge.analytics.schemas import Overview, ProblemStats, UserProgress
from codejudge.auth.dependencies import CurrentUser, Staff
from codejudge.core.deps import SessionDep
from codejudge.core.errors import NotFoundError
from codejudge.problems import service as problems

router = APIRouter(prefix="/api/v1/analytics", tags=["analytics"])
Days = Annotated[int, Query(ge=1, le=365)]


@router.get("/overview", response_model=Overview, summary="Submissions, verdicts and problems")
async def overview(_: Staff, session: SessionDep, days: Days = 30) -> Overview:
    return await service.overview(session, days)


@router.get("/problems/{ref}", response_model=ProblemStats, summary="One problem's statistics")
async def problem(ref: str, _: Staff, session: SessionDep, days: Days = 30) -> ProblemStats:
    return await service.problem_stats(session, await problems.get(session, ref), days)


@router.get("/me", response_model=UserProgress, summary="Your own progress")
async def me(user: CurrentUser, session: SessionDep, days: Days = 30) -> UserProgress:
    return await service.user_progress(session, user.id, days)


@router.get("/users/{user_id}", response_model=UserProgress, summary="A user's progress")
async def user(
    user_id: uuid.UUID, viewer: CurrentUser, session: SessionDep, days: Days = 30
) -> UserProgress:
    # Students may read their own progress only; anyone else's looks like it does not exist.
    if viewer.id != user_id and viewer.role not in ("staff", "admin"):
        raise NotFoundError("User not found")
    return await service.user_progress(session, user_id, days)
