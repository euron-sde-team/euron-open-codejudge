"""AC10 end to end: a disguised copy is flagged in a run, independent work is not."""

from __future__ import annotations

import httpx
import pytest

from codejudge.core.container import Container
from codejudge.plagiarism.service import process_next
from tests.integration.conftest import Stack, make_problem
from tests.unit.plagiarism.test_winnow import DISGUISED_PY, INDEPENDENT_PY, ORIGINAL_PY

pytestmark = pytest.mark.asyncio


async def submit(stack: Stack, client: httpx.AsyncClient, source: str) -> str:
    resp = await client.post(
        "/api/v1/submissions", json={"problem": "sum", "language": "python3", "source": source}
    )
    assert resp.status_code == 202, resp.text
    return str((await stack.verdict(resp.json()["id"], client))["id"])


async def work(stack: Stack) -> int:
    container = Container.build(stack.settings)
    try:
        return await process_next(container)
    finally:
        await container.close()


async def test_a_run_flags_the_copy_and_not_the_independent_solution(stack: Stack) -> None:
    await make_problem(stack)
    ada = await stack.user(name="Ada")
    bob = await stack.user(name="Bob")
    cy = await stack.user(name="Cy")
    original = await submit(stack, ada, ORIGINAL_PY)
    copy = await submit(stack, bob, DISGUISED_PY)
    await submit(stack, cy, INDEPENDENT_PY)

    run = await stack.ok(
        "POST", "/api/v1/plagiarism/runs", {"scope": "problem", "scope_id": "sum"}, status=202
    )
    assert run["status"] == "queued"
    assert await work(stack) == 1
    assert await work(stack) == 0  # nothing left to claim

    detail = await stack.ok("GET", f"/api/v1/plagiarism/runs/{run['id']}")
    assert detail["status"] == "done" and detail["documents"] == 3 and detail["comparisons"] == 3
    assert detail["flagged"] == 1 and len(detail["pairs"]) == 1
    pair = detail["pairs"][0]
    assert {pair["a"]["submission_id"], pair["b"]["submission_id"]} == {original, copy}
    assert {pair["a"]["author"], pair["b"]["author"]} == {"Ada", "Bob"}
    assert pair["similarity"] >= 0.5 and pair["a"]["ranges"] and pair["b"]["ranges"]

    full = await stack.ok("GET", f"/api/v1/plagiarism/pairs/{pair['id']}")
    assert {full["source_a"], full["source_b"]} == {ORIGINAL_PY, DISGUISED_PY}
    listed = await stack.ok(
        "GET", f"/api/v1/plagiarism/runs?scope=problem&scope_id={detail['scope_id']}"
    )
    assert [r["id"] for r in listed] == [run["id"]]


async def test_one_program_per_author_the_accepted_one(stack: Stack) -> None:
    await make_problem(stack)
    ada, bob = await stack.user(name="Ada"), await stack.user(name="Bob")
    await submit(stack, ada, INDEPENDENT_PY + "#VERDICT:WA")
    accepted = await submit(stack, ada, ORIGINAL_PY)
    await submit(stack, ada, INDEPENDENT_PY + "#VERDICT:WA")  # a later failure does not replace it
    await submit(stack, bob, DISGUISED_PY)
    run = await stack.ok(
        "POST", "/api/v1/plagiarism/runs", {"scope": "problem", "scope_id": "sum"}, status=202
    )
    await work(stack)
    detail = await stack.ok("GET", f"/api/v1/plagiarism/runs/{run['id']}")
    assert detail["documents"] == 2 and detail["flagged"] == 1
    assert accepted in {
        detail["pairs"][0]["a"]["submission_id"],
        detail["pairs"][0]["b"]["submission_id"],
    }


async def test_plagiarism_checks_are_staff_only(stack: Stack) -> None:
    await make_problem(stack)
    student = await stack.user()
    resp = await student.post(
        "/api/v1/plagiarism/runs", json={"scope": "problem", "scope_id": "sum"}
    )
    assert resp.status_code == 403
    assert (await student.get("/api/v1/plagiarism/runs")).status_code == 403
    bad = await stack.client.post(
        "/api/v1/plagiarism/runs", json={"scope": "contest", "scope_id": "nope"}
    )
    assert bad.status_code == 400 and bad.json()["error"]["code"] == "invalid_scope"
