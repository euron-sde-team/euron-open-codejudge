"""HTTP endpoints for contests: browsing and registering for everyone, the scoreboard and
clarifications for participants, everything that shapes a contest for staff."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Query, Response
from sqlalchemy import func, select

from codejudge.audit.service import Actor
from codejudge.auth.dependencies import CurrentSubmitter, OptionalSubmitter, Staff
from codejudge.contests import service
from codejudge.contests.schemas import (
    Announcement,
    ClarificationIn,
    ClarificationOut,
    ContestCreate,
    ContestOut,
    ContestProblemIn,
    ContestProblemOut,
    ContestSummary,
    ContestUpdate,
    JoinRequest,
    MyStatus,
    ProblemOrder,
    Scoreboard,
)
from codejudge.core.contexts import Submitter
from codejudge.core.deps import ContainerDep, SessionDep
from codejudge.core.schemas import ApiModel
from codejudge.problems.models import Problem
from codejudge.problems.schemas import ProblemOut
from codejudge.submissions import service as submissions
from codejudge.submissions.schemas import SubmissionOut

router = APIRouter(prefix="/api/v1", tags=["contests"])


class ContestSubmissionPage(ApiModel):
    items: list[SubmissionOut]
    total: int


def _staff(actor: Actor) -> Submitter:
    return Submitter(user_id=actor.id, candidate_id=None, role=actor.role)


@router.get("/contests", response_model=list[ContestSummary])
async def list_contests(who: OptionalSubmitter, session: SessionDep) -> list[ContestSummary]:
    return await service.list_contests(session, who)


@router.post("/contests", response_model=ContestOut, status_code=201)
async def create_contest(body: ContestCreate, actor: Staff, session: SessionDep) -> ContestOut:
    c = await service.create(session, body, actor)
    return await service.detail(session, _staff(actor), c)


@router.post("/contests/join", response_model=ContestOut)
async def join(
    body: JoinRequest, who: CurrentSubmitter, session: SessionDep, container: ContainerDep
) -> ContestOut:
    c = await service.join(container, session, who, body.code)
    return await service.detail(session, who, c)


@router.get("/contests/{ref}", response_model=ContestOut)
async def get_contest(ref: str, who: OptionalSubmitter, session: SessionDep) -> ContestOut:
    return await service.detail(session, who, await service.get(session, ref))


@router.patch("/contests/{contest_id}", response_model=ContestOut)
async def update_contest(
    contest_id: uuid.UUID,
    body: ContestUpdate,
    actor: Staff,
    session: SessionDep,
    container: ContainerDep,
) -> ContestOut:
    c = await service.update(
        container, session, await service.get(session, contest_id), body, actor
    )
    return await service.detail(session, _staff(actor), c)


@router.delete("/contests/{contest_id}", status_code=204)
async def delete_contest(contest_id: uuid.UUID, actor: Staff, session: SessionDep) -> Response:
    await service.delete(session, await service.get(session, contest_id), actor)
    return Response(status_code=204)


@router.post(
    "/contests/{contest_id}/problems", response_model=list[ContestProblemOut], status_code=201
)
async def add_problem(
    contest_id: uuid.UUID,
    body: ContestProblemIn,
    actor: Staff,
    session: SessionDep,
    container: ContainerDep,
) -> list[ContestProblemOut]:
    return await service.add_problem(
        container, session, await service.get(session, contest_id), body, actor
    )


@router.delete("/contests/{contest_id}/problems/{label}", status_code=204)
async def remove_problem(
    contest_id: uuid.UUID, label: str, actor: Staff, session: SessionDep, container: ContainerDep
) -> Response:
    await service.remove_problem(
        container, session, await service.get(session, contest_id), label, actor
    )
    return Response(status_code=204)


@router.put("/contests/{contest_id}/problems/order", response_model=list[ContestProblemOut])
async def reorder(
    contest_id: uuid.UUID,
    body: ProblemOrder,
    actor: Staff,
    session: SessionDep,
    container: ContainerDep,
) -> list[ContestProblemOut]:
    return await service.reorder(
        container, session, await service.get(session, contest_id), body.labels, actor
    )


@router.get("/contests/{ref}/problems/{label}", response_model=ProblemOut)
async def contest_problem(
    ref: str, label: str, who: CurrentSubmitter, session: SessionDep
) -> ProblemOut:
    return await service.problem(session, who, await service.get(session, ref), label)


@router.post("/contests/{ref}/register", response_model=MyStatus)
async def register(
    ref: str, who: CurrentSubmitter, session: SessionDep, container: ContainerDep
) -> MyStatus:
    c = await service.get(session, ref)
    await service.register(container, session, who, c)
    return await service.my_status(container, session, who, c)


@router.get("/contests/{ref}/me", response_model=MyStatus)
async def my_status(
    ref: str, who: CurrentSubmitter, session: SessionDep, container: ContainerDep
) -> MyStatus:
    return await service.my_status(container, session, who, await service.get(session, ref))


@router.get("/contests/{ref}/scoreboard", response_model=Scoreboard)
async def scoreboard(
    ref: str, who: OptionalSubmitter, session: SessionDep, container: ContainerDep
) -> Scoreboard:
    return await service.scoreboard(container, session, who, await service.get(session, ref))


@router.post("/contests/{contest_id}/unfreeze", response_model=ContestOut)
async def unfreeze(
    contest_id: uuid.UUID, actor: Staff, session: SessionDep, container: ContainerDep
) -> ContestOut:
    c = await service.unfreeze(container, session, await service.get(session, contest_id), actor)
    return await service.detail(session, _staff(actor), c)


@router.get("/contests/{ref}/clarifications", response_model=list[ClarificationOut])
async def clarifications(
    ref: str, who: CurrentSubmitter, session: SessionDep
) -> list[ClarificationOut]:
    return await service.clarifications(session, who, await service.get(session, ref))


@router.post("/contests/{ref}/clarifications", response_model=ClarificationOut, status_code=201)
async def ask(
    ref: str, body: ClarificationIn, who: CurrentSubmitter, session: SessionDep
) -> ClarificationOut:
    return await service.ask(session, who, await service.get(session, ref), body)


@router.post(
    "/contests/{contest_id}/announcements", response_model=ClarificationOut, status_code=201
)
async def announce(
    contest_id: uuid.UUID, body: Announcement, actor: Staff, session: SessionDep
) -> ClarificationOut:
    return await service.answer(
        session, _staff(actor), await service.get(session, contest_id), None, body, actor
    )


@router.post(
    "/contests/{contest_id}/clarifications/{clar_id}/answer", response_model=ClarificationOut
)
async def answer(
    contest_id: uuid.UUID, clar_id: uuid.UUID, body: Announcement, actor: Staff, session: SessionDep
) -> ClarificationOut:
    return await service.answer(
        session, _staff(actor), await service.get(session, contest_id), clar_id, body, actor
    )


@router.get("/contests/{contest_id}/submissions", response_model=ContestSubmissionPage)
async def contest_submissions(
    contest_id: uuid.UUID,
    actor: Staff,
    session: SessionDep,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> ContestSubmissionPage:
    """Every submission of the contest (staff): who, which problem, when, the verdict."""
    c = await service.get(session, contest_id)
    query = service.contest_submissions_query(c)
    total = int(await session.scalar(select(func.count()).select_from(query.subquery())) or 0)
    rows = (await session.execute(query.limit(limit).offset(offset))).all()
    probs = {
        p.id: p
        for p in (
            await session.scalars(
                select(Problem).where(Problem.id.in_({s.problem_id for s, _ in rows}))
            )
        ).all()
    }
    who = _staff(actor)
    items = []
    for s, name in rows:
        out = submissions.to_out(s, probs.get(s.problem_id), who, with_source=False)
        out.user_name = name
        items.append(out)
    return ContestSubmissionPage(items=items, total=total)
