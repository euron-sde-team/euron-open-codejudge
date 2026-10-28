"""Assignment marks, statuses and the gradebook CSV (no database)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from codejudge.classrooms.models import Assignment
from codejudge.classrooms.schemas import AssignmentProblemOut, Gradebook, GradeCell, GradeRow
from codejudge.classrooms.service import (
    CODE_ALPHABET,
    CODE_LENGTH,
    effective,
    gradebook_csv,
    new_join_code,
    status_of,
)

NOW = datetime(2026, 10, 28, 12, 0, tzinfo=UTC)


def assignment(policy: str = "penalty", penalty: int = 20) -> Assignment:
    return Assignment(
        id=uuid.uuid4(),
        class_id=uuid.uuid4(),
        title="Week 1",
        opens_at=NOW - timedelta(days=1),
        due_at=NOW + timedelta(days=1),
        late_policy=policy,
        penalty_percent=penalty,
    )


def test_marks_scale_to_points_and_late_penalties_apply_only_under_the_penalty_policy() -> None:
    assert effective(assignment(), 50, 100, 100, late=False) == 50
    assert effective(assignment(), 50, 40, 100, late=False) == 20
    assert effective(assignment("penalty", 20), 50, 100, 100, late=True) == 40
    assert effective(assignment("accept"), 50, 100, 100, late=True) == 50
    assert effective(assignment(), 50, 0, 0, late=False) == 0


def test_status_follows_the_window_and_the_late_policy() -> None:
    a = assignment()
    assert status_of(a, a.due_at, a.opens_at - timedelta(seconds=1)) == "upcoming"
    assert status_of(a, a.due_at, NOW) == "open"
    assert status_of(a, a.due_at, a.due_at + timedelta(seconds=1)) == "late"
    assert status_of(assignment("refuse"), a.due_at, a.due_at + timedelta(seconds=1)) == "closed"
    # An extension moves the due time for that student.
    assert status_of(a, a.due_at + timedelta(days=2), a.due_at + timedelta(days=1)) == "open"


def test_join_codes_avoid_look_alike_characters() -> None:
    codes = {new_join_code() for _ in range(200)}
    assert len(codes) == 200
    assert all(len(c) == CODE_LENGTH and set(c) <= set(CODE_ALPHABET) for c in codes)
    assert not set("01OI") & set(CODE_ALPHABET)


def test_the_gradebook_csv_marks_late_work_and_neutralises_formulas() -> None:
    pid = uuid.uuid4()
    book = Gradebook(
        assignment_id=uuid.uuid4(),
        title="Week 1",
        total_points=50,
        problems=[
            AssignmentProblemOut(id=pid, slug="sum", title="Sum", difficulty="easy", points=50)
        ],
        rows=[
            GradeRow(
                user_id=uuid.uuid4(),
                name="=HYPERLINK(1)",
                email="a@example.test",
                total=40,
                cells=[GradeCell(problem_id=pid, score=40, late=True, attempts=2)],
            ),
            GradeRow(
                user_id=uuid.uuid4(),
                name="Bo",
                email="b@example.test",
                total=0,
                cells=[GradeCell(problem_id=pid, score=None)],
            ),
        ],
    )
    lines = gradebook_csv(book).splitlines()
    assert lines[0] == "name,email,sum (50),total (50)"
    assert lines[1] == "'=HYPERLINK(1),a@example.test,40 (late),40"
    assert lines[2] == "Bo,b@example.test,,0"
