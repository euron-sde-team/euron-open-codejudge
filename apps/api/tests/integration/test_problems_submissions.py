"""The core flow: problems, the publish gate, submissions, verdicts and their ingestion."""

from __future__ import annotations

import io
import zipfile
from typing import Any

import httpx
import pytest

from codejudge.core.contract import JudgeJob, JudgeResult, Verdict
from tests.integration.conftest import JUDGE_TOKEN, SUM_TESTS, Stack, fake_result, make_problem

pytestmark = pytest.mark.asyncio

AC = "print(sum(map(int, input().split())))"


async def submit(
    stack: Stack, client: httpx.AsyncClient, problem: str, source: str, **extra: Any
) -> dict[str, Any]:
    resp = await client.post(
        "/api/v1/submissions",
        json={"problem": problem, "language": "python3", "source": source, **extra},
    )
    assert resp.status_code == 202, resp.text
    return await stack.verdict(resp.json()["id"], client)


async def test_a_correct_and_a_wrong_solution_get_their_verdicts(stack: Stack) -> None:
    await make_problem(stack)
    student = await stack.user()
    ok = await submit(stack, student, "sum", AC)
    assert ok["verdict"] == "AC" and ok["score"] == ok["max_score"] == 100
    wrong = await submit(stack, student, "sum", AC + "  #VERDICT:WA")
    assert wrong["verdict"] == "WA" and wrong["score"] == 0
    problem = await stack.ok("GET", "/api/v1/problems/sum")
    assert (
        problem["submissions_count"] == 2
        and problem["accepted_count"] == 1
        and problem["solvers_count"] == 1
    )


async def test_a_problem_cannot_be_published_until_its_reference_solution_passes(
    stack: Stack,
) -> None:
    p = await make_problem(stack, "gate", publish=False)
    resp = await stack.client.post(f"/api/v1/problems/{p['id']}/publish")
    assert resp.status_code == 400 and resp.json()["error"]["code"] == "not_publishable"
    # A reference solution that should pass but does not keeps it blocked.
    await stack.ok(
        "POST",
        f"/api/v1/problems/{p['id']}/references",
        {"name": "bad", "language": "python3", "source": "print(0) #VERDICT:WA"},
        status=201,
    )
    await stack.ok("POST", f"/api/v1/problems/{p['id']}/references/judge")
    for _ in range(100):
        admin = await stack.ok("GET", f"/api/v1/problems/{p['id']}/admin")
        if not any("judge the reference" in b for b in admin["publish_blockers"]):
            break
        await __import__("asyncio").sleep(0.1)
    assert any("got WA, expected AC" in b for b in admin["publish_blockers"]), admin[
        "publish_blockers"
    ]


async def test_students_never_see_hidden_tests(stack: Stack) -> None:
    p = await make_problem(stack)
    student = await stack.user()
    problem = (await student.get("/api/v1/problems/sum")).json()
    assert [s["name"] for s in problem["samples"]] == ["sample/1"]
    visible = str(problem["samples"]) + problem["statement_md"]
    assert "40 2" not in visible and "42" not in visible
    assert "tests" not in problem and "versions" not in problem
    for path in (
        f"/api/v1/problems/{p['id']}/admin",
        f"/api/v1/problems/{p['id']}/tests/secret/1",
        f"/api/v1/problems/{p['id']}/export",
    ):
        assert (await student.get(path)).status_code == 403, path
    wrong = await submit(stack, student, "sum", AC + "  #VERDICT:WA")
    hidden = [t for t in wrong["tests"] if t["name"].startswith("secret/")]
    assert hidden and all(t["output"] is None and t["message"] is None for t in hidden)


async def test_drafts_and_private_problems_are_hidden_from_students(stack: Stack) -> None:
    await make_problem(stack, "draft-one", publish=False)
    await make_problem(stack, "private-one", visibility="private")
    student = await stack.user()
    listed = {p["slug"] for p in (await student.get("/api/v1/problems")).json()["items"]}
    assert "draft-one" not in listed and "private-one" not in listed
    assert (await student.get("/api/v1/problems/draft-one")).status_code == 404
    resp = await student.post(
        "/api/v1/submissions", json={"problem": "private-one", "language": "python3", "source": AC}
    )
    assert resp.status_code == 404


async def test_runs_on_samples_and_custom_input_are_not_counted(stack: Stack) -> None:
    await make_problem(stack)
    student = await stack.user()
    resp = await student.post(
        "/api/v1/runs", json={"problem": "sum", "language": "python3", "source": AC}
    )
    run = await stack.verdict(resp.json()["id"], student)
    assert run["context"] == "run" and [t["name"] for t in run["tests"]] == ["sample/1"]
    resp = await student.post(
        "/api/v1/runs", json={"problem": "sum", "language": "python3", "source": AC, "input": "7 8"}
    )
    custom = await stack.verdict(resp.json()["id"], student)
    assert custom["run_output"] == "echo: 7 8"
    problem = await stack.ok("GET", "/api/v1/problems/sum")
    assert problem["submissions_count"] == 0
    mine = (await student.get("/api/v1/submissions")).json()
    assert mine["total"] == 0


