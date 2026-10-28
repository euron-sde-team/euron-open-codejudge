"""HTTP endpoints for submissions, runs, live verdicts and the judge's internal calls."""

from __future__ import annotations

import asyncio
import hmac
import json
import uuid
from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, Response
from fastapi.responses import StreamingResponse
from sqlalchemy import select

from codejudge.auth.dependencies import CurrentSubmitter, Staff
from codejudge.core.contexts import Submitter
from codejudge.core.contract import Heartbeat, JudgeResult
from codejudge.core.deps import ContainerDep, SessionDep
from codejudge.core.errors import AuthenticationError, NotFoundError
from codejudge.core.schemas import ApiModel
from codejudge.core.storage import ObjectNotFoundError
from codejudge.problems import service as problems
from codejudge.problems.models import Problem
from codejudge.problems.service import package_key
from codejudge.submissions import service
from codejudge.submissions.models import Submission
from codejudge.submissions.schemas import (
    QueueStatus,
    RejudgeRequest,
    RejudgeResult,
    RunCreate,
    SubmissionCreate,
    SubmissionOut,
)
from codejudge.users.models import User

router = APIRouter(prefix="/api/v1", tags=["submissions"])
internal = APIRouter(prefix="/internal/judge", tags=["internal"], include_in_schema=False)


class SubmissionPage(ApiModel):
    items: list[SubmissionOut]
    total: int


async def _out(
    session: SessionDep, s: Submission, who: Submitter, *, with_source: bool
) -> SubmissionOut:
    p = await session.get(Problem, s.problem_id)
    return service.to_out(s, p, who, with_source=with_source)


@router.post("/submissions", response_model=SubmissionOut, status_code=202)
async def create_submission(
    body: SubmissionCreate, who: CurrentSubmitter, session: SessionDep, container: ContainerDep
) -> SubmissionOut:
    p = await problems.get(session, body.problem)
    s = await service.submit(
        container,
        session,
        who,
        p,
        language=body.language,
        source=body.source,
        context=body.context,
        context_id=body.context_id,
    )
    return service.to_out(s, p, who, with_source=True)


@router.post("/runs", response_model=SubmissionOut, status_code=202)
async def create_run(
    body: RunCreate, who: CurrentSubmitter, session: SessionDep, container: ContainerDep
) -> SubmissionOut:
    p = await problems.get(session, body.problem)
    s = await service.run(
        container,
        session,
        who,
        p,
        language=body.language,
        source=body.source,
        custom_input=body.input,
        context=body.context,
        context_id=body.context_id,
    )
    return service.to_out(s, p, who, with_source=True)


