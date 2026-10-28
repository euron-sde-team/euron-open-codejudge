"""HTTP endpoints for classes, rosters, assignments and gradebooks."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response

from codejudge.audit.service import Actor
from codejudge.auth.dependencies import CurrentSubmitter, Staff
from codejudge.classrooms import service
from codejudge.classrooms.models import Assignment
from codejudge.classrooms.schemas import (
    AssignmentCreate,
    AssignmentOut,
    AssignmentUpdate,
    ClassCreate,
    ClassOut,
    ClassUpdate,
    ExtensionIn,
    Gradebook,
    JoinRequest,
    MemberAdd,
    MemberOut,
)
from codejudge.core.contexts import Submitter
from codejudge.core.deps import SessionDep
from codejudge.core.errors import PermissionDeniedError
from codejudge.problems import service as problems
from codejudge.problems.schemas import ProblemOut

router = APIRouter(prefix="/api/v1", tags=["classrooms"])


@dataclass(frozen=True)
class Person:
    who: Submitter
    actor: Actor


async def person(request: Request, who: CurrentSubmitter) -> Person:
    """A signed-in account (interview candidates have no classes)."""
    actor: Actor | None = getattr(request.state, "actor", None)
    if who.user_id is None or actor is None:
        raise PermissionDeniedError(
            "Sign in with an account to use classes", code="account_required"
        )
    return Person(who, actor)


Me = Annotated[Person, Depends(person)]


@router.get("/classes", response_model=list[ClassOut])
async def list_classes(me: Me, session: SessionDep, archived: bool = False) -> list[ClassOut]:
    return await service.list_classes(session, me.who, include_archived=archived)


@router.post("/classes", response_model=ClassOut, status_code=201)
async def create_class(body: ClassCreate, actor: Staff, me: Me, session: SessionDep) -> ClassOut:
    c = await service.create_class(session, body, actor)
    return await service.class_out(session, c, me.who)


@router.post("/classes/join", response_model=ClassOut)
async def join_class(body: JoinRequest, me: Me, session: SessionDep) -> ClassOut:
    c = await service.join(session, body.code, me.who, me.actor)
    return await service.class_out(session, c, me.who)


@router.get("/classes/{class_id}", response_model=ClassOut)
async def get_class(class_id: uuid.UUID, me: Me, session: SessionDep) -> ClassOut:
    return await service.class_out(session, await service.get_class(session, class_id), me.who)


@router.patch("/classes/{class_id}", response_model=ClassOut)
async def update_class(
    class_id: uuid.UUID, body: ClassUpdate, me: Me, session: SessionDep
) -> ClassOut:
    c = await service.get_class(session, class_id)
    await service.require_manager(session, c, me.who)
    return await service.class_out(
        session, await service.update_class(session, c, body, me.actor), me.who
    )


@router.post("/classes/{class_id}/rotate-code", response_model=ClassOut)
async def rotate_code(class_id: uuid.UUID, me: Me, session: SessionDep) -> ClassOut:
    c = await service.get_class(session, class_id)
    await service.require_manager(session, c, me.who)
    return await service.class_out(session, await service.rotate_code(session, c, me.actor), me.who)


@router.delete("/classes/{class_id}", status_code=204)
async def delete_class(class_id: uuid.UUID, me: Me, session: SessionDep) -> Response:
    c = await service.get_class(session, class_id)
    await service.require_manager(session, c, me.who)
    await service.delete_class(session, c, me.actor)
    return Response(status_code=204)


@router.get("/classes/{class_id}/members", response_model=list[MemberOut])
async def members(class_id: uuid.UUID, me: Me, session: SessionDep) -> list[MemberOut]:
    c = await service.get_class(session, class_id)
    await service.require_member(session, c, me.who)
    await service.require_manager(session, c, me.who)
    return await service.members(session, c)


@router.post("/classes/{class_id}/members", status_code=204)
async def add_member(class_id: uuid.UUID, body: MemberAdd, me: Me, session: SessionDep) -> Response:
    c = await service.get_class(session, class_id)
    await service.require_manager(session, c, me.who)
    await service.add_member(session, c, body.email, body.role, me.actor)
    return Response(status_code=204)


@router.delete("/classes/{class_id}/members/{user_id}", status_code=204)
async def remove_member(
    class_id: uuid.UUID, user_id: uuid.UUID, me: Me, session: SessionDep
) -> Response:
    c = await service.get_class(session, class_id)
    # Teachers remove anyone; a student may leave on their own.
    if user_id != me.who.user_id:
        await service.require_manager(session, c, me.who)
    await service.remove_member(session, c, user_id, me.actor)
    return Response(status_code=204)


@router.get("/classes/{class_id}/assignments", response_model=list[AssignmentOut])
async def class_assignments(
    class_id: uuid.UUID, me: Me, session: SessionDep
) -> list[AssignmentOut]:
    return await service.class_assignments(
        session, await service.get_class(session, class_id), me.who
    )


@router.post("/classes/{class_id}/assignments", response_model=AssignmentOut, status_code=201)
async def create_assignment(
    class_id: uuid.UUID, body: AssignmentCreate, me: Me, session: SessionDep
) -> AssignmentOut:
    c = await service.get_class(session, class_id)
    await service.require_manager(session, c, me.who)
    a = await service.create_assignment(session, c, body, me.actor)
    return (await service.assignment_for(session, a, me.who))[0]


@router.get("/my/assignments", response_model=list[AssignmentOut])
async def my_assignments(me: Me, session: SessionDep) -> list[AssignmentOut]:
    return await service.my_assignments(session, me.who)


@router.get("/assignments/{assignment_id}", response_model=AssignmentOut)
async def get_assignment(assignment_id: uuid.UUID, me: Me, session: SessionDep) -> AssignmentOut:
    return (
        await service.assignment_for(
            session, await service.get_assignment(session, assignment_id), me.who
        )
    )[0]


async def _managed(session: SessionDep, assignment_id: uuid.UUID, me: Person) -> Assignment:
    a = await service.get_assignment(session, assignment_id)
    await service.require_manager(session, await service.get_class(session, a.class_id), me.who)
    return a


@router.patch("/assignments/{assignment_id}", response_model=AssignmentOut)
async def update_assignment(
    assignment_id: uuid.UUID, body: AssignmentUpdate, me: Me, session: SessionDep
) -> AssignmentOut:
    a = await service.update_assignment(
        session, await _managed(session, assignment_id, me), body, me.actor
    )
    return (await service.assignment_for(session, a, me.who))[0]


@router.delete("/assignments/{assignment_id}", status_code=204)
async def delete_assignment(assignment_id: uuid.UUID, me: Me, session: SessionDep) -> Response:
    await service.delete_assignment(session, await _managed(session, assignment_id, me), me.actor)
    return Response(status_code=204)


@router.put("/assignments/{assignment_id}/extensions", status_code=204)
async def set_extension(
    assignment_id: uuid.UUID, body: ExtensionIn, me: Me, session: SessionDep
) -> Response:
    a = await _managed(session, assignment_id, me)
    await service.set_extension(session, a, body.user_id, body.due_at, me.actor)
    return Response(status_code=204)


@router.get("/assignments/{assignment_id}/problems/{ref}", response_model=ProblemOut)
async def assignment_problem(
    assignment_id: uuid.UUID, ref: str, me: Me, session: SessionDep
) -> ProblemOut:
    a = await service.get_assignment(session, assignment_id)
    p = await service.assignment_problem(session, a, ref, me.who)
    return await problems.detail(session, p, me.who, check_access=False)


@router.get("/assignments/{assignment_id}/gradebook", response_model=Gradebook)
async def gradebook(assignment_id: uuid.UUID, me: Me, session: SessionDep) -> Gradebook:
    return await service.gradebook(session, await _managed(session, assignment_id, me))


@router.get("/assignments/{assignment_id}/gradebook.csv")
async def gradebook_csv(assignment_id: uuid.UUID, me: Me, session: SessionDep) -> Response:
    a = await _managed(session, assignment_id, me)
    book = await service.gradebook(session, a)
    name = (
        "".join(ch if ch.isalnum() else "-" for ch in a.title.lower()).strip("-")[:60]
        or "assignment"
    )
    return Response(
        service.gradebook_csv(book),
        media_type="text/csv; charset=utf-8",
        headers={
            "content-disposition": f'attachment; filename="{name}-grades.csv"',
            "cache-control": "no-store",
        },
    )
