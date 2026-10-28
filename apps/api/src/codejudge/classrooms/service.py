"""Classes, rosters, assignments and gradebooks.

Who may do what: staff create classes and become their first teacher; teachers of a class
(and admins) manage it; students join with the class code. Submissions for an assignment
are admitted by ``AssignmentPolicy`` (registered as the ``assignment`` context): members
only, from the opening time, and after the due time according to the late policy.

The gradebook reads the submissions table directly (one query per gradebook, whatever the
class size): a student's mark on a problem is their best submission, scaled to the
problem's points, with the late penalty applied to late ones.
"""

from __future__ import annotations

import csv
import io
import secrets
import uuid
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from codejudge.audit.service import Actor, audit
from codejudge.classrooms.models import (
    Assignment,
    AssignmentExtension,
    AssignmentProblem,
    ClassMember,
    Classroom,
)
from codejudge.classrooms.schemas import (
    AssignmentCreate,
    AssignmentOut,
    AssignmentProblemIn,
    AssignmentProblemOut,
    AssignmentUpdate,
    ClassCreate,
    ClassOut,
    ClassUpdate,
    Gradebook,
    GradeCell,
    GradeRow,
    MemberOut,
)
from codejudge.core import contexts
from codejudge.core.contexts import Admission, Submitter
from codejudge.core.errors import AppError, ConflictError, NotFoundError, PermissionDeniedError
from codejudge.problems import service as problems
from codejudge.problems.models import Problem
from codejudge.submissions.models import Submission
from codejudge.users.models import User

# No 0/O or 1/I: codes are read aloud and copied from a projector.
CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
CODE_LENGTH = 8


def now() -> datetime:
    return datetime.now(UTC)


def new_join_code() -> str:
    return "".join(secrets.choice(CODE_ALPHABET) for _ in range(CODE_LENGTH))


# ── membership ───────────────────────────────────────────────────────────────────────
async def get_class(session: AsyncSession, class_id: uuid.UUID) -> Classroom:
    c = await session.get(Classroom, class_id)
    if c is None:
        raise NotFoundError("Class not found")
    return c


async def role_in(
    session: AsyncSession, class_id: uuid.UUID, user_id: uuid.UUID | None
) -> str | None:
    if user_id is None:
        return None
    role: str | None = await session.scalar(
        select(ClassMember.role).where(
            ClassMember.class_id == class_id, ClassMember.user_id == user_id
        )
    )
    return role


async def can_manage(session: AsyncSession, c: Classroom, who: Submitter) -> bool:
    return who.role == "admin" or await role_in(session, c.id, who.user_id) == "teacher"


async def require_manager(session: AsyncSession, c: Classroom, who: Submitter) -> None:
    if not await can_manage(session, c, who):
        raise PermissionDeniedError("Only the class's teachers can do that", code="not_teacher")


async def require_member(session: AsyncSession, c: Classroom, who: Submitter) -> str:
    """The person's role in the class (admins count as teachers); 404 for outsiders, so
    a class's existence does not leak to people outside it."""
    if who.role == "admin":
        return "teacher"
    role = await role_in(session, c.id, who.user_id)
    if role is None:
        raise NotFoundError("Class not found")
    return role


# ── classes ──────────────────────────────────────────────────────────────────────────
async def _counts(session: AsyncSession, ids: list[uuid.UUID]) -> dict[uuid.UUID, dict[str, int]]:
    out: dict[uuid.UUID, dict[str, int]] = {
        i: {"student": 0, "teacher": 0, "assignments": 0} for i in ids
    }
    if not ids:
        return out
    rows = await session.execute(
        select(ClassMember.class_id, ClassMember.role, func.count())
        .where(ClassMember.class_id.in_(ids))
        .group_by(ClassMember.class_id, ClassMember.role)
    )
    for cid, role, n in rows.all():
        out[cid][role] = int(n)
    assignments = await session.execute(
        select(Assignment.class_id, func.count())
        .where(Assignment.class_id.in_(ids))
        .group_by(Assignment.class_id)
    )
    for cid, n in assignments.all():
        out[cid]["assignments"] = int(n)
    return out