@router.get("/submissions", response_model=SubmissionPage)
async def list_submissions(
    who: CurrentSubmitter,
    session: SessionDep,
    problem: Annotated[str | None, Query(max_length=64)] = None,
    user_id: uuid.UUID | None = None,
    verdict: Annotated[str | None, Query(max_length=8)] = None,
    context: Annotated[str | None, Query(max_length=16)] = None,
    context_id: uuid.UUID | None = None,
    mine: bool = False,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> SubmissionPage:
    """Your own submissions; staff see everyone's (filter by user, problem, verdict)."""
    from sqlalchemy import func

    query = select(Submission).where(Submission.context != "run")
    if mine or not who.is_staff:
        query = (
            query.where(Submission.user_id == who.user_id)
            if who.user_id
            else query.where(Submission.candidate_id == who.candidate_id)
        )
        if not who.is_staff:
            query = query.where(Submission.context != "reference")
    elif user_id:
        query = query.where(Submission.user_id == user_id)
    if problem:
        query = query.where(Submission.problem_id == (await problems.get(session, problem)).id)
    if verdict:
        query = query.where(Submission.verdict == verdict.upper())
    if context:
        query = query.where(Submission.context == context)
    if context_id:
        query = query.where(Submission.context_id == context_id)
    total = int(await session.scalar(select(func.count()).select_from(query.subquery())) or 0)
    rows = list(
        (
            await session.scalars(
                query.order_by(Submission.created_at.desc()).limit(limit).offset(offset)
            )
        ).all()
    )
    probs = {
        p.id: p
        for p in (
            await session.scalars(
                select(Problem).where(Problem.id.in_({s.problem_id for s in rows}))
            )
        ).all()
    }
    names = {
        u.id: u.name
        for u in (
            await session.scalars(
                select(User).where(User.id.in_({s.user_id for s in rows if s.user_id}))
            )
        ).all()
    }
    items = []
    for s in rows:
        out = service.to_out(s, probs.get(s.problem_id), who, with_source=False)
        out.user_name = names.get(s.user_id) if s.user_id else None
        items.append(out)
    return SubmissionPage(items=items, total=total)


@router.get("/submissions/{submission_id}", response_model=SubmissionOut)
async def get_submission(
    submission_id: uuid.UUID, who: CurrentSubmitter, session: SessionDep
) -> SubmissionOut:
    s = await service.get(session, submission_id)
    if not await service.visible(session, who, s):
        raise NotFoundError("Submission not found")
    return await _out(session, s, who, with_source=True)


@router.get("/submissions/{submission_id}/events")
async def submission_events(
    submission_id: uuid.UUID,
    request: Request,
    who: CurrentSubmitter,
    session: SessionDep,
    container: ContainerDep,
) -> StreamingResponse:
    """Server-sent events until the verdict: ``judging`` updates, then ``done``.

    Events arrive through a subscription read by a separate task, so a quiet stream never
    disturbs it. Every few quiet seconds the stream also reads the submission itself, so a
    verdict published before the subscription started is still delivered and the stream
    always ends."""
    s = await service.get(session, submission_id)
    if not await service.visible(session, who, s):
        raise NotFoundError("Submission not found")
    # An ICPC contest or an interview shows the verdict only: no score, no test number.
    hide = s.hide_test_details and not who.is_staff

    def event(status: str, verdict: str, progress: str | None, score: float) -> str:
        payload: dict[str, object] = {"status": status, "verdict": verdict}
        if not hide:
            payload |= {"progress": progress, "score": score}
        return f"data: {json.dumps(payload)}\n\n"

    first = event(s.status, s.verdict, s.progress, s.score)
    done = s.status == "done"
    await session.close()  # do not hold a database connection for the life of the stream

    async def stream() -> AsyncIterator[str]:
        yield first
        if done:
            return
        inbox: asyncio.Queue[str] = asyncio.Queue()

        async def pump() -> None:
            async for data in container.queue.listen(str(submission_id)):
                await inbox.put(data)

        reader = asyncio.create_task(pump())
        try:
            while True:
                try:
                    data = await asyncio.wait_for(inbox.get(), timeout=5)
                except TimeoutError:
                    if await request.is_disconnected():
                        return
                    async with container.db.sessionmaker() as db:
                        row = await db.get(Submission, submission_id)
                    if row is not None and row.status == "done":
                        yield event(row.status, row.verdict, None, row.score)
                        return
                    yield ": keep-alive\n\n"
                    continue
                payload = json.loads(data)
                yield event(
                    payload.get("status", "judging"),
                    payload.get("verdict", "JUDGING"),
                    payload.get("progress"),
                    float(payload.get("score", 0.0)),
                )
                if payload.get("status") == "done":
                    return
        finally:
            reader.cancel()

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"cache-control": "no-cache, no-transform", "x-accel-buffering": "no"},
    )


@router.post("/submissions/rejudge", response_model=RejudgeResult)
async def rejudge(
    body: RejudgeRequest, actor: Staff, session: SessionDep, container: ContainerDep
) -> RejudgeResult:
    return RejudgeResult(
        queued=await service.rejudge(
            container, session, body.ids, actor, latest_version=body.latest_version
        )
    )


@router.get("/judge/queue", response_model=QueueStatus)
async def queue_status(_: Staff, container: ContainerDep) -> QueueStatus:
    return QueueStatus(**await container.queue.depth())


# ── internal: judge workers only ─────────────────────────────────────────────────────
def judge_only(request: Request, container: ContainerDep) -> None:
    header = request.headers.get("authorization", "")
    token = header[7:] if header.lower().startswith("bearer ") else ""
    if not token or not hmac.compare_digest(
        token.encode(), container.settings.judge_token.encode()
    ):
        raise AuthenticationError("Judge token required", code="judge_token_required")


JudgeOnly = Annotated[None, Depends(judge_only)]


@internal.get("/packages/{sha256}")
async def package(sha256: str, _: JudgeOnly, container: ContainerDep) -> Response:
    if len(sha256) != 64 or any(c not in "0123456789abcdef" for c in sha256):
        raise NotFoundError("Package not found")
    try:
        data = await container.storage.get(package_key(sha256))
    except ObjectNotFoundError as exc:
        raise NotFoundError("Package not found") from exc
    return Response(data, media_type="application/zip")


@internal.post("/results")
async def results(
    body: JudgeResult, _: JudgeOnly, session: SessionDep, container: ContainerDep
) -> Response:
    applied = await service.ingest(container, session, body)
    return Response(status_code=200 if applied else 409)


@internal.post("/heartbeat", status_code=204)
async def heartbeat(
    body: Heartbeat, _: JudgeOnly, session: SessionDep, container: ContainerDep
) -> Response:
    await service.heartbeat(container, session, body)
    return Response(status_code=204)
