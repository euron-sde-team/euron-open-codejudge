"""Analytics: the rollup is exact, survives rejudges unchanged, and ignores runs."""

from __future__ import annotations

from typing import Any

import httpx
import pytest

from tests.integration.conftest import Stack, make_problem

pytestmark = pytest.mark.asyncio

AC = "print(sum(map(int, input().split())))"


async def submit(stack: Stack, client: httpx.AsyncClient, source: str) -> dict[str, Any]:
    resp = await client.post(
        "/api/v1/submissions", json={"problem": "sum", "language": "python3", "source": source}
    )
    assert resp.status_code == 202, resp.text
    return await stack.verdict(resp.json()["id"], client)


async def seed(stack: Stack) -> tuple[httpx.AsyncClient, httpx.AsyncClient, list[str]]:
    await make_problem(stack)
    a, b = await stack.user(name="Ada"), await stack.user(name="Bob")
    ids = [
        (await submit(stack, a, AC + "  #VERDICT:WA"))["id"],
        (await submit(stack, a, AC))["id"],
        (await submit(stack, b, AC))["id"],
    ]
    return a, b, ids


async def test_the_overview_counts_judged_submissions(stack: Stack) -> None:
    a, _, _ = await seed(stack)
    await a.post("/api/v1/runs", json={"problem": "sum", "language": "python3", "source": AC})
    o = await stack.ok("GET", "/api/v1/analytics/overview")
    assert (o["submissions"], o["accepted"], o["acceptance"]) == (3, 2, 0.6667)
    assert o["verdicts"]["AC"] == 2 and o["verdicts"]["WA"] == 1
    assert o["daily"][-1]["submissions"] == 3 and len(o["daily"]) == 30
    assert o["top_problems"][0]["slug"] == "sum" and o["top_problems"][0]["submissions"] == 3
    assert o["by_difficulty"] == [
        {"difficulty": "medium", "submissions": 3, "accepted": 2, "acceptance": 0.6667}
    ]
    assert o["languages"] == [{"language": "python3", "submissions": 3, "accepted": 2}]
    assert o["active_users"] == 2


async def test_rejudging_changes_nothing(stack: Stack) -> None:
    _, _, ids = await seed(stack)
    before = await stack.ok("GET", "/api/v1/analytics/overview")
    await stack.ok("POST", "/api/v1/submissions/rejudge", {"ids": ids})
    for sid in ids:
        await stack.verdict(sid)
    after = await stack.ok("GET", "/api/v1/analytics/overview")
    assert after == before


async def test_problem_statistics(stack: Stack) -> None:
    await seed(stack)
    p = await stack.ok("GET", "/api/v1/analytics/problems/sum")
    assert (p["submissions"], p["accepted"], p["attempters"], p["solvers"]) == (3, 2, 2, 2)
    assert p["attempts_to_ac"] == {"1": 1, "2": 1, "3": 0, "4+": 0}
    assert p["median_attempts_to_ac"] == 1.5
    assert p["median_ac_time_ms"] == 12.0


async def test_students_see_only_their_own_progress(stack: Stack) -> None:
    a, b, _ = await seed(stack)
    mine = (await a.get("/api/v1/analytics/me")).json()
    assert (
        mine["solved"],
        mine["attempted"],
        mine["submissions"],
        mine["accepted_submissions"],
    ) == (1, 1, 2, 1)
    assert mine["solved_by_difficulty"]["medium"] == 1
    assert [r["verdict"] for r in mine["recent"]] == ["AC", "WA"]
    assert mine["activity"][-1] == {
        "day": mine["activity"][-1]["day"],
        "submissions": 2,
        "accepted": 1,
    }
    a_id = mine["user_id"]
    assert (await b.get(f"/api/v1/analytics/users/{a_id}")).status_code == 404
    assert (await b.get("/api/v1/analytics/overview")).status_code == 403
    assert (await stack.client.get(f"/api/v1/analytics/users/{a_id}")).json()["solved"] == 1


async def test_active_people_are_counted_once_across_problems_and_languages(stack: Stack) -> None:
    """One person on two problems in two languages is one active person, not four (each
    rollup row counts the people of one day, problem and language)."""
    await make_problem(stack)
    await make_problem(stack, "sum-two")
    student = await stack.user()
    for problem in ("sum", "sum-two"):
        for language in ("python3", "cpp17"):
            resp = await student.post(
                "/api/v1/submissions", json={"problem": problem, "language": language, "source": AC}
            )
            await stack.verdict(resp.json()["id"])
    o = await stack.ok("GET", "/api/v1/analytics/overview")
    assert o["submissions"] == 4 and o["active_users"] == 1