def _class_out(c: Classroom, role: str | None, counts: dict[str, int], manager: bool) -> ClassOut:
    return ClassOut(
        id=c.id,
        name=c.name,
        description=c.description,
        archived=c.archived,
        join_code=c.join_code if manager else None,
        my_role=role,
        students=counts["student"],
        teachers=counts["teacher"],
        assignments=counts["assignments"],
        created_at=c.created_at,
    )


async def list_classes(
    session: AsyncSession, who: Submitter, *, include_archived: bool = False
) -> list[ClassOut]:
    roles: dict[uuid.UUID, str] = {}
    if who.user_id is not None:
        rows = await session.execute(
            select(ClassMember.class_id, ClassMember.role).where(ClassMember.user_id == who.user_id)
        )
        roles = dict(rows.tuples().all())
    query = select(Classroom).order_by(Classroom.created_at.desc())
    if who.role != "admin":
        query = query.where(Classroom.id.in_(list(roles)))
    if not include_archived:
        query = query.where(Classroom.archived.is_(False))
    classes = list((await session.scalars(query)).all())
    counts = await _counts(session, [c.id for c in classes])
    return [
        _class_out(
            c, roles.get(c.id), counts[c.id], who.role == "admin" or roles.get(c.id) == "teacher"
        )
        for c in classes
    ]


async def class_out(session: AsyncSession, c: Classroom, who: Submitter) -> ClassOut:
    role = await require_member(session, c, who)
    counts = (await _counts(session, [c.id]))[c.id]
    mine = await role_in(session, c.id, who.user_id)
    return _class_out(c, mine, counts, role == "teacher")


async def create_class(session: AsyncSession, data: ClassCreate, actor: Actor) -> Classroom:
    c = Classroom(
        id=uuid.uuid4(),
        name=data.name,
        description=data.description,
        join_code=new_join_code(),
        created_by=actor.id,
    )
    session.add(c)
    await session.flush()
    if actor.id is not None:
        session.add(ClassMember(class_id=c.id, user_id=actor.id, role="teacher"))
    audit(session, actor, "class.created", "class", c.id, name=c.name)
    await session.commit()
    await session.refresh(c)
    return c


async def update_class(
    session: AsyncSession, c: Classroom, data: ClassUpdate, actor: Actor
) -> Classroom:
    changes = {k: v for k, v in data.model_dump(exclude_unset=True).items() if v is not None}
    for field, value in changes.items():
        setattr(c, field, value)
    audit(session, actor, "class.updated", "class", c.id, fields=sorted(changes))
    await session.commit()
    await session.refresh(c)
    return c


async def rotate_code(session: AsyncSession, c: Classroom, actor: Actor) -> Classroom:
    c.join_code = new_join_code()
    audit(session, actor, "class.code_rotated", "class", c.id)
    await session.commit()
    await session.refresh(c)
    return c


async def delete_class(session: AsyncSession, c: Classroom, actor: Actor) -> None:
    audit(session, actor, "class.deleted", "class", c.id, name=c.name)
    await session.delete(c)
    await session.commit()


async def join(session: AsyncSession, code: str, who: Submitter, actor: Actor) -> Classroom:
    if who.user_id is None:
        raise PermissionDeniedError("Sign in to join a class")
    c = await session.scalar(
        select(Classroom).where(
            Classroom.join_code == code.strip().upper(), Classroom.archived.is_(False)
        )
    )
    if c is None:
        raise NotFoundError(
            "No class has that code. Check it with your teacher", code="bad_join_code"
        )
    if await role_in(session, c.id, who.user_id) is None:
        session.add(ClassMember(class_id=c.id, user_id=who.user_id, role="student"))
        audit(session, actor, "class.joined", "class", c.id)
        await session.commit()
    return c


