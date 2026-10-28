"""HTTP endpoints for problems. Reading is open to everyone (published, public problems);
everything that creates or changes a problem, its tests or its checker is staff only."""

from __future__ import annotations

import uuid
from typing import Annotated, Literal

from fastapi import APIRouter, File, Form, Query, Response, UploadFile
from sqlalchemy import select

from codejudge.auth.dependencies import CurrentSubmitter, OptionalSubmitter, Staff
from codejudge.core.deps import ContainerDep, SessionDep
from codejudge.core.errors import AppError
from codejudge.core.schemas import ApiModel
from codejudge.problems import service
from codejudge.problems.models import Problem
from codejudge.problems.schemas import (
    ImportResult,
    LanguageOut,
    ProblemAdmin,
    ProblemCreate,
    ProblemOut,
    ProblemSummary,
    ProblemUpdate,
    ReferenceIn,
    ReferenceOut,
    VersionCreate,
    VersionOut,
)
from codejudge.submissions import service as submissions

router = APIRouter(prefix="/api/v1", tags=["problems"])


class ProblemPage(ApiModel):
    items: list[ProblemSummary]
    total: int


class TagCount(ApiModel):
    tag: str
    problems: int


class Judged(ApiModel):
    queued: int


async def _upload(file: UploadFile, limit: int) -> bytes:
    data = await file.read(limit + 1)
    if len(data) > limit:
        raise AppError("The upload is larger than the package limit", code="package_too_large")
    return data


@router.get("/languages", response_model=list[LanguageOut])
async def languages() -> list[LanguageOut]:
    return service.languages_out()


