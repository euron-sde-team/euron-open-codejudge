"""HTTP endpoints for plagiarism checks (staff only)."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Query

from codejudge.auth.dependencies import Staff
from codejudge.core.deps import SessionDep
from codejudge.plagiarism import service
from codejudge.plagiarism.schemas import PairDetail, RunCreate, RunDetail, RunOut, Scope

router = APIRouter(prefix="/api/v1/plagiarism", tags=["plagiarism"])


@router.post("/runs", response_model=RunOut, status_code=202, summary="Start a similarity check")
async def start_run(body: RunCreate, actor: Staff, session: SessionDep) -> RunOut:
    return service.run_out(await service.start(session, body, actor))


@router.get("/runs", response_model=list[RunOut], summary="Similarity checks, newest first")
async def list_runs(
    _: Staff,
    session: SessionDep,
    scope: Scope | None = None,
    scope_id: uuid.UUID | None = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> list[RunOut]:
    return await service.list_runs(session, scope, scope_id, limit)


@router.get("/runs/{run_id}", response_model=RunDetail, summary="A check and its flagged pairs")
async def get_run(run_id: uuid.UUID, _: Staff, session: SessionDep) -> RunDetail:
    return await service.detail(session, run_id)


@router.get("/pairs/{pair_id}", response_model=PairDetail, summary="Both programs of a pair")
async def get_pair(pair_id: uuid.UUID, _: Staff, session: SessionDep) -> PairDetail:
    return await service.pair_detail(session, pair_id)