async def members(session: AsyncSession, c: Classroom) -> list[MemberOut]:
    rows = await session.execute(
        select(ClassMember, User)
        .join(User, User.id == ClassMember.user_id)
        .where(ClassMember.class_id == c.id)
        .order_by(ClassMember.role.desc(), User.name)
    )
    return [
        MemberOut(user_id=u.id, name=u.name, email=u.email, role=m.role, joined_at=m.joined_at)
        for m, u in rows.all()
    ]


async def add_member(
    session: AsyncSession, c: Classroom, email: str, role: str, actor: Actor
) -> None:
    user = await session.scalar(select(User).where(func.lower(User.email) == email.strip().lower()))
    if user is None:
        raise NotFoundError(
            "No account has that email; ask them to sign up first", code="unknown_user"
        )
    if role == "teacher" and user.role == "student":
        raise AppError("Only staff accounts can teach a class", code="not_staff")
    existing = await session.get(ClassMember, (c.id, user.id))
    if existing is None:
        session.add(ClassMember(class_id=c.id, user_id=user.id, role=role))
    else:
        existing.role = role
    audit(session, actor, "class.member_added", "class", c.id, user_id=str(user.id), role=role)
    await session.commit()


async def remove_member(
    session: AsyncSession, c: Classroom, user_id: uuid.UUID, actor: Actor
) -> None:
    member = await session.get(ClassMember, (c.id, user_id))
    if member is None:
        raise NotFoundError("Not a member of this class")
    if member.role == "teacher":
        teachers = await session.scalar(
            select(func.count())
            .select_from(ClassMember)
            .where(ClassMember.class_id == c.id, ClassMember.role == "teacher")
        )
        if (teachers or 0) <= 1:
            raise ConflictError("A class needs at least one teacher", code="last_teacher")
    await session.delete(member)
    audit(session, actor, "class.member_removed", "class", c.id, user_id=str(user_id))
    await session.commit()


# ── assignments ──────────────────────────────────────────────────────────────────────
async def get_assignment(session: AsyncSession, assignment_id: uuid.UUID) -> Assignment:
    a = await session.get(Assignment, assignment_id)
    if a is None:
        raise NotFoundError("Assignment not found")
    return a


async def _resolve_problems(
    session: AsyncSession, items: list[AssignmentProblemIn]
) -> list[tuple[Problem, float]]:
    out: list[tuple[Problem, float]] = []
    seen: set[uuid.UUID] = set()
    for item in items:
        p = await problems.get(session, item.problem)
        if p.id in seen:
            raise AppError(f"{p.title!r} is listed twice", code="duplicate_problem")
        if p.current_version_id is None:
            raise AppError(f"{p.title!r} has no tests yet", code="no_tests")
        seen.add(p.id)
        out.append((p, item.points))
    return out


async def _set_problems(
    session: AsyncSession, a: Assignment, items: list[tuple[Problem, float]]
) -> None:
    await session.execute(delete(AssignmentProblem).where(AssignmentProblem.assignment_id == a.id))
    for position, (p, points) in enumerate(items):
        session.add(
            AssignmentProblem(assignment_id=a.id, problem_id=p.id, points=points, position=position)
        )


async def create_assignment(
    session: AsyncSession, c: Classroom, data: AssignmentCreate, actor: Actor
) -> Assignment:
    items = await _resolve_problems(session, data.problems)
    a = Assignment(
        id=uuid.uuid4(),
        class_id=c.id,
        title=data.title,
        description_md=data.description_md,
        opens_at=data.opens_at,
        due_at=data.due_at,
        late_policy=data.late_policy,
        penalty_percent=data.penalty_percent,
    )
    session.add(a)
    await session.flush()
    await _set_problems(session, a, items)
    audit(
        session,
        actor,
        "assignment.created",
        "assignment",
        a.id,
        class_id=str(c.id),
        problems=len(items),
    )
    await session.commit()
    await session.refresh(a)
    return a


