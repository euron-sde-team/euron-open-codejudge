"""Contests: lifecycle, registration, the submission policy, and the scoreboard.

The scoreboard is computed from the contest's submissions with a fixed number of queries
(problems, participants with names, and one over the submissions), however many people
take part, and cached per view. Every change that can move the board (a verdict, a
rejudge, an edited window or freeze, a new problem) bumps the contest's version key, so a
cached board is never served after the data under it changed; the short TTL only bounds
memory.
"""

from __future__ import annotations

import secrets
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from codejudge.audit.service import Actor, audit
from codejudge.contests import scoring
from codejudge.contests.models import Clarification, Contest, ContestParticipant, ContestProblem
from codejudge.contests.schemas import (
    Announcement,
    CellOut,
    ClarificationIn,
    ClarificationOut,
    ContestCreate,
    ContestOut,
    ContestProblemIn,
    ContestProblemOut,
    ContestSummary,
    ContestUpdate,
    MyStatus,
    Phase,
    RowOut,
    Scoreboard,
)
from codejudge.core import contexts
from codejudge.core.container import Container
from codejudge.core.contexts import Admission, Submitter
from codejudge.core.errors import AppError, ConflictError, NotFoundError, PermissionDeniedError
from codejudge.problems import service as problems
from codejudge.problems.models import Problem
from codejudge.problems.schemas import ProblemOut
from codejudge.submissions.models import Submission
from codejudge.users.models import User

BOARD_TTL_S = 30
LABELS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"


class ContestClosedError(AppError):
    status_code = 403
    code = "contest_not_running"


def now() -> datetime:
    return datetime.now(UTC)


def phase(c: Contest, at: datetime | None = None) -> Phase:
    t = at or now()
    if t < c.starts_at:
        return "upcoming"
    return "running" if t < c.ends_at else "ended"


def frozen_view(c: Contest, who: Submitter, at: datetime | None = None) -> bool:
    """Contestants see the frozen board from the freeze until staff unfreeze it."""
    if who.is_staff or c.freeze_at is None or c.unfrozen:
        return False
    return (at or now()) >= c.freeze_at


# ── loading and access ───────────────────────────────────────────────────────────────
async def get(session: AsyncSession, ref: str | uuid.UUID) -> Contest:
    try:
        cid = ref if isinstance(ref, uuid.UUID) else uuid.UUID(str(ref))
        row = await session.get(Contest, cid)
    except ValueError:
        row = await session.scalar(select(Contest).where(Contest.slug == str(ref)))
    if row is None:
        raise NotFoundError("Contest not found")
    return row


async def is_participant(session: AsyncSession, c: Contest, user_id: uuid.UUID | None) -> bool:
    if user_id is None:
        return False
    found = await session.scalar(
        select(ContestParticipant.id).where(
            ContestParticipant.contest_id == c.id, ContestParticipant.user_id == user_id
        )
    )
    return found is not None


async def visible(session: AsyncSession, who: Submitter, c: Contest) -> Contest:
    """The contest if this person may see it; private ones look missing to outsiders."""
    if who.is_staff or c.visibility == "public" or await is_participant(session, c, who.user_id):
        return c
    raise NotFoundError("Contest not found")


async def _participant_counts(session: AsyncSession, ids: list[uuid.UUID]) -> dict[uuid.UUID, int]:
    if not ids:
        return {}
    rows = await session.execute(
        select(ContestParticipant.contest_id, func.count())
        .where(ContestParticipant.contest_id.in_(ids))
        .group_by(ContestParticipant.contest_id)
    )
    return {cid: int(n) for cid, n in rows.all()}


async def _joined(
    session: AsyncSession, user_id: uuid.UUID | None, ids: list[uuid.UUID]
) -> set[uuid.UUID]:
    if user_id is None or not ids:
        return set()
    rows = await session.scalars(
        select(ContestParticipant.contest_id).where(
            ContestParticipant.user_id == user_id, ContestParticipant.contest_id.in_(ids)
        )
    )
    return set(rows.all())


def _summary(c: Contest, participants: int, registered: bool) -> ContestSummary:
    return ContestSummary(
        id=c.id,
        slug=c.slug,
        title=c.title,
        format=c.format,
        starts_at=c.starts_at,
        ends_at=c.ends_at,
        freeze_at=c.freeze_at,
        visibility=c.visibility,
        registration=c.registration,
        phase=phase(c),
        participants=participants,
        registered=registered,
    )


