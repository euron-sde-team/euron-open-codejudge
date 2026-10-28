"""Response models for analytics."""

from __future__ import annotations

import uuid
from datetime import date, datetime

from codejudge.core.schemas import ApiModel


class DayPoint(ApiModel):
    day: date
    submissions: int
    accepted: int


class VerdictMix(ApiModel):
    AC: int = 0
    WA: int = 0
    TLE: int = 0
    MLE: int = 0
    RE: int = 0
    CE: int = 0
    OLE: int = 0
    IE: int = 0


class ProblemRank(ApiModel):
    problem_id: uuid.UUID
    slug: str
    title: str
    difficulty: str
    submissions: int
    accepted: int
    acceptance: float | None


class DifficultyRow(ApiModel):
    difficulty: str
    submissions: int
    accepted: int
    acceptance: float | None


class LanguageRow(ApiModel):
    language: str
    submissions: int
    accepted: int


class Overview(ApiModel):
    days: int
    submissions: int
    accepted: int
    acceptance: float | None
    active_users: int
    daily: list[DayPoint]
    verdicts: VerdictMix
    top_problems: list[ProblemRank]
    by_difficulty: list[DifficultyRow]
    languages: list[LanguageRow]


class ProblemStats(ApiModel):
    problem_id: uuid.UUID
    slug: str
    title: str
    submissions: int
    accepted: int
    acceptance: float | None
    verdicts: VerdictMix
    attempters: int
    solvers: int
    median_ac_time_ms: float | None
    median_attempts_to_ac: float | None
    attempts_to_ac: dict[str, int]
    daily: list[DayPoint]


class RecentSubmission(ApiModel):
    id: uuid.UUID
    problem_slug: str
    problem_title: str
    language: str
    verdict: str
    score: float
    max_score: float
    created_at: datetime


class UserProgress(ApiModel):
    user_id: uuid.UUID
    name: str
    solved: int
    attempted: int
    submissions: int
    accepted_submissions: int
    solved_by_difficulty: dict[str, int]
    activity: list[DayPoint]
    recent: list[RecentSubmission]