async def update_assignment(
    session: AsyncSession, a: Assignment, data: AssignmentUpdate, actor: Actor
) -> Assignment:
    changes = {
        k: v
        for k, v in data.model_dump(exclude_unset=True, exclude={"problems"}).items()
        if v is not None
    }
    opens = changes.get("opens_at", a.opens_at)
    due = changes.get("due_at", a.due_at)
    if due <= opens:
        raise AppError("The due time must be after the opening time", code="bad_window")
    for field, value in changes.items():
        setattr(a, field, value)
    if data.problems is not None:
        await _set_problems(session, a, await _resolve_problems(session, data.problems))
    audit(
        session,
        actor,
        "assignment.updated",
        "assignment",
        a.id,
        fields=sorted([*changes, *(["problems"] if data.problems else [])]),
    )
    await session.commit()
    await session.refresh(a)
    return a


async def delete_assignment(session: AsyncSession, a: Assignment, actor: Actor) -> None:
    audit(session, actor, "assignment.deleted", "assignment", a.id, title=a.title)
    await session.delete(a)
    await session.commit()


async def set_extension(
    session: AsyncSession, a: Assignment, user_id: uuid.UUID, due_at: datetime, actor: Actor
) -> None:
    if await role_in(session, a.class_id, user_id) != "student":
        raise NotFoundError("That student is not in this class")
    ext = await session.get(AssignmentExtension, (a.id, user_id))
    if ext is None:
        session.add(AssignmentExtension(assignment_id=a.id, user_id=user_id, due_at=due_at))
    else:
        ext.due_at = due_at
    audit(
        session,
        actor,
        "assignment.extension",
        "assignment",
        a.id,
        user_id=str(user_id),
        due_at=due_at.isoformat(),
    )
    await session.commit()


async def due_for(session: AsyncSession, a: Assignment, user_id: uuid.UUID | None) -> datetime:
    if user_id is None:
        return a.due_at
    ext = await session.get(AssignmentExtension, (a.id, user_id))
    return ext.due_at if ext else a.due_at


def status_of(a: Assignment, due: datetime, at: datetime) -> str:
    if at < a.opens_at:
        return "upcoming"
    if at <= due:
        return "open"
    return "closed" if a.late_policy == "refuse" else "late"


async def _problem_rows(
    session: AsyncSession, assignment_ids: list[uuid.UUID]
) -> dict[uuid.UUID, list[tuple[AssignmentProblem, Problem]]]:
    out: dict[uuid.UUID, list[tuple[AssignmentProblem, Problem]]] = {i: [] for i in assignment_ids}
    if not assignment_ids:
        return out
    rows = await session.execute(
        select(AssignmentProblem, Problem)
        .join(Problem, Problem.id == AssignmentProblem.problem_id)
        .where(AssignmentProblem.assignment_id.in_(assignment_ids))
        .order_by(AssignmentProblem.position)
    )
    for ap, p in rows.all():
        out[ap.assignment_id].append((ap, p))
    return out


@dataclass
class Mark:
    score: float
    late: bool
    attempts: int
    verdict: str


def effective(a: Assignment, points: float, score: float, max_score: float, late: bool) -> float:
    """A submission's mark on an assignment problem: its score scaled to the problem's
    points, minus the late penalty when the policy has one."""
    if max_score <= 0:
        return 0.0
    value = score / max_score * points
    if late and a.late_policy == "penalty":
        value *= 1 - a.penalty_percent / 100
    return round(value, 4)


async def marks(
    session: AsyncSession,
    a: Assignment,
    points: dict[uuid.UUID, float],
    user_id: uuid.UUID | None = None,
) -> dict[tuple[uuid.UUID, uuid.UUID], Mark]:
    """Best mark per (student, problem) on this assignment, in one query."""
    query = select(
        Submission.user_id,
        Submission.problem_id,
        Submission.score,
        Submission.max_score,
        Submission.late,
        Submission.verdict,
    ).where(
        Submission.context == "assignment",
        Submission.context_id == a.id,
        Submission.status == "done",
        Submission.user_id.is_not(None),
    )
    if user_id is not None:
        query = query.where(Submission.user_id == user_id)
    out: dict[tuple[uuid.UUID, uuid.UUID], Mark] = {}
    for uid, pid, score, max_score, late, verdict in (await session.execute(query)).all():
        if uid is None or pid not in points:
            continue
        value = effective(a, points[pid], score, max_score, late)
        key = (uid, pid)
        current = out.get(key)
        if current is None:
            out[key] = Mark(value, late, 1, verdict)
            continue
        current.attempts += 1
        if value > current.score or (value == current.score and current.late and not late):
            current.score, current.late, current.verdict = value, late, verdict
    return out