async def list_contests(session: AsyncSession, who: Submitter) -> list[ContestSummary]:
    query = select(Contest)
    if not who.is_staff:
        mine = select(ContestParticipant.contest_id).where(
            ContestParticipant.user_id == who.user_id
        )
        query = query.where((Contest.visibility == "public") | Contest.id.in_(mine))
    rows = list((await session.scalars(query.order_by(Contest.starts_at.desc()))).all())
    ids = [c.id for c in rows]
    counts = await _participant_counts(session, ids)
    joined = await _joined(session, who.user_id, ids)
    return [_summary(c, counts.get(c.id, 0), c.id in joined) for c in rows]


async def contest_problems(session: AsyncSession, c: Contest) -> list[ContestProblemOut]:
    rows = await session.execute(
        select(ContestProblem, Problem.slug, Problem.title)
        .join(Problem, Problem.id == ContestProblem.problem_id)
        .where(ContestProblem.contest_id == c.id)
        .order_by(ContestProblem.position, ContestProblem.label)
    )
    return [
        ContestProblemOut(
            label=cp.label,
            problem_id=cp.problem_id,
            slug=slug,
            title=title,
            points=cp.points,
            position=cp.position,
        )
        for cp, slug, title in rows.all()
    ]


async def detail(session: AsyncSession, who: Submitter, c: Contest) -> ContestOut:
    await visible(session, who, c)
    counts = await _participant_counts(session, [c.id])
    registered = await is_participant(session, c, who.user_id)
    show_problems = who.is_staff or phase(c) != "upcoming"
    return ContestOut(
        **_summary(c, counts.get(c.id, 0), registered).model_dump(),
        description_md=c.description_md,
        penalty_minutes=c.penalty_minutes,
        unfrozen=c.unfrozen,
        problems=await contest_problems(session, c) if show_problems else [],
        join_code=c.join_code if who.is_staff else None,
    )


# ── staff: lifecycle ─────────────────────────────────────────────────────────────────
async def bump(container: Container, contest_id: uuid.UUID) -> None:
    """Invalidate every cached board of this contest."""
    await container.kv.incr(f"contest:{contest_id}:v")


async def create(session: AsyncSession, data: ContestCreate, actor: Actor) -> Contest:
    if await session.scalar(select(Contest.id).where(Contest.slug == data.slug)):
        raise ConflictError(f"A contest with the slug {data.slug!r} exists", code="slug_taken")
    c = Contest(id=uuid.uuid4(), created_by=actor.id, **data.model_dump())
    if c.registration == "invite":
        c.join_code = _code()
    session.add(c)
    await session.flush()
    audit(session, actor, "contest.created", "contest", c.id, slug=c.slug)
    await session.commit()
    await session.refresh(c)
    return c


def _code() -> str:
    return secrets.token_urlsafe(9)[:12]


async def update(
    container: Container, session: AsyncSession, c: Contest, data: ContestUpdate, actor: Actor
) -> Contest:
    changes = data.model_dump(exclude_unset=True)
    for required in (
        "title",
        "format",
        "starts_at",
        "ends_at",
        "visibility",
        "registration",
        "penalty_minutes",
    ):
        if required in changes and changes[required] is None:
            changes.pop(required)
    merged = {
        "title": c.title,
        "description_md": c.description_md,
        "format": c.format,
        "starts_at": c.starts_at,
        "ends_at": c.ends_at,
        "freeze_at": c.freeze_at,
        "visibility": c.visibility,
        "registration": c.registration,
        "penalty_minutes": c.penalty_minutes,
    } | changes
    ContestCreate.model_validate({"slug": c.slug, **merged})  # the window rules, on the result
    for field, value in changes.items():
        setattr(c, field, value)
    if c.registration == "invite" and not c.join_code:
        c.join_code = _code()
    audit(session, actor, "contest.updated", "contest", c.id, fields=sorted(changes))
    await session.commit()
    await session.refresh(c)
    await bump(container, c.id)
    return c


async def delete(session: AsyncSession, c: Contest, actor: Actor) -> None:
    audit(session, actor, "contest.deleted", "contest", c.id, slug=c.slug)
    await session.delete(c)
    await session.commit()


