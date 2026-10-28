"""AC8: classes, assignments, deadlines and the gradebook, through the real API."""

from __future__ import annotations

import csv
import io
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import pytest

from tests.integration.conftest import Stack, make_problem

pytestmark = pytest.mark.asyncio

AC = "print(sum(map(int, input().split())))"
TWO_GROUPS = [
    {"name": "sample/1", "input": "1 2\n", "answer": "3\n"},
    {"name": "secret/a/1", "input": "40 2\n", "answer": "42\n"},
    {"name": "secret/b/1", "input": "-5 5\n", "answer": "0\n"},
]


def iso(delta: timedelta) -> str:
    return (datetime.now(UTC) + delta).isoformat()


async def classroom(stack: Stack) -> tuple[httpx.AsyncClient, dict[str, Any]]:
    teacher = await stack.user("staff", name="Ms Teacher")
    resp = await teacher.post("/api/v1/classes", json={"name": "CS 101", "description": "Intro"})
    assert resp.status_code == 201, resp.text
    return teacher, resp.json()


async def student_in(stack: Stack, cls: dict[str, Any], name: str = "Student") -> httpx.AsyncClient:
    student = await stack.user(name=name)
    resp = await student.post("/api/v1/classes/join", json={"code": cls["join_code"].lower()})
    assert resp.status_code == 200 and resp.json()["my_role"] == "student", resp.text
    assert resp.json()["join_code"] is None, "students never see the join code"
    return student


