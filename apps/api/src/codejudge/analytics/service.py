"""Analytics: a daily rollup kept exact by recomputing one bucket per judgement, and the
charts read from it.

When a submission is judged (or rejudged) the listener recomputes the bucket it belongs to
(its day, problem and language) from the submissions themselves with one indexed query, so
the rollup is idempotent: judging the same submission twice changes nothing. An advisory
lock per bucket orders concurrent judgements, and each one recounts after the previous one
committed. The overview then reads only the rollup; per-problem and per-user pages query
the submissions of that one problem or user, on their indexes.
"""

from __future__ import annotations

import statistics
import uuid
from datetime import UTC, date, datetime, time, timedelta
from typing import Any

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from codejudge.analytics.models import StatsDaily
from codejudge.analytics.schemas import (
    DayPoint,
    DifficultyRow,
    LanguageRow,
    Overview,
    ProblemRank,
    ProblemStats,
    RecentSubmission,
    UserProgress,
    VerdictMix,
)
from codejudge.core.container import Container
from codejudge.core.contexts import on_judged
from codejudge.core.errors import NotFoundError
from codejudge.problems.models import Problem
from codejudge.submissions.models import Submission
from codejudge.users.models import User

COUNTED = ("practice", "contest", "assignment", "assessment")

VERDICT_COLUMNS = {
    "AC": "accepted",
    "WA": "wrong_answer",
    "TLE": "time_limit",
    "MLE": "memory_limit",
    "RE": "runtime_error",
    "CE": "compile_error",
    "OLE": "output_limit",
    "IE": "internal_error",
}

_RECOUNT = text(
    """
    INSERT INTO stats_daily (day, problem_id, language, submissions, accepted, wrong_answer,
        time_limit, memory_limit, runtime_error, compile_error, output_limit, internal_error,
        users)
    SELECT CAST(:day AS date), CAST(:problem_id AS uuid), CAST(:language AS varchar), count(*),
        count(*) FILTER (WHERE verdict = 'AC'), count(*) FILTER (WHERE verdict = 'WA'),
        count(*) FILTER (WHERE verdict = 'TLE'), count(*) FILTER (WHERE verdict = 'MLE'),
        count(*) FILTER (WHERE verdict = 'RE'), count(*) FILTER (WHERE verdict = 'CE'),
        count(*) FILTER (WHERE verdict = 'OLE'), count(*) FILTER (WHERE verdict = 'IE'),
        count(DISTINCT coalesce(user_id, candidate_id))
    FROM submissions
    WHERE problem_id = CAST(:problem_id AS uuid) AND language = CAST(:language AS varchar)
      AND status = 'done'
      AND context IN ('practice', 'contest', 'assignment', 'assessment')
      AND created_at >= :start AND created_at < :end
    ON CONFLICT (day, problem_id, language) DO UPDATE SET
        submissions = EXCLUDED.submissions, accepted = EXCLUDED.accepted,
        wrong_answer = EXCLUDED.wrong_answer, time_limit = EXCLUDED.time_limit,
        memory_limit = EXCLUDED.memory_limit, runtime_error = EXCLUDED.runtime_error,
        compile_error = EXCLUDED.compile_error, output_limit = EXCLUDED.output_limit,
        internal_error = EXCLUDED.internal_error, users = EXCLUDED.users
    """
)


def bucket_day(created_at: datetime) -> date:
    return created_at.astimezone(UTC).date()


async def recount(session: AsyncSession, problem_id: uuid.UUID, language: str, day: date) -> None:
    start = datetime.combine(day, time.min, tzinfo=UTC)
    key = f"stats:{problem_id}:{language}:{day.isoformat()}"
    await session.execute(select(func.pg_advisory_xact_lock(func.hashtext(key))))
    await session.execute(
        _RECOUNT,
        {
            "day": day,
            "problem_id": problem_id,
            "language": language,
            "start": start,
            "end": start + timedelta(days=1),
        },
    )


@on_judged
async def record(_container: Container, session: AsyncSession, s: Submission) -> None:
    if s.context not in COUNTED:
        return
    await session.flush()  # the recount must see this submission's new verdict
    await recount(session, s.problem_id, s.language, bucket_day(s.created_at))


# ── reading ──────────────────────────────────────────────────────────────────────────
def _rate(accepted: int, submissions: int) -> float | None:
    return round(accepted / submissions, 4) if submissions else None