async def add_problem(
    container: Container, session: AsyncSession, c: Contest, data: ContestProblemIn, actor: Actor
) -> list[ContestProblemOut]:
    p = await problems.get(session, data.problem)
    if p.current_version_id is None:
        raise AppError(f"{p.title!r} has no tests yet", code="no_tests")
    if p.status != "published" and p.visibility != "private":
        raise AppError(
            f"{p.title!r} is a public draft: publish it, or make it private for contests",
            code="problem_not_ready",
        )
    existing = list(
        (
            await session.scalars(select(ContestProblem).where(ContestProblem.contest_id == c.id))
        ).all()
    )
    if any(cp.problem_id == p.id for cp in existing):
        raise ConflictError(f"{p.title!r} is already in this contest", code="duplicate_problem")
    used = {cp.label for cp in existing}
    label = data.label or next((x for x in LABELS if x not in used), None)
    if label is None or label in used:
        raise ConflictError(f"The label {label!r} is taken", code="label_taken")
    session.add(
        ContestProblem(
            id=uuid.uuid4(),
            contest_id=c.id,
            problem_id=p.id,
            label=label,
            position=max((cp.position for cp in existing), default=-1) + 1,
            points=data.points,
        )
    )
    audit(session, actor, "contest.problem_added", "contest", c.id, problem=p.slug, label=label)
    await session.commit()
    await bump(container, c.id)
    return await contest_problems(session, c)


async def remove_problem(
    container: Container, session: AsyncSession, c: Contest, label: str, actor: Actor
) -> None:
    cp = await session.scalar(
        select(ContestProblem).where(
            ContestProblem.contest_id == c.id, ContestProblem.label == label
        )
    )
    if cp is None:
        raise NotFoundError(f"No problem {label} in this contest")
    await session.delete(cp)
    audit(session, actor, "contest.problem_removed", "contest", c.id, label=label)
    await session.commit()
    await bump(container, c.id)


async def reorder(
    container: Container, session: AsyncSession, c: Contest, labels: list[str], actor: Actor
) -> list[ContestProblemOut]:
    """New order by current labels; problems are relabelled A, B, C in that order."""
    rows = {
        cp.label: cp
        for cp in (
            await session.scalars(select(ContestProblem).where(ContestProblem.contest_id == c.id))
        ).all()
    }
    if sorted(labels) != sorted(rows):
        raise AppError("List every problem of the contest exactly once", code="bad_order")
    for i, label in enumerate(labels):
        rows[label].label = f"_{i}"  # free the labels first: (contest, label) is unique
    await session.flush()
    for i, label in enumerate(labels):
        rows[label].label, rows[label].position = LABELS[i], i
    audit(session, actor, "contest.reordered", "contest", c.id, order=labels)
    await session.commit()
    await bump(container, c.id)
    return await contest_problems(session, c)


async def unfreeze(
    container: Container, session: AsyncSession, c: Contest, actor: Actor
) -> Contest:
    if phase(c) != "ended":
        raise AppError(
            "The scoreboard can be unfrozen once the contest has ended", code="not_ended"
        )
    c.unfrozen = True
    audit(session, actor, "contest.unfrozen", "contest", c.id)
    await session.commit()
    await bump(container, c.id)
    return c


# ── registration ─────────────────────────────────────────────────────────────────────
async def _add_participant(
    container: Container, session: AsyncSession, c: Contest, user_id: uuid.UUID
) -> None:
    if phase(c) == "ended":
        raise ContestClosedError("This contest has ended; registration is closed")
    if await is_participant(session, c, user_id):
        return
    session.add(ContestParticipant(id=uuid.uuid4(), contest_id=c.id, user_id=user_id))
    await session.commit()
    await bump(container, c.id)


async def register(container: Container, session: AsyncSession, who: Submitter, c: Contest) -> None:
    await visible(session, who, c)
    if who.user_id is None:
        raise PermissionDeniedError("Sign in to register", code="not_signed_in")
    if c.registration != "open" and not who.is_staff:
        raise PermissionDeniedError(
            "This contest is by invitation: use the join code you were given", code="invite_only"
        )
    await _add_participant(container, session, c, who.user_id)


async def join(container: Container, session: AsyncSession, who: Submitter, code: str) -> Contest:
    c = await session.scalar(select(Contest).where(Contest.join_code == code.strip()))
    if c is None or who.user_id is None:
        raise NotFoundError("No contest has this join code")
    await _add_participant(container, session, c, who.user_id)
    return c