async def assignment(
    teacher: httpx.AsyncClient,
    cls: dict[str, Any],
    *,
    opens: timedelta = timedelta(hours=-1),
    due: timedelta = timedelta(days=1),
    policy: str = "penalty",
    problems: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    body = {
        "title": f"Week {policy}",
        "opens_at": iso(opens),
        "due_at": iso(due),
        "late_policy": policy,
        "penalty_percent": 20,
        "problems": problems or [{"problem": "sum", "points": 50}],
    }
    resp = await teacher.post(f"/api/v1/classes/{cls['id']}/assignments", json=body)
    assert resp.status_code == 201, resp.text
    return resp.json()


async def submit(
    stack: Stack, client: httpx.AsyncClient, a: dict[str, Any], source: str, problem: str = "sum"
) -> httpx.Response:
    resp = await client.post(
        "/api/v1/submissions",
        json={
            "problem": problem,
            "language": "python3",
            "source": source,
            "context": "assignment",
            "context_id": a["id"],
        },
    )
    if resp.status_code == 202:
        await stack.verdict(resp.json()["id"], client)
    return resp


async def test_members_see_open_assignments_and_outsiders_see_nothing(stack: Stack) -> None:
    await make_problem(stack)
    await make_problem(stack, "hidden-one", visibility="private")
    teacher, cls = await classroom(stack)
    student = await student_in(stack, cls)
    outsider = await stack.user(name="Outsider")
    week = await assignment(
        teacher,
        cls,
        problems=[{"problem": "sum", "points": 50}, {"problem": "hidden-one", "points": 50}],
    )
    await assignment(teacher, cls, opens=timedelta(days=2), due=timedelta(days=3), policy="accept")

    mine = (await student.get(f"/api/v1/classes/{cls['id']}/assignments")).json()
    assert [a["id"] for a in mine] == [week["id"]], "an assignment that has not opened is hidden"
    assert mine[0]["status"] == "open" and mine[0]["total_points"] == 100
    assert [a["id"] for a in (await student.get("/api/v1/my/assignments")).json()] == [week["id"]]
    assert len((await teacher.get(f"/api/v1/classes/{cls['id']}/assignments")).json()) == 2

    # A private problem is readable through the assignment, by members only.
    assert (
        await student.get(f"/api/v1/assignments/{week['id']}/problems/hidden-one")
    ).status_code == 200
    assert (
        await outsider.get(f"/api/v1/assignments/{week['id']}/problems/hidden-one")
    ).status_code == 404
    assert (await outsider.get(f"/api/v1/classes/{cls['id']}")).status_code == 404
    assert (await outsider.get(f"/api/v1/classes/{cls['id']}/assignments")).status_code == 404

    assert (await submit(stack, student, week, AC)).status_code == 202
    refused = await submit(stack, outsider, week, AC)
    assert refused.status_code == 403 and refused.json()["error"]["code"] == "not_a_member"
    # A problem that is not part of the assignment cannot be submitted under it.
    await make_problem(stack, "other")
    assert (await submit(stack, student, week, AC, problem="other")).status_code == 404

    # Teachers see their students' submissions; other students do not.
    sid = (await student.get("/api/v1/submissions")).json()["items"][0]["id"]
    assert (await teacher.get(f"/api/v1/submissions/{sid}")).status_code == 200
    classmate = await student_in(stack, cls, "Classmate")
    assert (await classmate.get(f"/api/v1/submissions/{sid}")).status_code == 404


async def test_late_work_follows_the_policy(stack: Stack) -> None:
    await make_problem(stack)
    teacher, cls = await classroom(stack)
    student = await student_in(stack, cls)
    past = {"opens": timedelta(days=-3), "due": timedelta(hours=-1)}
    penalty = await assignment(teacher, cls, policy="penalty", **past)
    accept = await assignment(teacher, cls, policy="accept", **past)
    refuse = await assignment(teacher, cls, policy="refuse", **past)

    statuses = {
        a["id"]: a["status"]
        for a in (await student.get(f"/api/v1/classes/{cls['id']}/assignments")).json()
    }
    assert statuses == {penalty["id"]: "late", accept["id"]: "late", refuse["id"]: "closed"}

    assert (await submit(stack, student, penalty, AC)).status_code == 202
    assert (await submit(stack, student, accept, AC)).status_code == 202
    closed = await submit(stack, student, refuse, AC)
    assert closed.status_code == 403 and closed.json()["error"]["code"] == "assignment_closed"

    subs = (await student.get("/api/v1/submissions")).json()["items"]
    assert len(subs) == 2 and all(s["late"] for s in subs)

    book = (await teacher.get(f"/api/v1/assignments/{penalty['id']}/gradebook")).json()
    cell = book["rows"][0]["cells"][0]
    assert cell["score"] == 40 and cell["late"], "50 points minus the 20% late penalty"
    book = (await teacher.get(f"/api/v1/assignments/{accept['id']}/gradebook")).json()
    assert book["rows"][0]["cells"][0]["score"] == 50 and book["rows"][0]["cells"][0]["late"]

    # An extension reopens a refusing assignment for that one student, on time.
    student_id = book["rows"][0]["user_id"]
    resp = await teacher.put(
        f"/api/v1/assignments/{refuse['id']}/extensions",
        json={"user_id": student_id, "due_at": iso(timedelta(days=1))},
    )
    assert resp.status_code == 204, resp.text
    assert (await submit(stack, student, refuse, AC)).status_code == 202
    latest = (await student.get("/api/v1/submissions")).json()["items"][0]
    assert latest["context_id"] == refuse["id"] and not latest["late"]
    other = await student_in(stack, cls, "No extension")
    assert (await submit(stack, other, refuse, AC)).status_code == 403


async def test_the_gradebook_keeps_the_best_mark_and_exports_csv(stack: Stack) -> None:
    await make_problem(
        stack,
        "parts",
        tests=TWO_GROUPS,
        groups=[{"name": "a", "points": 40}, {"name": "b", "points": 60}],
    )
    teacher, cls = await classroom(stack)
    ada = await student_in(stack, cls, "Ada")
    await student_in(stack, cls, "=cmd|' /C calc'!A0")
    week = await assignment(teacher, cls, problems=[{"problem": "parts", "points": 10}])
    await submit(stack, ada, week, AC + " #SCORE:40", problem="parts")
    await submit(stack, ada, week, AC + " #VERDICT:CE", problem="parts")
    book = (await teacher.get(f"/api/v1/assignments/{week['id']}/gradebook")).json()
    rows = {r["name"]: r for r in book["rows"]}
    assert rows["Ada"]["cells"][0] == {
        "problem_id": book["problems"][0]["id"],
        "score": 4.0,
        "late": False,
        "attempts": 2,
    }
    assert rows["Ada"]["total"] == 4.0
    await submit(stack, ada, week, AC, problem="parts")
    book = (await teacher.get(f"/api/v1/assignments/{week['id']}/gradebook")).json()
    assert {r["name"]: r["total"] for r in book["rows"]}["Ada"] == 10.0
    assert next(r for r in book["rows"] if r["name"] != "Ada")["cells"][0]["score"] is None

    mine = (await ada.get(f"/api/v1/assignments/{week['id']}")).json()
    assert mine["my_total"] == 10.0 and mine["problems"][0]["my_verdict"] == "AC"

    resp = await teacher.get(f"/api/v1/assignments/{week['id']}/gradebook.csv")
    assert resp.status_code == 200 and resp.headers["content-type"].startswith("text/csv")
    assert "attachment" in resp.headers["content-disposition"]
    table = list(csv.reader(io.StringIO(resp.text)))
    assert table[0] == ["name", "email", "parts (10)", "total (10)"]
    names = [row[0] for row in table[1:]]
    assert "Ada" in names and any(n.startswith("'=") for n in names), (
        "formula cells are neutralised"
    )

    # Students cannot read the gradebook or change the class.
    assert (await ada.get(f"/api/v1/assignments/{week['id']}/gradebook")).status_code == 403
    assert (await ada.get(f"/api/v1/assignments/{week['id']}/gradebook.csv")).status_code == 403
    assert (await ada.post(f"/api/v1/classes/{cls['id']}/assignments", json={})).status_code in (
        403,
        422,
    )
    assert (await ada.post("/api/v1/classes", json={"name": "Mine"})).status_code == 403


async def test_roster_codes_and_teachers(stack: Stack) -> None:
    teacher, cls = await classroom(stack)
    student = await stack.user(name="Bea")
    bad = await student.post("/api/v1/classes/join", json={"code": "NOPE2345"})
    assert bad.status_code == 404 and bad.json()["error"]["code"] == "bad_join_code"
    await student.post("/api/v1/classes/join", json={"code": cls["join_code"]})
    again = await student.post("/api/v1/classes/join", json={"code": cls["join_code"]})
    assert again.status_code == 200
    roster = (await teacher.get(f"/api/v1/classes/{cls['id']}/members")).json()
    assert sorted(m["role"] for m in roster) == ["student", "teacher"]
    assert (await student.get(f"/api/v1/classes/{cls['id']}/members")).status_code == 403

    # A rotated code stops working for new students.
    rotated = (await teacher.post(f"/api/v1/classes/{cls['id']}/rotate-code")).json()
    assert rotated["join_code"] != cls["join_code"]
    late = await stack.user(name="Late")
    assert (
        await late.post("/api/v1/classes/join", json={"code": cls["join_code"]})
    ).status_code == 404

    # The last teacher cannot be removed; a student can leave.
    teacher_id = next(m["user_id"] for m in roster if m["role"] == "teacher")
    student_id = next(m["user_id"] for m in roster if m["role"] == "student")
    resp = await teacher.delete(f"/api/v1/classes/{cls['id']}/members/{teacher_id}")
    assert resp.status_code == 409 and resp.json()["error"]["code"] == "last_teacher"
    assert (
        await student.delete(f"/api/v1/classes/{cls['id']}/members/{student_id}")
    ).status_code == 204
    assert (await student.get(f"/api/v1/classes/{cls['id']}")).status_code == 404
    listed = (await student.get("/api/v1/classes")).json()
    assert listed == []
