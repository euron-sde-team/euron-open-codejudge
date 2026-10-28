"""HTTP endpoints for AI hints."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query

from codejudge.auth.dependencies import CurrentSubmitter
from codejudge.core.deps import ContainerDep, SessionDep
from codejudge.hints import service
from codejudge.hints.schemas import HintContext, HintOut, HintRequestIn, HintStatus

router = APIRouter(prefix="/api/v1", tags=["hints"])


@router.get("/hints/status", response_model=HintStatus, summary="Whether a hint can be asked for")
async def hint_status(
    who: CurrentSubmitter,
    session: SessionDep,
    problem: Annotated[str, Query(max_length=64)],
    context: HintContext = "practice",
) -> HintStatus:
    return await service.status(session, who, problem, context)


@router.post("/hints", response_model=HintOut, summary="Ask the AI tutor for a hint")
async def ask(
    body: HintRequestIn, who: CurrentSubmitter, session: SessionDep, container: ContainerDep
) -> HintOut:
    return await service.request(container, session, who, body)