def _series(rows: dict[date, tuple[int, int]], since: date, until: date) -> list[DayPoint]:
    out = []
    day = since
    while day <= until:
        submissions, accepted = rows.get(day, (0, 0))
        out.append(DayPoint(day=day, submissions=submissions, accepted=accepted))
        day += timedelta(days=1)
    return out


def _sum(column: Any) -> Any:
    return func.coalesce(func.sum(column), 0)


def _mix(row: Any) -> VerdictMix:
    return VerdictMix(**{v: int(getattr(row, c) or 0) for v, c in VERDICT_COLUMNS.items()})


def _verdict_sums() -> list[Any]:
    return [_sum(getattr(StatsDaily, c)).label(c) for c in VERDICT_COLUMNS.values()]


async def overview(session: AsyncSession, days: int = 30) -> Overview:
    until = datetime.now(UTC).date()
    since = until - timedelta(days=days - 1)
    recent = StatsDaily.day >= since

    daily_rows = await session.execute(
        select(StatsDaily.day, _sum(StatsDaily.submissions), _sum(StatsDaily.accepted))
        .where(recent)
        .group_by(StatsDaily.day)
    )
    daily = {d: (int(n), int(a)) for d, n, a in daily_rows.all()}

    totals = (
        await session.execute(
            select(
                _sum(StatsDaily.submissions).label("submissions"),
                _sum(StatsDaily.users).label("users"),
                *_verdict_sums(),
            ).where(recent)
        )
    ).one()

    submissions_sum = _sum(StatsDaily.submissions)
    top = await session.execute(
        select(
            Problem.id,
            Problem.slug,
            Problem.title,
            Problem.difficulty,
            submissions_sum,
            _sum(StatsDaily.accepted),
        )
        .join(Problem, Problem.id == StatsDaily.problem_id)
        .where(recent)
        .group_by(Problem.id)
        .order_by(submissions_sum.desc(), Problem.slug)
        .limit(10)
    )
    by_difficulty = await session.execute(
        select(Problem.difficulty, _sum(StatsDaily.submissions), _sum(StatsDaily.accepted))
        .join(Problem, Problem.id == StatsDaily.problem_id)
        .where(recent)
        .group_by(Problem.difficulty)
    )
    order = {"easy": 0, "medium": 1, "hard": 2}
    languages = await session.execute(
        select(StatsDaily.language, submissions_sum, _sum(StatsDaily.accepted))
        .where(recent)
        .group_by(StatsDaily.language)
        .order_by(submissions_sum.desc())
    )
    submissions = int(totals.submissions)
    accepted = int(totals.accepted)
    return Overview(
        days=days,
        submissions=submissions,
        accepted=accepted,
        acceptance=_rate(accepted, submissions),
        active_users=int(totals.users),
        daily=_series(daily, since, until),
        verdicts=_mix(totals),
        top_problems=[
            ProblemRank(
                problem_id=pid,
                slug=slug,
                title=title,
                difficulty=difficulty,
                submissions=int(n),
                accepted=int(a),
                acceptance=_rate(int(a), int(n)),
            )
            for pid, slug, title, difficulty, n, a in top.all()
        ],
        by_difficulty=sorted(
            (
                DifficultyRow(
                    difficulty=d,
                    submissions=int(n),
                    accepted=int(a),
                    acceptance=_rate(int(a), int(n)),
                )
                for d, n, a in by_difficulty.all()
            ),
            key=lambda r: order.get(r.difficulty, 9),
        ),
        languages=[
            LanguageRow(language=lang, submissions=int(n), accepted=int(a))
            for lang, n, a in languages.all()
        ],
    )


def _author() -> Any:
    return func.coalesce(Submission.user_id, Submission.candidate_id)


