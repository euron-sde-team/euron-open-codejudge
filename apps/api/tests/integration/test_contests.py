"""AC7: contests. ICPC penalties and IOI best scores on the live board, the freeze, the
contest window, registration, private contest problems, clarifications, and a board built
with a fixed number of queries."""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import pytest
from sqlalchemy import event

from tests.integration.conftest import Stack, make_problem

pytestmark = pytest.mark.asyncio

AC = "print(sum(map(int, input().split())))"
GROUPED = [
    {"name": "sample/1", "input": "1 2\n", "answer": "3\n"},
    {"name": "secret/g1/1", "input": "1 1\n", "answer": "2\n"},
    {"name": "secret/g2/1", "input": "2 2\n", "answer": "4\n"},
]


def iso(delta_minutes: float) -> str:
    return (datetime.now(UTC) + timedelta(minutes=delta_minutes)).isoformat()


async def make_contest(
    stack: Stack,
    slug: str,
    problems: list[str],
    *,
    fmt: str = "icpc",
    starts: float = -60,
    ends: float = 60,
    **extra: Any,
) -> dict[str, Any]:
    contest: dict[str, Any] = await stack.ok(
        "POST", "/api/v1/contests",
        {"slug": slug, "title": slug.title(), "format": fmt, "starts_at": iso(starts), "ends_at": iso(ends), **extra},
        status=201,
    )  # fmt: skip
    for p in problems:
        await stack.ok(
            "POST", f"/api/v1/contests/{contest['id']}/problems", {"problem": p}, status=201
        )
    return contest


async def contestant(stack: Stack, contest: dict[str, Any], name: str) -> httpx.AsyncClient:
    client = await stack.user(name=name)
    resp = await client.post(f"/api/v1/contests/{contest['slug']}/register")
    assert resp.status_code == 200, resp.text
    return client


async def submit(
    stack: Stack, client: httpx.AsyncClient, contest: dict[str, Any], problem: str, source: str
) -> dict[str, Any]:
    resp = await client.post(
        "/api/v1/submissions",
        json={
            "problem": problem,
            "language": "python3",
            "source": source,
            "context": "contest",
            "context_id": contest["id"],
        },
    )
    assert resp.status_code == 202, resp.text
    return await stack.verdict(resp.json()["id"], client)