@router.get("/problems", response_model=ProblemPage)
async def list_problems(
    who: OptionalSubmitter,
    session: SessionDep,
    q: Annotated[str | None, Query(max_length=80)] = None,
    tag: Annotated[str | None, Query(max_length=40)] = None,
    difficulty: Literal["easy", "medium", "hard"] | None = None,
    status: Literal["draft", "published"] | None = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> ProblemPage:
    items, total = await service.list_problems(
        session, who, q=q, tag=tag, difficulty=difficulty, status=status, limit=limit, offset=offset
    )
    return ProblemPage(items=items, total=total)


@router.get("/problem-tags", response_model=list[TagCount])
async def tags(session: SessionDep) -> list[TagCount]:
    from sqlalchemy import func

    tag = func.unnest(Problem.tags).label("tag")
    sub = (
        select(tag).where(Problem.status == "published", Problem.visibility == "public").subquery()
    )
    rows = await session.execute(
        select(sub.c.tag, func.count())
        .group_by(sub.c.tag)
        .order_by(func.count().desc(), sub.c.tag)
        .limit(60)
    )
    return [TagCount(tag=t, problems=n) for t, n in rows.all()]


@router.get("/problems/{ref}", response_model=ProblemOut)
async def get_problem(ref: str, who: OptionalSubmitter, session: SessionDep) -> ProblemOut:
    return await service.detail(session, await service.get(session, ref), who)


@router.post("/problems", response_model=ProblemSummary, status_code=201)
async def create_problem(
    body: ProblemCreate, actor: Staff, session: SessionDep, container: ContainerDep
) -> ProblemSummary:
    service.check_limits(container.settings, body.time_limit_ms, body.memory_limit_mb)
    return service.summary(await service.create(session, body, actor))


@router.get("/problems/{ref}/admin", response_model=ProblemAdmin)
async def problem_admin(
    ref: str, _: Staff, who: CurrentSubmitter, session: SessionDep
) -> ProblemAdmin:
    return await service.admin_detail(session, await service.get(session, ref), who)


@router.patch("/problems/{problem_id}", response_model=ProblemSummary)
async def update_problem(
    problem_id: uuid.UUID,
    body: ProblemUpdate,
    actor: Staff,
    session: SessionDep,
    container: ContainerDep,
) -> ProblemSummary:
    service.check_limits(container.settings, body.time_limit_ms, body.memory_limit_mb)
    return service.summary(
        await service.update(session, await service.get(session, problem_id), body, actor)
    )


@router.delete("/problems/{problem_id}", status_code=204)
async def delete_problem(problem_id: uuid.UUID, actor: Staff, session: SessionDep) -> Response:
    await service.delete(session, await service.get(session, problem_id), actor)
    return Response(status_code=204)


@router.post("/problems/{problem_id}/publish", response_model=ProblemSummary)
async def publish(problem_id: uuid.UUID, actor: Staff, session: SessionDep) -> ProblemSummary:
    return service.summary(
        await service.set_status(
            session, await service.get(session, problem_id), "published", actor
        )
    )


@router.post("/problems/{problem_id}/unpublish", response_model=ProblemSummary)
async def unpublish(problem_id: uuid.UUID, actor: Staff, session: SessionDep) -> ProblemSummary:
    return service.summary(
        await service.set_status(session, await service.get(session, problem_id), "draft", actor)
    )


@router.post("/problems/{problem_id}/versions", response_model=VersionOut, status_code=201)
async def create_version(
    problem_id: uuid.UUID,
    body: VersionCreate,
    actor: Staff,
    session: SessionDep,
    container: ContainerDep,
) -> VersionOut:
    p = await service.get(session, problem_id)
    v = await service.create_version(container, session, p, body, actor)
    return service._version_out(v, v.id)


@router.post("/problems/{problem_id}/package", response_model=VersionOut, status_code=201)
async def upload_package(
    problem_id: uuid.UUID,
    actor: Staff,
    session: SessionDep,
    container: ContainerDep,
    file: Annotated[UploadFile, File()],
) -> VersionOut:
    p = await service.get(session, problem_id)
    v = await service.replace_package(
        container, session, p, await _upload(file, container.settings.max_package_bytes), actor
    )
    return service._version_out(v, v.id)


@router.post("/problems/import", response_model=ImportResult, status_code=201)
async def import_problem(
    actor: Staff,
    session: SessionDep,
    container: ContainerDep,
    file: Annotated[UploadFile, File()],
    slug: Annotated[str | None, Form(pattern=r"^[a-z0-9][a-z0-9\-]{1,62}[a-z0-9]$")] = None,
) -> ImportResult:
    return await service.import_package(
        container, session, await _upload(file, container.settings.max_package_bytes), actor, slug
    )


@router.get("/problems/{problem_id}/export")
async def export_problem(
    problem_id: uuid.UUID, actor: Staff, session: SessionDep, container: ContainerDep
) -> Response:
    p = await service.get(session, problem_id)
    data = await service.export(container, session, p)
    from codejudge.audit.service import audit

    audit(session, actor, "problem.exported", "problem", p.id)
    await session.commit()
    return Response(
        data,
        media_type="application/zip",
        headers={
            "content-disposition": f'attachment; filename="{p.slug}.zip"',
            "cache-control": "no-store",
        },
    )


@router.get("/problems/{problem_id}/tests/{name:path}")
async def get_test_content(
    problem_id: uuid.UUID,
    name: str,
    _: Staff,
    session: SessionDep,
    container: ContainerDep,
    part: Literal["input", "answer"] = "input",
) -> Response:
    data = await service.test_content(
        container, session, await service.get(session, problem_id), name, part
    )
    return Response(
        data, media_type="text/plain; charset=utf-8", headers={"cache-control": "no-store"}
    )


@router.post("/problems/{problem_id}/references", response_model=ReferenceOut, status_code=201)
async def add_reference(
    problem_id: uuid.UUID, body: ReferenceIn, actor: Staff, session: SessionDep
) -> ReferenceOut:
    p = await service.get(session, problem_id)
    r = await service.add_reference(session, p, body, actor)
    return next(x for x in await service.references(session, p) if x.id == r.id)


@router.delete("/problems/{problem_id}/references/{ref_id}", status_code=204)
async def remove_reference(
    problem_id: uuid.UUID, ref_id: uuid.UUID, actor: Staff, session: SessionDep
) -> Response:
    await service.remove_reference(session, await service.get(session, problem_id), ref_id, actor)
    return Response(status_code=204)


@router.post("/problems/{problem_id}/references/judge", response_model=Judged)
async def judge_references(
    problem_id: uuid.UUID, actor: Staff, session: SessionDep, container: ContainerDep
) -> Judged:
    p = await service.get(session, problem_id)
    return Judged(queued=await submissions.judge_reference(container, session, p, actor))


@router.post("/problems/{problem_id}/rejudge", response_model=Judged)
async def rejudge_problem(
    problem_id: uuid.UUID, actor: Staff, session: SessionDep, container: ContainerDep
) -> Judged:
    p = await service.get(session, problem_id)
    return Judged(queued=await submissions.rejudge_problem(container, session, p, actor))