async def problem_stats(session: AsyncSession, p: Problem, days: int = 30) -> ProblemStats:
    totals = (
        await session.execute(
            select(_sum(StatsDaily.submissions).label("submissions"), *_verdict_sums()).where(
                StatsDaily.problem_id == p.id
            )
        )
    ).one()
    until = datetime.now(UTC).date()
    since = until - timedelta(days=days - 1)
    daily_rows = await session.execute(
        select(StatsDaily.day, _sum(StatsDaily.submissions), _sum(StatsDaily.accepted))
        .where(StatsDaily.problem_id == p.id, StatsDaily.day >= since)
        .group_by(StatsDaily.day)
    )
    counted = (
        Submission.problem_id == p.id,
        Submission.context.in_(COUNTED),
        Submission.status == "done",
    )
    median_time = await session.scalar(
        select(func.percentile_cont(0.5).within_group(Submission.time_ms)).where(
            *counted, Submission.verdict == "AC"
        )
    )
    attempters = await session.scalar(select(func.count(func.distinct(_author()))).where(*counted))
    # Submissions each solver made up to and including their first accepted one.
    firsts = (
        select(_author().label("author"), func.min(Submission.created_at).label("first_ac"))
        .where(*counted, Submission.verdict == "AC")
        .group_by(_author())
        .subquery()
    )
    attempts_rows = await session.execute(
        select(firsts.c.author, func.count())
        .select_from(Submission)
        .join(firsts, _author() == firsts.c.author)
        .where(*counted, Submission.created_at <= firsts.c.first_ac)
        .group_by(firsts.c.author)
    )
    attempts = [int(n) for _, n in attempts_rows.all()]
    buckets = {"1": 0, "2": 0, "3": 0, "4+": 0}
    for n in attempts:
        buckets[str(n) if n < 4 else "4+"] += 1
    submissions = int(totals.submissions)
    accepted = int(totals.accepted)
    return ProblemStats(
        problem_id=p.id,
        slug=p.slug,
        title=p.title,
        submissions=submissions,
        accepted=accepted,
        acceptance=_rate(accepted, submissions),
        verdicts=_mix(totals),
        attempters=int(attempters or 0),
        solvers=len(attempts),
        median_ac_time_ms=float(median_time) if median_time is not None else None,
        median_attempts_to_ac=float(statistics.median(attempts)) if attempts else None,
        attempts_to_ac=buckets,
        daily=_series({d: (int(n), int(a)) for d, n, a in daily_rows.all()}, since, until),
    )


async def user_progress(session: AsyncSession, user_id: uuid.UUID, days: int = 30) -> UserProgress:
    user = await session.get(User, user_id)
    if user is None:
        raise NotFoundError("User not found")
    mine = (
        Submission.user_id == user_id,
        Submission.context.in_(COUNTED),
        Submission.status == "done",
    )
    totals = (
        await session.execute(
            select(
                func.count().label("submissions"),
                func.count().filter(Submission.verdict == "AC").label("accepted"),
                func.count(func.distinct(Submission.problem_id)).label("attempted"),
            ).where(*mine)
        )
    ).one()
    solved_rows = await session.execute(
        select(Problem.difficulty, func.count(func.distinct(Problem.id)))
        .join(Submission, Submission.problem_id == Problem.id)
        .where(*mine, Submission.verdict == "AC")
        .group_by(Problem.difficulty)
    )
    by_difficulty = {"easy": 0, "medium": 0, "hard": 0}
    for difficulty, n in solved_rows.all():
        by_difficulty[difficulty] = int(n)
    until = datetime.now(UTC).date()
    since = until - timedelta(days=days - 1)
    day = func.date(func.timezone("UTC", Submission.created_at))
    activity_rows = await session.execute(
        select(day, func.count(), func.count().filter(Submission.verdict == "AC"))
        .where(*mine, Submission.created_at >= datetime.combine(since, time.min, tzinfo=UTC))
        .group_by(day)
    )
    recent_rows = await session.execute(
        select(Submission, Problem.slug, Problem.title)
        .join(Problem, Problem.id == Submission.problem_id)
        .where(Submission.user_id == user_id, Submission.context.in_(COUNTED))
        .order_by(Submission.created_at.desc())
        .limit(10)
    )
    return UserProgress(
        user_id=user.id,
        name=user.name,
        solved=sum(by_difficulty.values()),
        attempted=int(totals.attempted),
        submissions=int(totals.submissions),
        accepted_submissions=int(totals.accepted),
        solved_by_difficulty=by_difficulty,
        activity=_series({d: (int(n), int(a)) for d, n, a in activity_rows.all()}, since, until),
        recent=[
            RecentSubmission(
                id=s.id,
                problem_slug=slug,
                problem_title=title,
                language=s.language,
                verdict=s.verdict,
                score=s.score,
                max_score=s.max_score,
                created_at=s.created_at,
            )
            for s, slug, title in recent_rows.all()
        ],
    )