def rows_by_name(board: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {r["name"]: r for r in board["rows"]}


async def test_icpc_ranks_by_solved_then_penalty(stack: Stack) -> None:
    await make_problem(stack, "alpha")
    await make_problem(stack, "beta")
    c = await make_contest(stack, "icpc-cup", ["alpha", "beta"])
    a, b, k = [await contestant(stack, c, n) for n in ("Ana", "Ben", "Cai")]
    await submit(stack, a, c, "alpha", AC)
    await submit(stack, b, c, "alpha", AC + " #VERDICT:WA")
    await submit(stack, b, c, "alpha", AC + " #VERDICT:CE")  # costs nothing
    await submit(stack, b, c, "alpha", AC)
    await submit(stack, k, c, "alpha", AC)
    board = await b.get(f"/api/v1/contests/{c['slug']}/scoreboard")
    rows = rows_by_name(board.json())
    assert rows["Ana"]["rank"] == rows["Cai"]["rank"] == 1 and rows["Ben"]["rank"] == 3
    assert rows["Ben"]["penalty"] - rows["Ana"]["penalty"] == 20
    assert rows["Ben"]["cells"][0]["attempts"] == 1
    # The cached board is invalidated by the next verdict.
    await submit(stack, k, c, "beta", AC)
    rows = rows_by_name((await b.get(f"/api/v1/contests/{c['slug']}/scoreboard")).json())
    assert rows["Cai"]["rank"] == 1 and rows["Cai"]["solved"] == 2 and rows["Ana"]["rank"] == 2


async def test_ioi_keeps_each_contestants_best_score(stack: Stack) -> None:
    groups = [{"name": "g1", "points": 40}, {"name": "g2", "points": 60}]
    await make_problem(stack, "subtasks", tests=GROUPED, groups=groups)
    c = await make_contest(stack, "ioi-open", ["subtasks"], fmt="ioi")
    ana, ben = await contestant(stack, c, "Ana"), await contestant(stack, c, "Ben")
    first = await submit(stack, ana, c, "subtasks", AC + " #SCORE:40")
    assert first["score"] == 40
    worse = await submit(stack, ana, c, "subtasks", AC + " #SCORE:0")
    assert worse["score"] == 0
    await submit(stack, ben, c, "subtasks", AC)
    rows = rows_by_name((await ana.get(f"/api/v1/contests/{c['slug']}/scoreboard")).json())
    assert rows["Ana"]["score"] == 40 and rows["Ben"]["score"] == 100
    assert rows["Ben"]["rank"] == 1 and rows["Ana"]["rank"] == 2


async def test_the_freeze_hides_later_verdicts_from_contestants_until_unfrozen(
    stack: Stack,
) -> None:
    await make_problem(stack, "frost")
    c = await make_contest(stack, "frozen-cup", ["frost"])
    ana, ben = await contestant(stack, c, "Ana"), await contestant(stack, c, "Ben")
    await submit(stack, ana, c, "frost", AC)
    await stack.ok("PATCH", f"/api/v1/contests/{c['id']}", {"freeze_at": iso(0)})
    await submit(stack, ben, c, "frost", AC)
    seen = (await ana.get(f"/api/v1/contests/{c['slug']}/scoreboard")).json()
    rows = rows_by_name(seen)
    assert seen["frozen"] and rows["Ana"]["solved"] == 1
    assert rows["Ben"]["solved"] == 0 and rows["Ben"]["cells"][0]["pending"] == 1
    staff = rows_by_name(await stack.ok("GET", f"/api/v1/contests/{c['slug']}/scoreboard"))
    assert staff["Ben"]["solved"] == 1
    # Unfreezing needs the contest to be over.
    early = await stack.client.post(f"/api/v1/contests/{c['id']}/unfreeze")
    assert early.status_code == 400
    await stack.ok("PATCH", f"/api/v1/contests/{c['id']}", {"ends_at": iso(0.01)})
    await asyncio.sleep(1.0)
    await stack.ok("POST", f"/api/v1/contests/{c['id']}/unfreeze")
    after = (await ana.get(f"/api/v1/contests/{c['slug']}/scoreboard")).json()
    assert not after["frozen"] and rows_by_name(after)["Ben"]["solved"] == 1


async def test_submissions_outside_the_window_or_from_outsiders_are_refused(stack: Stack) -> None:
    await make_problem(stack, "window")
    await make_problem(stack, "elsewhere")
    soon = await make_contest(stack, "not-yet", ["window"], starts=30, ends=90)
    over = await make_contest(stack, "all-over", ["window"], starts=-90, ends=-30)
    live = await make_contest(stack, "on-now", ["window"])
    student = await stack.user()
    await student.post(f"/api/v1/contests/{soon['slug']}/register")
    payload = {"problem": "window", "language": "python3", "source": AC, "context": "contest"}
    resp = await student.post("/api/v1/submissions", json={**payload, "context_id": soon["id"]})
    assert resp.status_code == 403 and resp.json()["error"]["code"] == "contest_not_running"
    assert "not started" in resp.json()["error"]["message"]
    reg = await student.post(f"/api/v1/contests/{over['slug']}/register")
    assert reg.status_code == 403
    resp = await student.post("/api/v1/submissions", json={**payload, "context_id": over["id"]})
    assert resp.status_code == 403
    resp = await student.post("/api/v1/submissions", json={**payload, "context_id": live["id"]})
    assert resp.status_code == 403 and resp.json()["error"]["code"] == "not_registered"
    await student.post(f"/api/v1/contests/{live['slug']}/register")
    resp = await student.post(
        "/api/v1/submissions", json={**payload, "problem": "elsewhere", "context_id": live["id"]}
    )
    assert resp.status_code == 404
    resp = await student.post("/api/v1/submissions", json={**payload, "context_id": live["id"]})
    assert resp.status_code == 202
    # Before the start nobody but staff sees the problem set or the board.
    detail = (await student.get(f"/api/v1/contests/{soon['slug']}")).json()
    assert detail["problems"] == [] and detail["phase"] == "upcoming"
    assert (await student.get(f"/api/v1/contests/{soon['slug']}/scoreboard")).status_code == 403


async def test_a_private_problem_is_open_to_participants_only_through_the_contest(
    stack: Stack,
) -> None:
    await make_problem(stack, "secret-sauce", visibility="private")
    c = await make_contest(stack, "private-cup", ["secret-sauce"])
    member = await contestant(stack, c, "Ana")
    outsider = await stack.user()
    assert (await member.get("/api/v1/problems/secret-sauce")).status_code == 404
    got = await member.get(f"/api/v1/contests/{c['slug']}/problems/A")
    assert got.status_code == 200, got.text
    body = got.json()
    assert body["slug"] == "secret-sauce" and [s["name"] for s in body["samples"]] == ["sample/1"]
    assert "40 2" not in got.text, "hidden tests must never be in the problem view"
    assert (await outsider.get(f"/api/v1/contests/{c['slug']}/problems/A")).status_code == 403
    done = await submit(stack, member, c, "secret-sauce", AC)
    assert done["verdict"] == "AC"
    # Another contestant can never read someone else's code.
    other = await contestant(stack, c, "Ben")
    assert (await other.get(f"/api/v1/submissions/{done['id']}")).status_code == 404


async def test_invite_only_contests_need_the_join_code(stack: Stack) -> None:
    await make_problem(stack, "invite-prob")
    c = await make_contest(
        stack, "by-invite", ["invite-prob"], registration="invite", visibility="private"
    )
    student = await stack.user()
    assert (await student.get(f"/api/v1/contests/{c['slug']}")).status_code == 404
    assert c["join_code"]
    assert (
        await student.post("/api/v1/contests/join", json={"code": "wrong-code"})
    ).status_code == 404
    joined = await student.post("/api/v1/contests/join", json={"code": c["join_code"]})
    assert (
        joined.status_code == 200
        and joined.json()["registered"]
        and joined.json()["join_code"] is None
    )
    listed = {x["slug"] for x in (await student.get("/api/v1/contests")).json()}
    assert "by-invite" in listed


async def test_clarifications_are_private_until_answered_publicly(stack: Stack) -> None:
    await make_problem(stack, "clar")
    c = await make_contest(stack, "clar-cup", ["clar"])
    ana, ben = await contestant(stack, c, "Ana"), await contestant(stack, c, "Ben")
    asked = await ana.post(
        f"/api/v1/contests/{c['slug']}/clarifications",
        json={"question": "Can n be 0?", "problem_label": "A"},
    )
    assert asked.status_code == 201 and asked.json()["mine"]
    assert (await ben.get(f"/api/v1/contests/{c['slug']}/clarifications")).json() == []
    staff_view = await stack.ok("GET", f"/api/v1/contests/{c['slug']}/clarifications")
    assert staff_view[0]["asked_by_name"] == "Ana"
    await stack.ok(
        "POST",
        f"/api/v1/contests/{c['id']}/clarifications/{asked.json()['id']}/answer",
        {"answer": "No, n >= 1.", "public": True},
    )
    await stack.ok(
        "POST",
        f"/api/v1/contests/{c['id']}/announcements",
        {"answer": "Problem A limits fixed."},
        status=201,
    )
    seen = (await ben.get(f"/api/v1/contests/{c['slug']}/clarifications")).json()
    assert {x["answer"] for x in seen} == {"No, n >= 1.", "Problem A limits fixed."}
    assert all(x["asked_by_name"] is None for x in seen)
    outsider = await stack.user()
    resp = await outsider.post(
        f"/api/v1/contests/{c['slug']}/clarifications", json={"question": "hi"}
    )
    assert resp.status_code == 403


async def test_the_board_takes_the_same_number_of_queries_for_any_crowd(stack: Stack) -> None:
    """No N+1: three queries whether 2 or 12 people took part."""
    from codejudge.contests import service
    from codejudge.contests.models import Contest
    from codejudge.core.db import Database

    await make_problem(stack, "crowd")
    small = await make_contest(stack, "small-crowd", ["crowd"])
    large = await make_contest(stack, "large-crowd", ["crowd"])
    for i in range(2):
        await submit(stack, await contestant(stack, small, f"S{i}"), small, "crowd", AC)
    for i in range(12):
        await submit(
            stack,
            await contestant(stack, large, f"L{i}"),
            large,
            "crowd",
            AC + (" #VERDICT:WA" if i % 2 else ""),
        )
    db = Database(stack.settings.database_url, pool_size=1, max_overflow=0)
    counts = []
    statements: list[str] = []

    def count(*_args: Any) -> None:
        statements.append("q")

    event.listen(db.engine.sync_engine, "before_cursor_execute", count)
    try:
        for ref in (small["id"], large["id"]):
            async with db.sessionmaker() as session:
                c = await session.get(Contest, uuid.UUID(ref))
                assert c is not None
                statements.clear()
                board = await service.board(session, c, frozen=False)
                counts.append(len(statements))
        assert len(board.rows) == 12
    finally:
        event.remove(db.engine.sync_engine, "before_cursor_execute", count)
        await db.dispose()
    assert counts[0] == counts[1] == 3, counts


async def test_staff_see_every_contest_submission(stack: Stack) -> None:
    await make_problem(stack, "audit-me")
    c = await make_contest(stack, "staff-view", ["audit-me"])
    ana = await contestant(stack, c, "Ana")
    await submit(stack, ana, c, "audit-me", AC)
    page = await stack.ok("GET", f"/api/v1/contests/{c['id']}/submissions")
    assert (
        page["total"] == 1
        and page["items"][0]["user_name"] == "Ana"
        and page["items"][0]["source"] is None
    )
    assert (await ana.get(f"/api/v1/contests/{c['id']}/submissions")).status_code == 403
    mine = (await ana.get(f"/api/v1/contests/{c['slug']}/me")).json()
    assert mine["registered"] and mine["row"]["solved"] == 1


async def test_reordering_relabels_problems(stack: Stack) -> None:
    await make_problem(stack, "first-p")
    await make_problem(stack, "second-p")
    c = await make_contest(stack, "order-cup", ["first-p", "second-p"])
    order = await stack.ok(
        "PUT", f"/api/v1/contests/{c['id']}/problems/order", {"labels": ["B", "A"]}
    )
    assert [(p["label"], p["slug"]) for p in order] == [("A", "second-p"), ("B", "first-p")]
    bad = await stack.client.put(
        f"/api/v1/contests/{c['id']}/problems/order", json={"labels": ["A"]}
    )
    assert bad.status_code == 400
