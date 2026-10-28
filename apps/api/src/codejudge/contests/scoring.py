"""Contest scoreboards, computed from attempts. Pure functions: no database, no clock.

ICPC: rank by problems solved, then penalty (for each solved problem, the minutes from the
start to its first accepted attempt plus ``penalty_minutes`` for every rejected attempt
before it), then the time of the last accepted attempt. A compilation error is not an
attempt (it costs nothing), attempts after the first acceptance are ignored, and an
internal error is the judge's fault, so it is ignored too.

IOI: per problem the best score of any attempt (scaled to the problem's contest points),
total is the sum, ties go to whoever reached their total first.

Freeze: in the frozen view every attempt made at or after ``freeze_at`` is shown as
pending: counted, verdict hidden. Unjudged attempts are pending in every view.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

IGNORED = frozenset({"CE", "IE", "SKIPPED"})


@dataclass(frozen=True)
class Attempt:
    user_id: uuid.UUID
    label: str
    created_at: datetime
    status: str  # queued, judging, done
    verdict: str
    score: float = 0.0
    max_score: float = 0.0


@dataclass
class Cell:
    label: str
    solved: bool = False
    # Rejected attempts counted towards the penalty (before the first acceptance).
    attempts: int = 0
    pending: int = 0
    minute: int | None = None
    score: float = 0.0
    first: bool = False
    # When the best score (IOI) or the acceptance (ICPC) happened.
    at: datetime | None = None


@dataclass
class Row:
    user_id: uuid.UUID
    cells: dict[str, Cell]
    solved: int = 0
    penalty: int = 0
    score: float = 0.0
    rank: int = 0
    # Tie breaker: last acceptance (ICPC) or when the total was reached (IOI).
    tie: datetime | None = None
    attempted: bool = False


@dataclass(frozen=True)
class Problem:
    label: str
    points: float = 100.0


@dataclass
class Board:
    rows: list[Row] = field(default_factory=list)


def _pending(a: Attempt, freeze_at: datetime | None) -> bool:
    return a.status != "done" or (freeze_at is not None and a.created_at >= freeze_at)


def _minute(start: datetime, t: datetime) -> int:
    return max(0, int((t - start).total_seconds() // 60))


def _empty_rows(users: Iterable[uuid.UUID], problems: list[Problem]) -> dict[uuid.UUID, Row]:
    return {
        u: Row(user_id=u, cells={p.label: Cell(label=p.label) for p in problems}) for u in users
    }


def _rank(rows: list[Row], key: Callable[[Row], tuple[Any, ...]]) -> list[Row]:
    """Sort and number; rows with equal keys share a rank (1, 2, 2, 4)."""
    ordered = sorted(rows, key=key)
    previous: tuple[tuple[Any, ...], int] | None = None
    for i, row in enumerate(ordered, start=1):
        current = key(row)
        row.rank = previous[1] if previous and previous[0] == current else i
        previous = (current, row.rank)
    return ordered


def _first_solvers(rows: list[Row]) -> None:
    best: dict[str, Cell] = {}
    for row in rows:
        for cell in row.cells.values():
            if cell.at is None or not (cell.solved or cell.score > 0):
                continue
            current = best.get(cell.label)
            if current is None or cell.at < (current.at or cell.at):
                best[cell.label] = cell
    for cell in best.values():
        cell.first = True


def icpc(
    attempts: Iterable[Attempt],
    problems: list[Problem],
    participants: Iterable[uuid.UUID],
    *,
    start: datetime,
    penalty_minutes: int,
    freeze_at: datetime | None = None,
) -> list[Row]:
    labels = {p.label for p in problems}
    rows = _empty_rows(participants, problems)
    for a in sorted(attempts, key=lambda a: a.created_at):
        if a.label not in labels:
            continue
        row = rows.setdefault(a.user_id, _empty_rows([a.user_id], problems)[a.user_id])
        row.attempted = True
        cell = row.cells[a.label]
        if cell.solved:
            continue
        if _pending(a, freeze_at):
            cell.pending += 1
            continue
        if a.verdict in IGNORED:
            continue
        if a.verdict == "AC":
            cell.solved, cell.at, cell.minute = True, a.created_at, _minute(start, a.created_at)
            row.solved += 1
            row.penalty += cell.minute + penalty_minutes * cell.attempts
            row.tie = a.created_at if row.tie is None or a.created_at > row.tie else row.tie
        else:
            cell.attempts += 1
    ordered = _rank(
        list(rows.values()),
        lambda r: (-r.solved, r.penalty, _minute(start, r.tie) if r.tie else 0),
    )
    _first_solvers(ordered)
    return ordered


def ioi(
    attempts: Iterable[Attempt],
    problems: list[Problem],
    participants: Iterable[uuid.UUID],
    *,
    start: datetime,
    freeze_at: datetime | None = None,
) -> list[Row]:
    points = {p.label: p.points for p in problems}
    rows = _empty_rows(participants, problems)
    for a in sorted(attempts, key=lambda a: a.created_at):
        if a.label not in points:
            continue
        row = rows.setdefault(a.user_id, _empty_rows([a.user_id], problems)[a.user_id])
        row.attempted = True
        cell = row.cells[a.label]
        if _pending(a, freeze_at):
            cell.pending += 1
            continue
        if a.verdict in IGNORED:
            continue
        cell.attempts += 1
        scaled = round(a.score / a.max_score * points[a.label], 4) if a.max_score else 0.0
        if scaled > cell.score:
            cell.score, cell.at, cell.minute = scaled, a.created_at, _minute(start, a.created_at)
        cell.solved = cell.score >= points[a.label] > 0
    for row in rows.values():
        row.score = round(sum(c.score for c in row.cells.values()), 4)
        row.solved = sum(1 for c in row.cells.values() if c.solved)
        reached = [c.at for c in row.cells.values() if c.at is not None and c.score > 0]
        row.tie = max(reached) if reached else None
    far = datetime.max.replace(tzinfo=start.tzinfo)
    ordered = _rank(list(rows.values()), lambda r: (-r.score, r.tie or far))
    _first_solvers(ordered)
    return ordered
