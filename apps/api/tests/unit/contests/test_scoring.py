"""Scoreboard rules, without a database: ICPC penalties, IOI best scores, the freeze."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from codejudge.contests.scoring import Attempt, Problem, icpc, ioi

START = datetime(2026, 11, 1, 10, 0, tzinfo=UTC)
A, B, C = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
PROBLEMS = [Problem("A"), Problem("B")]


def at(minutes: float) -> datetime:
    return START + timedelta(minutes=minutes)


def att(
    user: uuid.UUID,
    label: str,
    minute: float,
    verdict: str,
    score: float = 0.0,
    status: str = "done",
) -> Attempt:
    return Attempt(user, label, at(minute), status, verdict, score, 100.0)


def by_user(rows: list) -> dict:  # type: ignore[type-arg]
    return {r.user_id: r for r in rows}


def test_icpc_penalty_counts_minutes_and_rejected_tries() -> None:
    rows = icpc(
        [
            att(A, "A", 10, "AC"),
            att(B, "A", 5, "WA"),
            att(B, "A", 7, "TLE"),
            att(B, "A", 12, "AC"),
            att(B, "A", 30, "WA"),  # after the acceptance: ignored
        ],
        PROBLEMS, [A, B], start=START, penalty_minutes=20,
    )  # fmt: skip
    users = by_user(rows)
    assert users[A].penalty == 10 and users[A].solved == 1
    assert users[B].penalty == 12 + 2 * 20 and users[B].cells["A"].attempts == 2
    assert [r.user_id for r in rows] == [A, B] and rows[0].rank == 1 and rows[1].rank == 2


def test_icpc_compilation_errors_and_internal_errors_cost_nothing() -> None:
    rows = icpc(
        [att(A, "A", 3, "CE"), att(A, "A", 4, "IE"), att(A, "A", 9, "AC")],
        PROBLEMS,
        [A],
        start=START,
        penalty_minutes=20,
    )
    assert rows[0].penalty == 9 and rows[0].cells["A"].attempts == 0


def test_icpc_more_solved_beats_less_penalty() -> None:
    rows = icpc(
        [att(A, "A", 100, "AC"), att(A, "B", 110, "AC"), att(B, "A", 1, "AC")],
        PROBLEMS, [A, B], start=START, penalty_minutes=20,
    )  # fmt: skip
    assert [r.user_id for r in rows] == [A, B]


def test_icpc_equal_results_share_a_rank_and_first_solves_are_marked() -> None:
    rows = icpc(
        [att(A, "A", 10, "AC"), att(B, "A", 10.5, "AC")],
        PROBLEMS,
        [A, B, C],
        start=START,
        penalty_minutes=20,
    )
    users = by_user(rows)
    assert users[A].rank == users[B].rank == 1 and users[C].rank == 3
    assert users[A].cells["A"].first and not users[B].cells["A"].first


def test_the_freeze_hides_later_verdicts_as_pending() -> None:
    attempts = [att(A, "A", 10, "WA"), att(A, "A", 50, "AC"), att(B, "A", 55, "WA")]
    live = by_user(icpc(attempts, PROBLEMS, [A, B], start=START, penalty_minutes=20))
    frozen = by_user(
        icpc(attempts, PROBLEMS, [A, B], start=START, penalty_minutes=20, freeze_at=at(40))
    )
    assert live[A].solved == 1 and live[B].cells["A"].attempts == 1
    assert (
        frozen[A].solved == 0
        and frozen[A].cells["A"].pending == 1
        and frozen[A].cells["A"].attempts == 1
    )
    assert frozen[B].cells["A"].pending == 1 and frozen[B].cells["A"].attempts == 0


def test_unjudged_attempts_are_pending_in_every_view() -> None:
    rows = icpc(
        [att(A, "A", 5, "PENDING", status="queued")], PROBLEMS, [A], start=START, penalty_minutes=20
    )
    assert rows[0].cells["A"].pending == 1 and rows[0].solved == 0


def test_ioi_keeps_the_best_score_per_problem() -> None:
    rows = ioi(
        [att(A, "A", 5, "WA", 40), att(A, "A", 9, "WA", 70), att(A, "A", 12, "WA", 30), att(A, "B", 20, "AC", 100)],
        PROBLEMS, [A], start=START,
    )  # fmt: skip
    row = rows[0]
    assert row.cells["A"].score == 70 and row.cells["B"].score == 100 and row.score == 170
    assert row.cells["B"].solved and not row.cells["A"].solved


def test_ioi_scales_to_contest_points_and_ties_go_to_the_earlier_total() -> None:
    problems = [Problem("A", 50.0)]
    rows = ioi(
        [att(A, "A", 30, "AC", 100), att(B, "A", 10, "AC", 100)], problems, [A, B], start=START
    )
    assert rows[0].user_id == B and rows[0].score == 50 and rows[1].rank == 2


def test_people_who_never_submitted_still_have_a_row() -> None:
    rows = icpc([], PROBLEMS, [A, B], start=START, penalty_minutes=20)
    assert {r.user_id for r in rows} == {A, B} and all(r.rank == 1 for r in rows)
