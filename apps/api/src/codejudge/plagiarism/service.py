"""Plagiarism checks: start a run, compare in the background, read the flagged pairs.

A run takes one submission per author and problem in its scope (their latest accepted one,
or else their best scoring one), groups them by problem and language, fingerprints each
program (``winnow``) and compares every pair in a group. Fingerprints shared by most of
the group (given template code, the obvious idiom) are ignored when the group is big
enough to tell. Pairs at or above the threshold are stored, the most similar first, with
the matched line ranges for a side-by-side view. Comparing is CPU work, so it runs in a
thread off the event loop, and groups are capped (newest programs first) so one huge
problem cannot stall the worker.

A similarity score is a signal for a person to review, never a verdict: the UI says so.
"""

from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import Select, delete, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from codejudge.audit.service import Actor, audit
from codejudge.core.container import Container
from codejudge.core.errors import AppError, NotFoundError
from codejudge.core.tasks import periodic
from codejudge.plagiarism import winnow
from codejudge.plagiarism.models import PlagiarismPair, PlagiarismRun
from codejudge.plagiarism.schemas import (
    PairDetail,
    PairOut,
    PlagiarismRunCreate,
    RunDetail,
    RunOut,
    Side,
)
from codejudge.problems import service as problems
from codejudge.problems.models import Problem
from codejudge.submissions.models import Submission
from codejudge.users.models import User

COUNTED = ("practice", "contest", "assignment", "assessment")
MAX_PER_GROUP = 1500
MAX_PAIRS = 500
STALE_RUNNING = timedelta(minutes=30)


# ── starting and reading ─────────────────────────────────────────────────────────────
async def start(session: AsyncSession, data: PlagiarismRunCreate, actor: Actor) -> PlagiarismRun:
    if data.scope == "problem":
        scope_id = (await problems.get(session, data.scope_id)).id
    else:
        try:
            scope_id = uuid.UUID(data.scope_id)
        except ValueError as exc:
            raise AppError(f"scope_id must be the {data.scope}'s id", code="invalid_scope") from exc
    run = PlagiarismRun(
        id=uuid.uuid4(),
        scope=data.scope,
        scope_id=scope_id,
        threshold=data.threshold,
        created_by=actor.id,
    )
    session.add(run)
    audit(session, actor, "plagiarism.run_started", data.scope, scope_id, threshold=data.threshold)
    await session.commit()
    await session.refresh(run)
    return run


def run_out(run: PlagiarismRun) -> RunOut:
    return RunOut.model_validate(run)


async def list_runs(
    session: AsyncSession, scope: str | None, scope_id: uuid.UUID | None, limit: int
) -> list[RunOut]:
    query = select(PlagiarismRun).order_by(PlagiarismRun.created_at.desc()).limit(limit)
    if scope:
        query = query.where(PlagiarismRun.scope == scope)
    if scope_id:
        query = query.where(PlagiarismRun.scope_id == scope_id)
    return [run_out(r) for r in (await session.scalars(query)).all()]


async def get_run(session: AsyncSession, run_id: uuid.UUID) -> PlagiarismRun:
    run = await session.get(PlagiarismRun, run_id)
    if run is None:
        raise NotFoundError("Plagiarism run not found")
    return run


def _author_label(s: Submission, names: dict[uuid.UUID, str]) -> str:
    if s.user_id is not None:
        return names.get(s.user_id, "Deleted user")
    return f"Candidate {str(s.candidate_id)[:8]}" if s.candidate_id else "Unknown"


async def _pairs_out(
    session: AsyncSession, pairs: list[PlagiarismPair]
) -> tuple[list[PairOut], dict[uuid.UUID, Submission]]:
    """Pairs with their authors and problems, in three queries whatever the count."""
    ids = {p.submission_a for p in pairs} | {p.submission_b for p in pairs}
    subs = {
        s.id: s
        for s in (await session.scalars(select(Submission).where(Submission.id.in_(ids)))).all()
    }
    user_ids = {s.user_id for s in subs.values() if s.user_id}
    names = {
        u.id: u.name
        for u in (await session.scalars(select(User).where(User.id.in_(user_ids)))).all()
    }
    probs = {
        p.id: p
        for p in (
            await session.scalars(
                select(Problem).where(Problem.id.in_({x.problem_id for x in pairs}))
            )
        ).all()
    }
    out = []
    for pair in pairs:
        a, b, prob = (
            subs.get(pair.submission_a),
            subs.get(pair.submission_b),
            probs.get(pair.problem_id),
        )
        if a is None or b is None or prob is None:
            continue
        out.append(
            PairOut(
                id=pair.id,
                problem_id=prob.id,
                problem_slug=prob.slug,
                problem_title=prob.title,
                language=pair.language,
                similarity=pair.similarity,
                a=_side(a, names, pair.coverage_a, pair.ranges_a),
                b=_side(b, names, pair.coverage_b, pair.ranges_b),
            )
        )
    return out, subs


def _side(s: Submission, names: dict[uuid.UUID, str], coverage: float, ranges: list[Any]) -> Side:
    return Side(
        submission_id=s.id,
        author=_author_label(s, names),
        user_id=s.user_id,
        verdict=s.verdict,
        score=s.score,
        created_at=s.created_at,
        coverage=coverage,
        ranges=[(int(r[0]), int(r[1])) for r in ranges],
    )