# ── the scoreboard ───────────────────────────────────────────────────────────────────
async def board(session: AsyncSession, c: Contest, *, frozen: bool) -> Scoreboard:
    """Built with three queries whatever the number of participants or submissions."""
    probs = await contest_problems(session, c)
    label_of = {p.problem_id: p.label for p in probs}
    people = dict(
        (
            await session.execute(
                select(ContestParticipant.user_id, User.name)
                .join(User, User.id == ContestParticipant.user_id)
                .where(ContestParticipant.contest_id == c.id)
            )
        ).all()
    )
    subs = await session.execute(
        select(
            Submission.user_id,
            Submission.problem_id,
            Submission.created_at,
            Submission.status,
            Submission.verdict,
            Submission.score,
            Submission.max_score,
        ).where(
            Submission.context == "contest",
            Submission.context_id == c.id,
            Submission.created_at >= c.starts_at,
            Submission.created_at < c.ends_at,
        )
    )
    attempts = [
        scoring.Attempt(
            user_id=u,
            label=label_of[pid],
            created_at=t,
            status=st,
            verdict=v,
            score=sc,
            max_score=mx,
        )
        for u, pid, t, st, v, sc, mx in subs.all()
        if u in people and pid in label_of
    ]
    spec = [scoring.Problem(label=p.label, points=p.points) for p in probs]
    freeze_at = c.freeze_at if frozen else None
    if c.format == "ioi":
        rows = scoring.ioi(attempts, spec, people, start=c.starts_at, freeze_at=freeze_at)
    else:
        rows = scoring.icpc(
            attempts,
            spec,
            people,
            start=c.starts_at,
            penalty_minutes=c.penalty_minutes,
            freeze_at=freeze_at,
        )
    return Scoreboard(
        contest_id=c.id,
        format=c.format,
        phase=phase(c),
        frozen=frozen,
        freeze_at=c.freeze_at,
        problems=probs,
        rows=[_row(r, people.get(r.user_id, "")) for r in rows],
    )


def _row(r: scoring.Row, name: str) -> RowOut:
    return RowOut(
        rank=r.rank,
        user_id=r.user_id,
        name=name,
        solved=r.solved,
        penalty=r.penalty,
        score=r.score,
        cells=[
            CellOut(
                label=x.label,
                solved=x.solved,
                attempts=x.attempts,
                pending=x.pending,
                minute=x.minute,
                score=x.score,
                first=x.first,
            )
            for x in r.cells.values()
        ],
    )


async def scoreboard(
    container: Container, session: AsyncSession, who: Submitter, c: Contest
) -> Scoreboard:
    await visible(session, who, c)
    if phase(c) == "upcoming" and not who.is_staff:
        raise ContestClosedError("The scoreboard opens when the contest starts")
    frozen = frozen_view(c, who)
    version = (await container.kv.get(f"contest:{c.id}:v") or b"0").decode()
    # The phase is part of the key: a board cached while running is not served once ended.
    key = f"contest:{c.id}:board:{'frozen' if frozen else 'live'}:{phase(c)}:{version}"
    cached = await container.kv.get(key)
    if cached is not None:
        return Scoreboard.model_validate_json(cached)
    result = await board(session, c, frozen=frozen)
    await container.kv.set(key, result.model_dump_json().encode(), BOARD_TTL_S)
    return result


async def my_status(
    container: Container, session: AsyncSession, who: Submitter, c: Contest
) -> MyStatus:
    await visible(session, who, c)
    registered = await is_participant(session, c, who.user_id)
    row = None
    if registered and phase(c) != "upcoming":
        live = await board(session, c, frozen=frozen_view(c, who))
        row = next((r for r in live.rows if r.user_id == who.user_id), None)
    return MyStatus(registered=registered, phase=phase(c), row=row)


# ── clarifications ───────────────────────────────────────────────────────────────────
def _clar_out(x: Clarification, who: Submitter, names: dict[uuid.UUID, str]) -> ClarificationOut:
    return ClarificationOut(
        id=x.id,
        problem_label=x.problem_label,
        question=x.question,
        answer=x.answer,
        public=x.public,
        mine=x.asked_by is not None and x.asked_by == who.user_id,
        asked_by_name=names.get(x.asked_by) if (who.is_staff and x.asked_by) else None,
        created_at=x.created_at,
        answered_at=x.answered_at,
    )


async def clarifications(
    session: AsyncSession, who: Submitter, c: Contest
) -> list[ClarificationOut]:
    await visible(session, who, c)
    query = select(Clarification).where(Clarification.contest_id == c.id)
    if not who.is_staff:
        query = query.where(
            Clarification.public.is_(True) | (Clarification.asked_by == who.user_id)
        )
    rows = list((await session.scalars(query.order_by(Clarification.created_at.desc()))).all())
    names: dict[uuid.UUID, str] = {}
    if who.is_staff:
        ids = {x.asked_by for x in rows if x.asked_by}
        if ids:
            names = dict(
                (await session.execute(select(User.id, User.name).where(User.id.in_(ids)))).all()
            )
    return [_clar_out(x, who, names) for x in rows]