def _problem_out(
    ap: AssignmentProblem, p: Problem, mark: Mark | None = None
) -> AssignmentProblemOut:
    return AssignmentProblemOut(
        id=p.id,
        slug=p.slug,
        title=p.title,
        difficulty=p.difficulty,
        points=ap.points,
        my_score=mark.score if mark else None,
        my_verdict=mark.verdict if mark else None,
    )


async def assignments_out(
    session: AsyncSession, items: Iterable[Assignment], who: Submitter, *, as_student: bool
) -> list[AssignmentOut]:
    items = list(items)
    rows = await _problem_rows(session, [a.id for a in items])
    at = now()
    exts: dict[uuid.UUID, datetime] = {}
    if who.user_id is not None and items:
        found = await session.execute(
            select(AssignmentExtension.assignment_id, AssignmentExtension.due_at).where(
                AssignmentExtension.user_id == who.user_id,
                AssignmentExtension.assignment_id.in_([a.id for a in items]),
            )
        )
        exts = dict(found.all())
    out = []
    for a in items:
        probs = rows[a.id]
        due = exts.get(a.id, a.due_at)
        mine: dict[uuid.UUID, Mark] = {}
        if as_student and who.user_id is not None:
            found_marks = await marks(
                session, a, {ap.problem_id: ap.points for ap, _ in probs}, who.user_id
            )
            mine = {pid: m for (_, pid), m in found_marks.items()}
        problem_outs = [_problem_out(ap, p, mine.get(p.id)) for ap, p in probs]
        out.append(
            AssignmentOut(
                id=a.id,
                class_id=a.class_id,
                title=a.title,
                description_md=a.description_md,
                opens_at=a.opens_at,
                due_at=a.due_at,
                my_due_at=due,
                late_policy=a.late_policy,
                penalty_percent=a.penalty_percent,
                status=status_of(a, due, at),
                total_points=sum(ap.points for ap, _ in probs),
                my_total=round(sum(m.score for m in mine.values()), 4) if as_student else None,
                problems=problem_outs,
            )
        )
    return out


async def class_assignments(
    session: AsyncSession, c: Classroom, who: Submitter
) -> list[AssignmentOut]:
    role = await require_member(session, c, who)
    query = select(Assignment).where(Assignment.class_id == c.id).order_by(Assignment.due_at)
    if role != "teacher":
        # Students see an assignment once it opens.
        query = query.where(Assignment.opens_at <= now())
    return await assignments_out(
        session, (await session.scalars(query)).all(), who, as_student=role == "student"
    )


async def my_assignments(session: AsyncSession, who: Submitter) -> list[AssignmentOut]:
    if who.user_id is None:
        return []
    query = (
        select(Assignment)
        .join(ClassMember, ClassMember.class_id == Assignment.class_id)
        .join(Classroom, Classroom.id == Assignment.class_id)
        .where(
            ClassMember.user_id == who.user_id,
            ClassMember.role == "student",
            Classroom.archived.is_(False),
            Assignment.opens_at <= now(),
        )
        .order_by(Assignment.due_at)
    )
    return await assignments_out(
        session, (await session.scalars(query)).all(), who, as_student=True
    )


async def assignment_for(
    session: AsyncSession, a: Assignment, who: Submitter
) -> tuple[AssignmentOut, str]:
    c = await get_class(session, a.class_id)
    role = await require_member(session, c, who)
    if role == "student" and now() < a.opens_at:
        raise NotFoundError("Assignment not found")
    out = await assignments_out(session, [a], who, as_student=role == "student")
    return out[0], role