async def detail(session: AsyncSession, run_id: uuid.UUID) -> RunDetail:
    run = await get_run(session, run_id)
    pairs = list(
        (
            await session.scalars(
                select(PlagiarismPair)
                .where(PlagiarismPair.run_id == run.id)
                .order_by(PlagiarismPair.similarity.desc(), PlagiarismPair.id)
            )
        ).all()
    )
    out, _ = await _pairs_out(session, pairs)
    return RunDetail(**run_out(run).model_dump(), pairs=out)


async def pair_detail(session: AsyncSession, pair_id: uuid.UUID) -> PairDetail:
    pair = await session.get(PlagiarismPair, pair_id)
    if pair is None:
        raise NotFoundError("Pair not found")
    out, subs = await _pairs_out(session, [pair])
    if not out:
        raise NotFoundError("The submissions of this pair no longer exist")
    return PairDetail(
        **out[0].model_dump(),
        source_a=subs[pair.submission_a].source,
        source_b=subs[pair.submission_b].source,
    )


# ── comparing ────────────────────────────────────────────────────────────────────────
@dataclass(frozen=True)
class Program:
    submission_id: uuid.UUID
    problem_id: uuid.UUID
    language: str
    source: str


@dataclass(frozen=True)
class Found:
    problem_id: uuid.UUID
    language: str
    a: uuid.UUID
    b: uuid.UUID
    match: winnow.Match


def documents_query(scope: str, scope_id: uuid.UUID) -> Select[uuid.UUID, uuid.UUID, str, str]:
    """One submission per author and problem: the latest accepted, else the best scoring."""
    author = func.coalesce(Submission.user_id, Submission.candidate_id)
    query = select(
        Submission.id, Submission.problem_id, Submission.language, Submission.source
    ).where(Submission.status == "done", author.is_not(None))
    if scope == "problem":
        query = query.where(Submission.problem_id == scope_id, Submission.context.in_(COUNTED))
    else:
        query = query.where(Submission.context == scope, Submission.context_id == scope_id)
    return query.distinct(Submission.problem_id, author).order_by(
        Submission.problem_id,
        author,
        (Submission.verdict == "AC").desc(),
        Submission.score.desc(),
        Submission.created_at.desc(),
    )


def analyse(programs: list[Program], threshold: float) -> tuple[int, list[Found]]:
    """Every pair within each (problem, language) group. Returns (comparisons, flagged)."""
    groups: dict[tuple[uuid.UUID, str], list[Program]] = {}
    for p in programs:
        groups.setdefault((p.problem_id, p.language), []).append(p)
    comparisons = 0
    found: list[Found] = []
    for (problem_id, language), members in groups.items():
        members = members[:MAX_PER_GROUP]
        docs = [winnow.fingerprint(str(m.submission_id), m.source, language) for m in members]
        ignore = winnow.common(docs)
        for i in range(len(docs)):
            for j in range(i + 1, len(docs)):
                comparisons += 1
                match = winnow.compare(docs[i], docs[j], ignore)
                if match is not None and match.similarity >= threshold:
                    found.append(
                        Found(
                            problem_id,
                            language,
                            members[i].submission_id,
                            members[j].submission_id,
                            match,
                        )
                    )
    found.sort(key=lambda f: f.match.similarity, reverse=True)
    return comparisons, found[:MAX_PAIRS]


async def execute(session: AsyncSession, run: PlagiarismRun) -> None:
    rows = (await session.execute(documents_query(run.scope, run.scope_id))).all()
    programs = [Program(r[0], r[1], r[2], r[3]) for r in rows]
    comparisons, found = await asyncio.to_thread(analyse, programs, run.threshold)
    for f in found:
        session.add(
            PlagiarismPair(
                id=uuid.uuid4(),
                run_id=run.id,
                problem_id=f.problem_id,
                language=f.language,
                submission_a=f.a,
                submission_b=f.b,
                similarity=f.match.similarity,
                coverage_a=f.match.coverage_a,
                coverage_b=f.match.coverage_b,
                ranges_a=[list(r) for r in f.match.ranges_a],
                ranges_b=[list(r) for r in f.match.ranges_b],
            )
        )
    run.documents, run.comparisons, run.flagged = len(programs), comparisons, len(found)
    run.status, run.finished_at = "done", datetime.now(UTC)


@periodic("plagiarism.runs")
async def process_next(container: Container) -> int:
    """Claim one queued run (or one a dead worker left running) and complete it."""
    async with container.db.sessionmaker() as session:
        stale = datetime.now(UTC) - STALE_RUNNING
        run = await session.scalar(
            select(PlagiarismRun)
            .where(
                or_(
                    PlagiarismRun.status == "queued",
                    (PlagiarismRun.status == "running") & (PlagiarismRun.started_at < stale),
                )
            )
            .order_by(PlagiarismRun.created_at)
            .limit(1)
            .with_for_update(skip_locked=True)
        )
        if run is None:
            return 0
        run.status, run.started_at, run.error = "running", datetime.now(UTC), None
        await session.commit()
        run_id = run.id
    async with container.db.sessionmaker() as session:
        run = await session.get(PlagiarismRun, run_id)
        assert run is not None
        try:
            # A run reclaimed from a dead worker may have stored pairs already: start clean.
            await session.execute(delete(PlagiarismPair).where(PlagiarismPair.run_id == run_id))
            await execute(session, run)
            await session.commit()
        except Exception as exc:
            await session.rollback()
            await session.execute(
                update(PlagiarismRun)
                .where(PlagiarismRun.id == run_id)
                .values(status="failed", error=str(exc)[:500], finished_at=datetime.now(UTC))
            )
            await session.commit()
            raise
    return 1
