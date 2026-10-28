"""Interview assessments: invitations, the candidate's timed session, and the report.

A candidate has no account. Their invitation email carries a random token; the database
keeps only its HMAC. Exchanging the token (``POST /candidate/session``) starts the timer on
first use: the deadline is the start plus the assessment's duration, capped by the
assessment's closing time. Afterwards the browser sends the same token in the
``X-CodeJudge-Candidate`` header; ``resolve_candidate`` turns it into a ``Submitter`` that
can see and submit to that one assessment until the deadline, and nothing else.

Paste and tab-away events are recorded and shown to the interviewer as signals with a note
that they are not proof: a candidate may paste from their own notes or switch tabs to read
the documentation, and a determined one can hide both.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import secrets
import uuid
from datetime import UTC, datetime, timedelta

from fastapi import Request
from sqlalchemy import and_, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from codejudge.assessments.models import (
    Assessment,
    AssessmentProblem,
    CandidateEvent,
    Invitation,
)
from codejudge.assessments.schemas import (
    AssessmentCreate,
    AssessmentOut,
    AssessmentProblemIn,
    AssessmentProblemOut,
    AssessmentUpdate,
    CandidatePreview,
    CandidateProblem,
    CandidateView,
    InvitationCounts,
    InvitationOut,
    InviteIn,
    InviteResult,
    Report,
    ReportEvent,
    ReportProblem,
    ReportSubmission,
)
from codejudge.audit.service import Actor, audit
from codejudge.auth.dependencies import register_candidate_resolver
from codejudge.core import contexts, mail
from codejudge.core.config import Settings
from codejudge.core.container import Container
from codejudge.core.contexts import Admission, Submitter
from codejudge.core.errors import (
    AppError,
    AuthenticationError,
    NotFoundError,
    PermissionDeniedError,
    RateLimitedError,
)
from codejudge.core.tasks import periodic
from codejudge.problems import service as problems
from codejudge.problems.models import Problem
from codejudge.submissions.models import Submission

log = logging.getLogger(__name__)

MAX_EVENTS = 500
EVENTS_PER_MINUTE = 60
SIGNALS_NOTE = (
    "Paste and tab-away events are signals reported by the candidate's browser, not proof: "
    "pasting from one's own notes or reading documentation in another tab is common and "
    "fair, and a determined person can hide both. Read the code and the timeline together."
)


def now() -> datetime:
    return datetime.now(UTC)


def new_token() -> str:
    return secrets.token_urlsafe(32)


def token_hash(settings: Settings, token: str) -> str:
    return hmac.new(
        settings.invite_token_pepper.encode(), token.encode(), hashlib.sha256
    ).hexdigest()


def link(settings: Settings, token: str) -> str:
    return f"{settings.public_url.rstrip('/')}/take/{token}"


# ── assessments ──────────────────────────────────────────────────────────────────────
async def get(session: AsyncSession, assessment_id: uuid.UUID) -> Assessment:
    a = await session.get(Assessment, assessment_id)
    if a is None:
        raise NotFoundError("Assessment not found")
    return a


async def _problem_rows(
    session: AsyncSession, assessment_id: uuid.UUID
) -> list[tuple[AssessmentProblem, Problem]]:
    rows = await session.execute(
        select(AssessmentProblem, Problem)
        .join(Problem, Problem.id == AssessmentProblem.problem_id)
        .where(AssessmentProblem.assessment_id == assessment_id)
        .order_by(AssessmentProblem.position)
    )
    return [(ap, p) for ap, p in rows.all()]


async def _set_problems(
    session: AsyncSession, a: Assessment, items: list[AssessmentProblemIn]
) -> None:
    seen: set[uuid.UUID] = set()
    resolved: list[tuple[Problem, float]] = []
    for item in items:
        p = await problems.get(session, item.problem)
        if p.id in seen:
            raise AppError(f"{p.title!r} is listed twice", code="duplicate_problem")
        if p.current_version_id is None:
            raise AppError(f"{p.title!r} has no tests yet", code="no_tests")
        seen.add(p.id)
        resolved.append((p, item.points))
    old = (
        await session.scalars(
            select(AssessmentProblem).where(AssessmentProblem.assessment_id == a.id)
        )
    ).all()
    for row in old:
        await session.delete(row)
    await session.flush()
    for position, (p, points) in enumerate(resolved):
        session.add(
            AssessmentProblem(assessment_id=a.id, problem_id=p.id, points=points, position=position)
        )


async def _counts(session: AsyncSession, ids: list[uuid.UUID]) -> dict[uuid.UUID, InvitationCounts]:
    out = {i: InvitationCounts() for i in ids}
    if ids:
        rows = await session.execute(
            select(Invitation.assessment_id, Invitation.status, func.count())
            .where(Invitation.assessment_id.in_(ids))
            .group_by(Invitation.assessment_id, Invitation.status)
        )
        for aid, status, n in rows.all():
            setattr(out[aid], status, int(n))
    return out


async def out(
    session: AsyncSession, a: Assessment, counts: InvitationCounts | None = None
) -> AssessmentOut:
    rows = await _problem_rows(session, a.id)
    return AssessmentOut(
        id=a.id,
        title=a.title,
        instructions_md=a.instructions_md,
        duration_minutes=a.duration_minutes,
        opens_at=a.opens_at,
        closes_at=a.closes_at,
        total_points=sum(ap.points for ap, _ in rows),
        problems=[
            AssessmentProblemOut(
                id=p.id, slug=p.slug, title=p.title, difficulty=p.difficulty, points=ap.points
            )
            for ap, p in rows
        ],
        invitations=counts or (await _counts(session, [a.id]))[a.id],
        created_at=a.created_at,
    )


async def list_all(session: AsyncSession) -> list[AssessmentOut]:
    items = list(
        (await session.scalars(select(Assessment).order_by(Assessment.created_at.desc()))).all()
    )
    counts = await _counts(session, [a.id for a in items])
    return [await out(session, a, counts[a.id]) for a in items]


async def create(session: AsyncSession, data: AssessmentCreate, actor: Actor) -> Assessment:
    a = Assessment(
        id=uuid.uuid4(),
        title=data.title,
        instructions_md=data.instructions_md,
        duration_minutes=data.duration_minutes,
        opens_at=data.opens_at,
        closes_at=data.closes_at,
        created_by=actor.id,
    )
    session.add(a)
    await session.flush()
    await _set_problems(session, a, data.problems)
    audit(session, actor, "assessment.created", "assessment", a.id, title=a.title)
    await session.commit()
    await session.refresh(a)
    return a


async def update_assessment(
    session: AsyncSession, a: Assessment, data: AssessmentUpdate, actor: Actor
) -> Assessment:
    changes = data.model_dump(exclude_unset=True, exclude={"problems"})
    for required in ("title", "instructions_md", "duration_minutes"):
        if changes.get(required, "") is None:
            changes.pop(required)
    opens, closes = changes.get("opens_at", a.opens_at), changes.get("closes_at", a.closes_at)
    if opens and closes and closes <= opens:
        raise AppError("The closing time must be after the opening time", code="bad_window")
    for field, value in changes.items():
        setattr(a, field, value)
    if data.problems is not None:
        await _set_problems(session, a, data.problems)
    audit(session, actor, "assessment.updated", "assessment", a.id, fields=sorted(changes))
    await session.commit()
    await session.refresh(a)
    return a


async def delete(session: AsyncSession, a: Assessment, actor: Actor) -> None:
    audit(session, actor, "assessment.deleted", "assessment", a.id, title=a.title)
    await session.delete(a)
    await session.commit()


# ── invitations ──────────────────────────────────────────────────────────────────────
async def _scores(
    session: AsyncSession, a: Assessment, invitation_ids: list[uuid.UUID]
) -> dict[uuid.UUID, dict[uuid.UUID, tuple[float, str, int]]]:
    """Per invitation, per problem: (best earned points, its verdict, attempts). One query."""
    points = {ap.problem_id: ap.points for ap, _ in await _problem_rows(session, a.id)}
    out: dict[uuid.UUID, dict[uuid.UUID, tuple[float, str, int]]] = {i: {} for i in invitation_ids}
    if not invitation_ids:
        return out
    rows = await session.execute(
        select(
            Submission.candidate_id,
            Submission.problem_id,
            Submission.score,
            Submission.max_score,
            Submission.verdict,
        ).where(
            Submission.context == "assessment",
            Submission.candidate_id.in_(invitation_ids),
            Submission.status == "done",
        )
    )
    for cid, pid, score, max_score, verdict in rows.all():
        if pid not in points or cid not in out:
            continue
        earned = round(score / max_score * points[pid], 4) if max_score else 0.0
        best = out[cid].get(pid)
        if best is None:
            out[cid][pid] = (earned, verdict, 1)
        else:
            out[cid][pid] = (
                (earned, verdict, best[2] + 1)
                if earned > best[0]
                else (best[0], best[1], best[2] + 1)
            )
    return out


def _invitation_out(inv: Invitation, score: float | None = None, signals: int = 0) -> InvitationOut:
    return InvitationOut(
        id=inv.id,
        assessment_id=inv.assessment_id,
        email=inv.email,
        name=inv.name,
        status=inv.status,
        sent_at=inv.sent_at,
        started_at=inv.started_at,
        deadline_at=inv.deadline_at,
        submitted_at=inv.submitted_at,
        score=score,
        signals=signals,
        created_at=inv.created_at,
    )


async def invitations(session: AsyncSession, a: Assessment) -> list[InvitationOut]:
    rows = list(
        (
            await session.scalars(
                select(Invitation)
                .where(Invitation.assessment_id == a.id)
                .order_by(Invitation.created_at.desc())
            )
        ).all()
    )
    scores = await _scores(session, a, [i.id for i in rows])
    signals = (
        dict(
            (
                await session.execute(
                    select(CandidateEvent.invitation_id, func.count())
                    .where(
                        CandidateEvent.invitation_id.in_([i.id for i in rows]),
                        CandidateEvent.kind.in_(("paste", "tab_hidden")),
                    )
                    .group_by(CandidateEvent.invitation_id)
                )
            ).all()
        )
        if rows
        else {}
    )
    return [
        _invitation_out(
            i,
            round(sum(v[0] for v in scores[i.id].values()), 4) if i.status != "invited" else None,
            int(signals.get(i.id, 0)),
        )
        for i in rows
    ]


async def _send(container: Container, a: Assessment, inv: Invitation, token: str) -> bool:
    settings = container.settings
    url = link(settings, token)
    greeting = f"Hello {inv.name}," if inv.name else "Hello,"
    window = f"\nThe link works until {a.closes_at:%Y-%m-%d %H:%M} UTC." if a.closes_at else ""
    text = (
        f'{greeting}\n\nYou are invited to the coding assessment "{a.title}".\n'
        f"It has {a.duration_minutes} minutes; the timer starts when you open the link.{window}\n\n"
        f"Open it here (it is personal, do not share it):\n{url}\n"
    )
    html = (
        f"<p>{_esc(greeting)}</p><p>You are invited to the coding assessment "
        f"<strong>{_esc(a.title)}</strong>. It has {a.duration_minutes} minutes; the timer "
        f"starts when you open the link.{_esc(window)}</p>"
        f'<p><a href="{_esc(url)}">Start the assessment</a></p>'
        "<p>The link is personal: please do not share it.</p>"
    )
    try:
        await mail.send(settings, inv.email, f"Coding assessment: {a.title}", text, html)
    except mail.MailError:
        return False
    return True


def _esc(text: str) -> str:
    return (
        text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")
    )


async def invite(
    container: Container, session: AsyncSession, a: Assessment, people: list[InviteIn], actor: Actor
) -> InviteResult:
    created: list[tuple[Invitation, str]] = []
    for person in people:
        token = new_token()
        inv = Invitation(
            id=uuid.uuid4(),
            assessment_id=a.id,
            email=person.email,
            name=person.name,
            token_hash=token_hash(container.settings, token),
            invited_by=actor.id,
        )
        session.add(inv)
        created.append((inv, token))
    audit(session, actor, "assessment.invited", "assessment", a.id, count=len(created))
    await session.commit()
    failed: list[str] = []
    for inv, token in created:
        if await _send(container, a, inv, token):
            inv.sent_at = now()
        else:
            failed.append(inv.email)
    await session.commit()
    for inv, _ in created:
        await session.refresh(inv)
    return InviteResult(invitations=[_invitation_out(inv) for inv, _ in created], failed=failed)


async def get_invitation(
    session: AsyncSession, a: Assessment, invitation_id: uuid.UUID
) -> Invitation:
    inv = await session.get(Invitation, invitation_id)
    if inv is None or inv.assessment_id != a.id:
        raise NotFoundError("Invitation not found")
    return inv


async def resend(
    container: Container, session: AsyncSession, a: Assessment, inv: Invitation, actor: Actor
) -> InvitationOut:
    """A new link (the old one stops working: only its hash was kept)."""
    if inv.status not in ("invited", "started"):
        raise AppError(
            f"This invitation is {inv.status}; it cannot be resent", code="not_resendable"
        )
    token = new_token()
    inv.token_hash = token_hash(container.settings, token)
    audit(session, actor, "assessment.resent", "invitation", inv.id)
    await session.commit()
    if not await _send(container, a, inv, token):
        raise AppError("The mail server refused the message; try again later", code="mail_failed")
    inv.sent_at = now()
    await session.commit()
    await session.refresh(inv)
    return _invitation_out(inv)


async def revoke(session: AsyncSession, inv: Invitation, actor: Actor) -> InvitationOut:
    if inv.status in ("submitted", "revoked"):
        raise AppError(f"This invitation is already {inv.status}", code="not_revocable")
    inv.status = "revoked"
    audit(session, actor, "assessment.revoked", "invitation", inv.id)
    await session.commit()
    await session.refresh(inv)
    return _invitation_out(inv)


# ── the candidate ────────────────────────────────────────────────────────────────────
async def _by_token(session: AsyncSession, settings: Settings, token: str) -> Invitation:
    inv = await session.scalar(
        select(Invitation).where(Invitation.token_hash == token_hash(settings, token))
    )
    if inv is None:
        raise AuthenticationError(
            "This link is not valid. Use the latest link from your email", code="bad_link"
        )
    return inv


async def _expire_if_over(session: AsyncSession, inv: Invitation) -> None:
    if inv.status == "started" and inv.deadline_at is not None and inv.deadline_at <= now():
        inv.status = "expired"
        await session.commit()


def _refuse_unusable(inv: Invitation) -> None:
    messages = {
        "revoked": (
            "This invitation was withdrawn. Contact the person who invited you",
            "link_revoked",
        ),
        "submitted": (
            "You have already finished this assessment. Thank you",
            "assessment_submitted",
        ),
        "expired": ("The time for this assessment is over", "assessment_over"),
    }
    if inv.status in messages:
        message, code = messages[inv.status]
        raise AuthenticationError(message, code=code)


async def preview(container: Container, session: AsyncSession, token: str) -> CandidatePreview:
    """What the candidate needs before deciding to start: the title, the duration, the
    instructions and the window. Starts nothing: the clock runs only from ``open_session``."""
    inv = await _by_token(session, container.settings, token)
    await _expire_if_over(session, inv)
    a = await get(session, inv.assessment_id)
    rows = await _problem_rows(session, a.id)
    return CandidatePreview(
        name=inv.name,
        title=a.title,
        instructions_md=a.instructions_md,
        duration_minutes=a.duration_minutes,
        opens_at=a.opens_at,
        closes_at=a.closes_at,
        status=inv.status,
        problems=len(rows),
        total_points=sum(ap.points for ap, _ in rows),
    )


async def open_session(container: Container, session: AsyncSession, token: str) -> Invitation:
    """Exchange the link for a candidate session, starting the timer on first use."""
    inv = await _by_token(session, container.settings, token)
    await _expire_if_over(session, inv)
    _refuse_unusable(inv)
    a = await get(session, inv.assessment_id)
    at = now()
    if inv.status == "invited":
        if a.opens_at and at < a.opens_at:
            raise PermissionDeniedError(
                f"This assessment opens at {a.opens_at:%Y-%m-%d %H:%M} UTC", code="not_open_yet"
            )
        if a.closes_at and at >= a.closes_at:
            inv.status = "expired"
            await session.commit()
            raise AuthenticationError("This assessment has closed", code="assessment_over")
        deadline = at + timedelta(minutes=a.duration_minutes)
        if a.closes_at and a.closes_at < deadline:
            deadline = a.closes_at
        inv.status, inv.started_at, inv.deadline_at = "started", at, deadline
        session.add(CandidateEvent(invitation_id=inv.id, kind="started", detail={}))
        inv.events_count += 1
        await session.commit()
        await session.refresh(inv)
    return inv


async def resolve_candidate(request: Request, session: AsyncSession, token: str) -> Submitter:
    """The ``X-CodeJudge-Candidate`` header: a started, unfinished invitation only."""
    container: Container = request.app.state.container
    inv = await _by_token(session, container.settings, token)
    await _expire_if_over(session, inv)
    _refuse_unusable(inv)
    if inv.status != "started":
        raise AuthenticationError("Open your invitation link to start", code="not_started")
    request.state.candidate = inv.id
    return Submitter(user_id=None, candidate_id=inv.id, role="candidate")


register_candidate_resolver(resolve_candidate)


def require_candidate(who: Submitter) -> uuid.UUID:
    if who.role != "candidate" or who.candidate_id is None:
        raise PermissionDeniedError("Only the invited candidate can do this", code="candidate_only")
    return who.candidate_id


async def candidate_view(session: AsyncSession, inv: Invitation, who: Submitter) -> CandidateView:
    a = await get(session, inv.assessment_id)
    rows = await _problem_rows(session, a.id)
    scores = (await _scores(session, a, [inv.id]))[inv.id]
    at = now()
    items = []
    for ap, p in rows:
        best = scores.get(p.id)
        items.append(
            CandidateProblem(
                points=ap.points,
                best_score=best[0] if best else None,
                best_verdict=best[1] if best else None,
                problem=await problems.detail(session, p, who, check_access=False),
            )
        )
    left = (
        int((inv.deadline_at - at).total_seconds()) if inv.deadline_at else a.duration_minutes * 60
    )
    return CandidateView(
        invitation_id=inv.id,
        name=inv.name,
        title=a.title,
        instructions_md=a.instructions_md,
        status=inv.status,
        started_at=inv.started_at,
        deadline_at=inv.deadline_at,
        now=at,
        seconds_left=max(0, left),
        total_points=sum(ap.points for ap, _ in rows),
        problems=items,
    )


async def record_event(
    container: Container,
    session: AsyncSession,
    inv: Invitation,
    kind: str,
    detail: dict[str, object],
) -> None:
    decision = await container.kv.hit(f"candidate-events:{inv.id}", EVENTS_PER_MINUTE)
    if not decision.allowed:
        raise RateLimitedError(
            "Too many events",
            code="rate_limited",
            headers={"retry-after": str(decision.retry_after_s)},
        )
    # Bounded: the cap keeps a misbehaving page from filling the table.
    claimed = await session.execute(
        update(Invitation)
        .where(Invitation.id == inv.id, Invitation.events_count < MAX_EVENTS)
        .values(events_count=Invitation.events_count + 1)
    )
    if claimed.rowcount:  # type: ignore[attr-defined]
        small = {str(k)[:40]: str(v)[:200] for k, v in list(detail.items())[:8]}
        session.add(CandidateEvent(invitation_id=inv.id, kind=kind, detail=small))
    await session.commit()


async def finish(session: AsyncSession, inv: Invitation) -> Invitation:
    if inv.status != "started":
        raise AppError("This assessment is not in progress", code="not_in_progress")
    inv.status, inv.submitted_at = "submitted", now()
    session.add(CandidateEvent(invitation_id=inv.id, kind="submitted", detail={}))
    inv.events_count += 1
    await session.commit()
    await session.refresh(inv)
    return inv


# ── the report ───────────────────────────────────────────────────────────────────────
async def report(session: AsyncSession, a: Assessment, inv: Invitation) -> Report:
    rows = await _problem_rows(session, a.id)
    scores = (await _scores(session, a, [inv.id]))[inv.id]
    by_id = {p.id: p for _, p in rows}
    subs = list(
        (
            await session.scalars(
                select(Submission)
                .where(Submission.candidate_id == inv.id, Submission.context == "assessment")
                .order_by(Submission.created_at)
            )
        ).all()
    )
    events = list(
        (
            await session.scalars(
                select(CandidateEvent)
                .where(CandidateEvent.invitation_id == inv.id)
                .order_by(CandidateEvent.at, CandidateEvent.id)
            )
        ).all()
    )
    total = round(sum(v[0] for v in scores.values()), 4)
    used = None
    if inv.started_at:
        end = inv.submitted_at or (inv.deadline_at if inv.status == "expired" else None) or now()
        used = round((end - inv.started_at).total_seconds() / 60, 1)
    signals = sum(1 for e in events if e.kind in ("paste", "tab_hidden"))
    return Report(
        invitation=_invitation_out(inv, total, signals),
        assessment_title=a.title,
        duration_minutes=a.duration_minutes,
        total_points=sum(ap.points for ap, _ in rows),
        total=total,
        minutes_used=used,
        problems=[
            ReportProblem(
                id=p.id,
                slug=p.slug,
                title=p.title,
                points=ap.points,
                earned=scores[p.id][0] if p.id in scores else 0.0,
                best_verdict=scores[p.id][1] if p.id in scores else None,
                attempts=scores[p.id][2] if p.id in scores else 0,
            )
            for ap, p in rows
        ],
        submissions=[
            ReportSubmission(
                id=s.id,
                problem_id=s.problem_id,
                problem_slug=by_id[s.problem_id].slug if s.problem_id in by_id else "",
                language=s.language,
                verdict=s.verdict,
                score=s.score,
                max_score=s.max_score,
                time_ms=s.time_ms,
                memory_kb=s.memory_kb,
                source=s.source,
                created_at=s.created_at,
            )
            for s in subs
            if s.context == "assessment"
        ],
        events=[ReportEvent(kind=e.kind, at=e.at, detail=e.detail) for e in events],
        signals_note=SIGNALS_NOTE,
    )


# ── the submission policy ────────────────────────────────────────────────────────────
class AssessmentPolicy:
    async def admit(
        self, session: AsyncSession, who: Submitter, problem: Problem, context_id: uuid.UUID | None
    ) -> Admission:
        if context_id is None:
            raise NotFoundError("Assessment not found")
        if who.role == "candidate":
            if who.candidate_id != context_id:
                raise NotFoundError("Assessment not found")
            inv = await session.get(Invitation, context_id)
            if inv is None:
                raise NotFoundError("Assessment not found")
            await _expire_if_over(session, inv)
            if inv.status != "started" or inv.deadline_at is None or inv.deadline_at <= now():
                raise PermissionDeniedError(
                    "The time for this assessment is over", code="assessment_over"
                )
            assessment_id = inv.assessment_id
        elif who.is_staff:
            # Staff preview: the context names an invitation or the assessment itself.
            inv = await session.get(Invitation, context_id)
            assessment_id = inv.assessment_id if inv else context_id
            if await session.get(Assessment, assessment_id) is None:
                raise NotFoundError("Assessment not found")
        else:
            raise NotFoundError("Assessment not found")
        if await session.get(AssessmentProblem, (assessment_id, problem.id)) is None:
            raise NotFoundError("Problem not found")
        return Admission(show_test_details=False)

    async def can_view(self, session: AsyncSession, who: Submitter, submission: Submission) -> bool:
        # Only the candidate (author) and staff, who are both handled before this.
        return False


contexts.register("assessment", AssessmentPolicy())


# ── housekeeping ─────────────────────────────────────────────────────────────────────
@periodic("assessments.expire")
async def expire(container: Container) -> int:
    """Close invitations whose time ran out (or whose assessment closed unopened)."""
    at = now()
    async with container.db.sessionmaker() as session:
        started = await session.execute(
            update(Invitation)
            .where(Invitation.status == "started", Invitation.deadline_at <= at)
            .values(status="expired")
        )
        closed_ids = select(Assessment.id).where(
            Assessment.closes_at.is_not(None), Assessment.closes_at <= at
        )
        unopened = await session.execute(
            update(Invitation)
            .where(and_(Invitation.status == "invited", Invitation.assessment_id.in_(closed_ids)))
            .values(status="expired")
        )
        await session.commit()
        return int(started.rowcount or 0) + int(unopened.rowcount or 0)  # type: ignore[attr-defined]