async def assignment_problem(
    session: AsyncSession, a: Assignment, ref: str, who: Submitter
) -> Problem:
    """A problem of the assignment, for a member (even when it is private or a draft)."""
    await assignment_for(session, a, who)
    p = await problems.get(session, ref)
    linked = await session.get(AssignmentProblem, (a.id, p.id))
    if linked is None:
        raise NotFoundError("Problem not found")
    return p


# ── gradebook ────────────────────────────────────────────────────────────────────────
async def gradebook(session: AsyncSession, a: Assignment) -> Gradebook:
    probs = (await _problem_rows(session, [a.id]))[a.id]
    points = {ap.problem_id: ap.points for ap, _ in probs}
    best = await marks(session, a, points)
    students = (
        await session.execute(
            select(User)
            .join(ClassMember, ClassMember.user_id == User.id)
            .where(ClassMember.class_id == a.class_id, ClassMember.role == "student")
            .order_by(User.name, User.email)
        )
    ).scalars()
    rows = []
    for u in students:
        cells = []
        for _, p in probs:
            m = best.get((u.id, p.id))
            cells.append(
                GradeCell(
                    problem_id=p.id,
                    score=m.score if m else None,
                    late=bool(m and m.late),
                    attempts=m.attempts if m else 0,
                )
            )
        rows.append(
            GradeRow(
                user_id=u.id,
                name=u.name,
                email=u.email,
                total=round(sum(c.score or 0 for c in cells), 4),
                cells=cells,
            )
        )
    return Gradebook(
        assignment_id=a.id,
        title=a.title,
        problems=[_problem_out(ap, p) for ap, p in probs],
        total_points=sum(points.values()),
        rows=rows,
    )


def gradebook_csv(book: Gradebook) -> str:
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(
        [
            "name",
            "email",
            *[f"{p.slug} ({p.points:g})" for p in book.problems],
            f"total ({book.total_points:g})",
        ]
    )
    for row in book.rows:
        writer.writerow(
            [
                _csv_safe(row.name),
                row.email,
                *[
                    "" if c.score is None else f"{c.score:g}{' (late)' if c.late else ''}"
                    for c in row.cells
                ],
                f"{row.total:g}",
            ]
        )
    return buf.getvalue()


def _csv_safe(value: str) -> str:
    """Spreadsheets run cells that start with = + - @ as formulas: neutralise them."""
    return "'" + value if value[:1] in ("=", "+", "-", "@") else value


# ── the submission policy ────────────────────────────────────────────────────────────
class AssignmentPolicy:
    async def admit(
        self, session: AsyncSession, who: Submitter, problem: Problem, context_id: uuid.UUID | None
    ) -> Admission:
        a = await session.get(Assignment, context_id) if context_id else None
        if a is None:
            raise NotFoundError("Assignment not found")
        if await session.get(AssignmentProblem, (a.id, problem.id)) is None:
            raise NotFoundError("Problem not found")
        if who.is_staff and await role_in(session, a.class_id, who.user_id) != "student":
            return Admission()
        c = await session.get(Classroom, a.class_id)
        role = await role_in(session, a.class_id, who.user_id)
        if c is None or role is None:
            raise PermissionDeniedError("You are not in this class", code="not_a_member")
        if role == "teacher":
            return Admission()
        if c.archived:
            raise PermissionDeniedError("This class is archived", code="class_archived")
        at = now()
        if at < a.opens_at:
            raise PermissionDeniedError(
                "This assignment is not open yet", code="assignment_not_open"
            )
        if at > await due_for(session, a, who.user_id):
            if a.late_policy == "refuse":
                raise PermissionDeniedError(
                    "The due time has passed and this assignment does not accept late work",
                    code="assignment_closed",
                )
            return Admission(late=True)
        return Admission()

    async def can_view(self, session: AsyncSession, who: Submitter, submission: Submission) -> bool:
        a = await session.get(Assignment, submission.context_id) if submission.context_id else None
        return a is not None and await role_in(session, a.class_id, who.user_id) == "teacher"


contexts.register("assignment", AssignmentPolicy())
