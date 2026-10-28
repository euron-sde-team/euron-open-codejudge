"""Submissions: accept, dispatch to the judge, ingest verdicts, rejudge.

Ingestion is idempotent. A submission points at the job currently responsible for it; a
result is applied only when it belongs to that job and the submission is not already
final for it (row locked ``FOR UPDATE``), so a worker retrying its POST, a redelivered job
judged twice, or a stale result from before a rejudge never changes a verdict twice.
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from codejudge.audit.service import Actor, audit
from codejudge.core import contexts
from codejudge.core.container import Container
from codejudge.core.contexts import Admission, Submitter
from codejudge.core.contract import (
    CheckerSpec,
    GroupSpec,
    Heartbeat,
    JudgeJob,
    JudgeResult,
    Limits,
    TestSpec,
    Verdict,
)
from codejudge.core.errors import AppError, NotFoundError
from codejudge.judge import languages as language_registry
from codejudge.problems.models import Problem, ProblemVersion, ReferenceSolution
from codejudge.problems.service import can_practice
from codejudge.submissions.models import Submission
from codejudge.submissions.schemas import SubmissionOut, TestOut

COUNTED = ("practice", "contest", "assignment", "assessment")


def new_job_id() -> str:
    return uuid.uuid4().hex


# ── accepting ────────────────────────────────────────────────────────────────────────
async def _current_version(session: AsyncSession, p: Problem) -> ProblemVersion:
    v = await session.get(ProblemVersion, p.current_version_id) if p.current_version_id else None
    if v is None:
        raise AppError("This problem has no tests yet", code="no_tests")
    return v


def _check_language(language: str) -> None:
    if language not in language_registry.registry():
        known = ", ".join(language_registry.registry())
        raise AppError(
            f"Unknown language {language!r}. Choose one of: {known}", code="unknown_language"
        )


async def admit(
    session: AsyncSession, who: Submitter, p: Problem, context: str, context_id: uuid.UUID | None
) -> Admission:
    if context == "practice":
        if not can_practice(p, who):
            raise NotFoundError("Problem not found")
        return Admission()
    if context == "reference":
        # A setter's own solution, judged to check the tests before publishing.
        if not who.is_staff:
            raise NotFoundError("Problem not found")
        return Admission()
    policy = contexts.policy(context)
    if policy is None:
        raise AppError(f"Unknown submission context {context!r}", code="unknown_context")
    return await policy.admit(session, who, p, context_id)


def build_job(s: Submission, p: Problem, v: ProblemVersion) -> JudgeJob:
    return JudgeJob(
        job_id=s.job_id,
        submission_id=str(s.id),
        language=s.language,
        source=s.source,
        package_sha256=v.package_sha256,
        limits=Limits(
            time_ms=p.time_limit_ms, memory_mb=p.memory_limit_mb, output_mb=p.output_limit_mb
        ),
        checker=CheckerSpec.model_validate(v.checker or {}),
        groups=[GroupSpec.model_validate(g) for g in v.groups],
        tests=[TestSpec(name=t["name"], group=t["group"], sample=t["sample"]) for t in v.tests],
        only_tests=list(s.only_tests or []),
        custom_input=s.run_input if s.context == "run" and s.only_tests is None else None,
    )


async def _rate_limit(container: Container, who: Submitter) -> None:
    key = f"submit:{who.user_id or who.candidate_id}"
    decision = await container.kv.hit(key, container.settings.submit_rpm)
    if not decision.allowed:
        raise AppError(
            "You are submitting too fast. Wait a few seconds and try again",
            code="rate_limited",
            headers={"retry-after": str(max(1, int(decision.retry_after_s)))},
        )


async def submit(
    container: Container,
    session: AsyncSession,
    who: Submitter,
    p: Problem,
    *,
    language: str,
    source: str,
    context: str = "practice",
    context_id: uuid.UUID | None = None,
) -> Submission:
    _check_language(language)
    if len(source.encode()) > container.settings.max_source_bytes:
        raise AppError("The source is longer than the limit", code="source_too_large")
    if not source.strip():
        raise AppError("The source is empty", code="empty_source")
    admission = await admit(session, who, p, context, context_id)
    if context != "reference":
        await _rate_limit(container, who)
    v = await _current_version(session, p)
    s = Submission(
        id=uuid.uuid4(),
        user_id=who.user_id,
        candidate_id=who.candidate_id,
        problem_id=p.id,
        version_id=v.id,
        language=language,
        source=source,
        context=context,
        context_id=context_id,
        late=admission.late,
        hide_test_details=not admission.show_test_details,
        job_id=new_job_id(),
        max_score=v.max_score,
    )
    session.add(s)
    if context in COUNTED:
        await session.execute(
            update(Problem)
            .where(Problem.id == p.id)
            .values(submissions_count=Problem.submissions_count + 1)
        )
    await session.commit()
    await container.queue.enqueue(build_job(s, p, v))
    return s


async def run(
    container: Container,
    session: AsyncSession,
    who: Submitter,
    p: Problem,
    *,
    language: str,
    source: str,
    custom_input: str | None,
    context: str = "practice",
    context_id: uuid.UUID | None = None,
) -> Submission:
    """Run on the samples (custom_input None) or on the person's own input: judged like a
    submission, never counted, shown only to its author."""
    _check_language(language)
    if len(source.encode()) > container.settings.max_source_bytes:
        raise AppError("The source is longer than the limit", code="source_too_large")
    await admit(session, who, p, context, context_id)
    await _rate_limit(container, who)
    v = await _current_version(session, p)
    samples = [t["name"] for t in v.tests if t["sample"]]
    if custom_input is None and not samples:
        raise AppError("This problem has no samples; run it on your own input", code="no_samples")
    s = Submission(
        id=uuid.uuid4(),
        user_id=who.user_id,
        candidate_id=who.candidate_id,
        problem_id=p.id,
        version_id=v.id,
        language=language,
        source=source,
        context="run",
        context_id=context_id,
        run_input=custom_input,
        only_tests=samples if custom_input is None else None,
        job_id=new_job_id(),
        max_score=0.0,
    )
    session.add(s)
    await session.commit()
    await container.queue.enqueue(build_job(s, p, v))
    return s


async def judge_reference(
    container: Container, session: AsyncSession, p: Problem, actor: Actor
) -> int:
    """Judge every reference solution on the current version."""
    who = Submitter(user_id=actor.id, candidate_id=None, role="staff")
    refs = list(
        (
            await session.scalars(
                select(ReferenceSolution).where(ReferenceSolution.problem_id == p.id)
            )
        ).all()
    )
    for r in refs:
        s = await submit(
            container,
            session,
            who,
            p,
            language=r.language,
            source=r.source,
            context="reference",
            context_id=r.id,
        )
        r.last_submission_id = s.id
        await session.commit()
    return len(refs)


# ── reading ──────────────────────────────────────────────────────────────────────────
async def get(session: AsyncSession, submission_id: uuid.UUID) -> Submission:
    s = await session.get(Submission, submission_id)
    if s is None:
        raise NotFoundError("Submission not found")
    return s


async def visible(session: AsyncSession, who: Submitter, s: Submission) -> bool:
    if who.is_staff:
        return True
    if (who.user_id and s.user_id == who.user_id) or (
        who.candidate_id and s.candidate_id == who.candidate_id
    ):
        return True
    if s.context in ("run", "reference", "practice", "assessment"):
        return False
    policy = contexts.policy(s.context)
    return bool(policy and await policy.can_view(session, who, s))


def to_out(
    s: Submission, problem: Problem | None, who: Submitter, *, with_source: bool
) -> SubmissionOut:
    own = (who.user_id is not None and s.user_id == who.user_id) or (
        who.candidate_id is not None and s.candidate_id == who.candidate_id
    )
    hide = s.hide_test_details and not who.is_staff
    tests = []
    for t in s.tests:
        sample = str(t.get("name", "")).startswith("sample/")
        if hide and not sample:
            continue
        tests.append(
            TestOut(
                name=t["name"],
                group=t["group"],
                verdict=t["verdict"],
                time_ms=t.get("time_ms", 0),
                memory_kb=t.get("memory_kb", 0),
                # Output and checker messages exist only for samples; never for hidden tests.
                output=t.get("output_preview") if sample else None,
                message=t.get("checker_message") if sample or who.is_staff else None,
            )
        )
    return SubmissionOut(
        id=s.id,
        problem_id=s.problem_id,
        problem_slug=problem.slug if problem else None,
        problem_title=problem.title if problem else None,
        user_id=s.user_id,
        language=s.language,
        context=s.context,
        context_id=s.context_id,
        status=s.status,
        verdict=s.verdict,
        score=s.score,
        max_score=s.max_score,
        time_ms=s.time_ms,
        memory_kb=s.memory_kb,
        late=s.late,
        progress=s.progress,
        created_at=s.created_at,
        judged_at=s.judged_at,
        compile_output=s.compile_output if (own or who.is_staff) else None,
        source=s.source if with_source and (own or who.is_staff) else None,
        tests=tests,
        groups=[] if hide else list(s.groups or []),
        run_input=s.run_input if own else None,
        run_output=s.run_output if own else None,
        error=s.error if who.is_staff else None,
        worker=s.worker if who.is_staff else None,
    )


# ── ingesting results ────────────────────────────────────────────────────────────────
async def heartbeat(container: Container, session: AsyncSession, beat: Heartbeat) -> None:
    s = await session.scalar(select(Submission).where(Submission.job_id == beat.job_id))
    if s is None or s.status == "done":
        return
    progress = "compiling" if beat.status == "compiling" else f"running test {beat.tests_done + 1}"
    s.status, s.progress, s.worker, s.attempt = "judging", progress, beat.worker, beat.attempt
    s.verdict = Verdict.JUDGING.value
    await session.commit()
    await container.queue.publish(
        str(s.id), json.dumps({"status": "judging", "progress": progress})
    )


async def ingest(container: Container, session: AsyncSession, result: JudgeResult) -> bool:
    """Apply a verdict. False (409 to the worker) when it is stale or already applied."""
    try:
        sid = uuid.UUID(result.submission_id)
    except ValueError:
        return False
    s = await session.scalar(select(Submission).where(Submission.id == sid).with_for_update())
    if s is None or s.job_id != result.job_id or s.status == "done":
        return False
    s.status, s.verdict = "done", result.verdict.value
    s.score, s.max_score = result.score, result.max_score or s.max_score
    s.time_ms, s.memory_kb = result.time_ms, result.memory_kb
    s.compile_output = (result.compile_output or None) and result.compile_output[:16_000]
    s.tests = [t.model_dump(exclude_none=True) for t in result.tests]
    s.groups = [g.model_dump() for g in result.groups]
    s.run_output = result.run_output
    s.worker, s.attempt, s.error, s.progress = result.worker, result.attempt, result.error, None
    s.judged_ms, s.judged_at = result.judged_ms, datetime.now(UTC)
    if s.context in COUNTED:
        await _count(session, s)
    for listener in contexts.listeners():
        await listener(container, session, s)
    await session.commit()
    await container.queue.publish(
        str(s.id), json.dumps({"status": "done", "verdict": s.verdict, "score": s.score})
    )
    return True


async def _count(session: AsyncSession, s: Submission) -> None:
    """Problem counters: accepted submissions and distinct solvers (first AC only)."""
    if s.verdict != Verdict.AC.value or s.rejudged:
        return
    values: dict[str, Any] = {"accepted_count": Problem.accepted_count + 1}
    if s.user_id is not None:
        earlier = await session.scalar(
            select(func.count())
            .select_from(Submission)
            .where(
                Submission.user_id == s.user_id,
                Submission.problem_id == s.problem_id,
                Submission.verdict == Verdict.AC.value,
                Submission.context.in_(COUNTED),
                Submission.id != s.id,
            )
        )
        if not earlier:
            values["solvers_count"] = Problem.solvers_count + 1
    await session.execute(update(Problem).where(Problem.id == s.problem_id).values(**values))


# ── rejudging ────────────────────────────────────────────────────────────────────────
async def rejudge(
    container: Container,
    session: AsyncSession,
    ids: list[uuid.UUID],
    actor: Actor,
    *,
    latest_version: bool = False,
) -> int:
    """Judge again with a new job (the old job's late result is then ignored). With
    ``latest_version`` the problem's current tests are used, otherwise the original ones."""
    rows = list(
        (
            await session.scalars(
                select(Submission).where(Submission.id.in_(ids), Submission.context != "run")
            )
        ).all()
    )
    problems = {
        p.id: p
        for p in (
            await session.scalars(
                select(Problem).where(Problem.id.in_({s.problem_id for s in rows}))
            )
        ).all()
    }
    jobs = []
    for s in rows:
        p = problems[s.problem_id]
        v = (
            await _current_version(session, p)
            if latest_version
            else await session.get(ProblemVersion, s.version_id)
        )
        if v is None:
            continue
        s.version_id, s.job_id, s.status, s.verdict = (
            v.id,
            new_job_id(),
            "queued",
            Verdict.PENDING.value,
        )
        s.rejudged += 1
        s.progress = None
        jobs.append(build_job(s, p, v))
    audit(
        session,
        actor,
        "submission.rejudged",
        "submission",
        None,
        count=len(jobs),
        latest_version=latest_version,
    )
    await session.commit()
    for job in jobs:
        await container.queue.enqueue(job)
    return len(jobs)


async def rejudge_problem(
    container: Container, session: AsyncSession, p: Problem, actor: Actor
) -> int:
    ids = list(
        (
            await session.scalars(
                select(Submission.id).where(
                    Submission.problem_id == p.id, Submission.context != "run"
                )
            )
        ).all()
    )
    return await rejudge(container, session, ids, actor, latest_version=True)