async def test_a_result_is_applied_once_and_a_stale_one_is_ignored(stack: Stack) -> None:
    """AC5 at the API: retries and redeliveries never apply a verdict twice, and after a
    rejudge the old job's late result is refused."""
    await make_problem(stack)
    stack.judge.paused.set()
    student = await stack.user()
    resp = await student.post(
        "/api/v1/submissions", json={"problem": "sum", "language": "python3", "source": AC}
    )
    sid = resp.json()["id"]
    first = await stack.client.get(f"/api/v1/submissions/{sid}")
    job = await _job_for(stack, sid)
    internal = httpx.AsyncClient(
        base_url=stack.api_url,
        headers={"authorization": f"Bearer {JUDGE_TOKEN}", "content-type": "application/json"},
    )
    result = fake_result(job)
    assert (
        await internal.post("/internal/judge/results", content=result.model_dump_json())
    ).status_code == 200
    assert (
        await internal.post("/internal/judge/results", content=result.model_dump_json())
    ).status_code == 409
    # Rejudge: a new job; the old job's result is now stale and refused.
    await stack.ok("POST", "/api/v1/submissions/rejudge", {"ids": [sid]})
    stale = result.model_copy(update={"verdict": Verdict.WA, "attempt": 2})
    assert (
        await internal.post("/internal/judge/results", content=stale.model_dump_json())
    ).status_code == 409
    stack.judge.paused.clear()
    final = await stack.verdict(sid)
    assert final["verdict"] == "AC" and first.status_code == 200
    problem = await stack.ok("GET", "/api/v1/problems/sum")
    assert problem["accepted_count"] == 1, "a rejudge must not count the same solve twice"
    await internal.aclose()


async def test_the_internal_endpoints_need_the_judge_token(stack: Stack) -> None:
    async with stack.anonymous() as anon:
        assert (await anon.post("/internal/judge/results", content="{}")).status_code == 401
        assert (await anon.get("/internal/judge/packages/" + "0" * 64)).status_code == 401
    student = await stack.user()
    assert (await student.get("/internal/judge/packages/" + "0" * 64)).status_code == 401


async def test_a_package_exports_and_imports_unchanged(stack: Stack) -> None:
    """AC6: export as a Kattis package, import it back: same tests, groups and solution."""
    p = await make_problem(stack, "roundtrip", groups=[{"name": "secret", "points": 100}])
    resp = await stack.client.get(f"/api/v1/problems/{p['id']}/export")
    assert resp.status_code == 200
    names = set(zipfile.ZipFile(io.BytesIO(resp.content)).namelist())
    assert {
        "problem.yaml",
        "problem_statement/problem.md",
        "data/sample/1.in",
        "data/secret/2.ans",
    } <= names
    assert any(n.startswith("submissions/accepted/") for n in names)
    imported = await stack.client.post(
        "/api/v1/problems/import",
        files={"file": ("roundtrip.zip", resp.content, "application/zip")},
        data={"slug": "roundtrip-copy"},
    )
    assert imported.status_code == 201, imported.text
    body = imported.json()
    assert body["tests"] == len(SUM_TESTS) and body["references"] == 1
    original = await stack.ok("GET", f"/api/v1/problems/{p['id']}/admin")
    copy = await stack.ok("GET", f"/api/v1/problems/{body['problem']['id']}/admin")
    assert copy["versions"][0]["package_sha256"] == original["versions"][0]["package_sha256"]
    assert copy["statement_md"] == original["statement_md"]


async def test_a_hostile_package_is_refused(stack: Stack) -> None:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("../escape.in", "x")
        z.writestr("data/secret/1.in", "1")
        z.writestr("data/secret/1.ans", "1")
    resp = await stack.client.post(
        "/api/v1/problems/import", files={"file": ("bad.zip", buf.getvalue(), "application/zip")}
    )
    assert resp.status_code == 400 and resp.json()["error"]["code"] == "bad_package"


async def _job_for(stack: Stack, submission_id: str) -> JudgeJob:
    import redis.asyncio as aioredis

    from tests.integration.conftest import STREAM, TEST_REDIS

    r = aioredis.Redis.from_url(TEST_REDIS, decode_responses=True)
    for _, fields in await r.xrange(STREAM):
        job = JudgeJob.model_validate_json(fields["job"])
        if job.submission_id == submission_id:
            await r.aclose()
            return job
    await r.aclose()
    raise AssertionError("job not on the stream")


__all__ = ["JudgeResult"]


async def test_large_tests_upload_for_staff_but_not_anonymously(stack: Stack) -> None:
    """Packages are large: staff may send them past the general body limit; anonymous
    clients stay at the small limit."""
    p = await stack.ok("POST", "/api/v1/problems", {"slug": "big", "title": "Big"}, status=201)
    big = "1 " * 1_500_000
    tests = [
        {"name": "sample/1", "input": "1 1\n", "answer": "2\n"},
        {"name": "secret/1", "input": big, "answer": "3\n"},
    ]
    resp = await stack.client.post(f"/api/v1/problems/{p['id']}/versions", json={"tests": tests})
    assert resp.status_code == 201, resp.text[:300]
    # Refused before the body is read: a 413, or the connection closed while sending.
    async with stack.anonymous() as anon:
        try:
            resp = await anon.post(f"/api/v1/problems/{p['id']}/versions", json={"tests": tests})
            assert resp.status_code == 413
        except httpx.TransportError:
            pass


@pytest.mark.parametrize("settings_overrides", [{"submit_rpm": 2}])
async def test_submitting_too_fast_is_a_429_with_retry_after(stack: Stack) -> None:
    await make_problem(stack)
    student = await stack.user()
    body = {"problem": "sum", "language": "python3", "source": AC}
    codes = [(await student.post("/api/v1/submissions", json=body)) for _ in range(3)]
    assert [r.status_code for r in codes[:2]] == [202, 202]
    assert codes[2].status_code == 429 and int(codes[2].headers["retry-after"]) >= 1
    assert codes[2].json()["error"]["code"] == "rate_limited"