async def ask(
    session: AsyncSession, who: Submitter, c: Contest, data: ClarificationIn
) -> ClarificationOut:
    if not who.is_staff and not await is_participant(session, c, who.user_id):
        raise PermissionDeniedError(
            "Register for this contest to ask a question", code="not_registered"
        )
    if not who.is_staff and phase(c) != "running":
        raise ContestClosedError("Questions are open while the contest runs")
    x = Clarification(
        id=uuid.uuid4(),
        contest_id=c.id,
        problem_label=data.problem_label,
        question=data.question,
        asked_by=who.user_id,
    )
    session.add(x)
    await session.commit()
    await session.refresh(x)
    return _clar_out(x, who, {})


async def answer(
    session: AsyncSession,
    who: Submitter,
    c: Contest,
    clar_id: uuid.UUID | None,
    data: Announcement,
    actor: Actor,
) -> ClarificationOut:
    """Answer a question, or with no question post a public announcement."""
    if clar_id is None:
        x = Clarification(id=uuid.uuid4(), contest_id=c.id, question="Announcement", public=True)
        session.add(x)
    else:
        found = await session.get(Clarification, clar_id)
        if found is None or found.contest_id != c.id:
            raise NotFoundError("Question not found")
        x = found
        x.public = data.public
    x.answer, x.answered_by, x.answered_at = data.answer, actor.id, now()
    audit(session, actor, "contest.clarification_answered", "contest", c.id, public=x.public)
    await session.commit()
    await session.refresh(x)
    return _clar_out(x, who, {})


# ── problems inside a contest ────────────────────────────────────────────────────────
async def problem(session: AsyncSession, who: Submitter, c: Contest, label: str) -> ProblemOut:
    """A contest problem for its participants, even when the problem itself is private.
    Uses the same view as the practice page, so hidden tests are never in it."""
    await visible(session, who, c)
    if not who.is_staff:
        if phase(c) == "upcoming":
            raise ContestClosedError("The problems open when the contest starts")
        if phase(c) == "running" and not await is_participant(session, c, who.user_id):
            raise PermissionDeniedError(
                "Register for this contest to see its problems", code="not_registered"
            )
    cp = await session.scalar(
        select(ContestProblem).where(
            ContestProblem.contest_id == c.id, ContestProblem.label == label
        )
    )
    if cp is None:
        raise NotFoundError(f"No problem {label} in this contest")
    p = await problems.get(session, cp.problem_id)
    return await problems.detail(session, p, who, check_access=False)


# ── the submission policy and the judged listener ────────────────────────────────────
class ContestPolicy:
    async def admit(
        self, session: AsyncSession, who: Submitter, problem: Problem, context_id: uuid.UUID | None
    ) -> Admission:
        if context_id is None:
            raise AppError("Say which contest this submission is for", code="contest_required")
        if who.candidate_id is not None:
            raise PermissionDeniedError(
                "Interview candidates cannot enter contests", code="not_registered"
            )
        c = await get(session, context_id)
        in_contest = await session.scalar(
            select(ContestProblem.id).where(
                ContestProblem.contest_id == c.id, ContestProblem.problem_id == problem.id
            )
        )
        if in_contest is None:
            raise NotFoundError("This problem is not part of the contest")
        details = c.format != "icpc"
        if who.is_staff:
            return Admission(show_test_details=True)
        if not await is_participant(session, c, who.user_id):
            raise PermissionDeniedError(
                "Register for this contest before submitting", code="not_registered"
            )
        current = phase(c)
        if current == "upcoming":
            raise ContestClosedError("This contest has not started yet")
        if current == "ended":
            raise ContestClosedError(
                "This contest has ended; practise the problems from the problem list"
            )
        return Admission(show_test_details=details)

    async def can_view(self, session: AsyncSession, who: Submitter, submission: Submission) -> bool:
        # Authors and staff are handled by the submissions domain. Nobody else reads a
        # contestant's code: not during the contest, and not after it either.
        return False


contexts.register("contest", ContestPolicy())


@contexts.on_judged
async def _invalidate(container: Container, session: AsyncSession, s: Submission) -> None:
    if s.context == "contest" and s.context_id is not None:
        await bump(container, s.context_id)


def contest_submissions_query(c: Contest) -> Any:
    return (
        select(Submission, User.name)
        .outerjoin(User, User.id == Submission.user_id)
        .where(Submission.context == "contest", Submission.context_id == c.id)
        .order_by(Submission.created_at.desc())
    )
