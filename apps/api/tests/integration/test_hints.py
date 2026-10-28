"""AC11: AI hints are optional. Off means no LLM request at all; on, they never carry hidden
test data and are never available in contests or assessments."""

from __future__ import annotations

from typing import Any

import httpx
import pytest

from tests.integration.conftest import Stack, make_problem

pytestmark = pytest.mark.asyncio

AC = "print(sum(map(int, input().split())))"


async def mock(stack: Stack, path: str, body: dict[str, Any] | None = None) -> Any:
    async with httpx.AsyncClient(base_url=stack.mock_ai_url) as c:
        resp = await (c.post(path, json=body or {}) if path.startswith("/admin") else c.get(path))
        return resp.json()


async def enable(stack: Stack, **extra: Any) -> None:
    await stack.ok(
        "PATCH",
        "/api/v1/org/settings",
        {
            "ai_enabled": True,
            "ai_base_url": stack.mock_ai_url + "/v1",
            "ai_model": "mock-tutor",
            **extra,
        },
    )


async def ask(client: httpx.AsyncClient, **extra: Any) -> httpx.Response:
    body = {"problem": "sum", "language": "python3", "source": AC, **extra}
    return await client.post("/api/v1/hints", json=body)


async def test_with_ai_off_no_request_is_ever_made(stack: Stack) -> None:
    await mock(stack, "/admin/reset")
    await make_problem(stack)
    student = await stack.user()
    resp = await ask(student)
    assert resp.status_code == 403 and resp.json()["error"]["code"] == "ai_disabled"
    status = (await student.get("/api/v1/hints/status", params={"problem": "sum"})).json()
    assert status["available"] is False and status["reason"]
    # Even with an endpoint configured, hints stay off until an admin turns them on.
    await stack.ok(
        "PATCH", "/api/v1/org/settings", {"ai_base_url": stack.mock_ai_url + "/v1", "ai_model": "m"}
    )
    assert (await ask(student)).status_code == 403
    assert (await mock(stack, "/stats"))["requests"] == 0


async def test_a_hint_never_carries_hidden_test_data(stack: Stack) -> None:
    await mock(stack, "/admin/reset")
    await make_problem(stack)
    await enable(stack)
    student = await stack.user()
    resp = await student.post(
        "/api/v1/submissions",
        json={"problem": "sum", "language": "python3", "source": AC + "  #VERDICT:WA"},
    )
    wrong = await stack.verdict(resp.json()["id"], student)
    assert wrong["verdict"] == "WA"
    resp = await ask(student, question="Why is my answer wrong?")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["hint"] and body["model"] == "mock-tutor" and body["used"] == 1
    sent = (await mock(stack, "/stats"))["last"]
    prompt = " ".join(m["content"] for m in sent["messages"])
    assert "WA" in prompt and "secret/1" in prompt and "Why is my answer wrong?" in prompt
    assert "1 2" in prompt  # the public sample
    for hidden in ("40 2", "42", "-5 5"):
        assert hidden not in prompt, hidden


async def test_contests_and_assessments_never_get_hints(stack: Stack) -> None:
    await mock(stack, "/admin/reset")
    await make_problem(stack)
    await enable(stack, ai_allowed_in_assignments=True)
    student = await stack.user()
    for context in ("contest", "assessment"):
        resp = await ask(student, context=context)
        assert resp.status_code == 403 and resp.json()["error"]["code"] == "ai_not_allowed", context
    assert (await mock(stack, "/stats"))["requests"] == 0


async def test_assignments_need_the_teachers_permission(stack: Stack) -> None:
    await mock(stack, "/admin/reset")
    await make_problem(stack)
    await enable(stack)
    student = await stack.user()
    resp = await ask(student, context="assignment")
    assert resp.status_code == 403 and resp.json()["error"]["code"] == "ai_not_allowed"
    assert (await mock(stack, "/stats"))["requests"] == 0


async def test_the_cap_holds_and_failed_calls_do_not_use_it(stack: Stack) -> None:
    await mock(stack, "/admin/reset")
    await make_problem(stack)
    await enable(stack, ai_max_hints_per_problem=2)
    student = await stack.user()
    await mock(stack, "/admin/reset", {"fail": True})
    failed = await ask(student)
    assert failed.status_code == 502 and failed.json()["error"]["code"] == "ai_unavailable"
    assert "Settings" in failed.json()["error"]["message"]
    await mock(stack, "/admin/reset")
    assert (await ask(student)).json()["remaining"] == 1
    assert (await ask(student)).json()["remaining"] == 0
    capped = await ask(student)
    assert capped.status_code == 429 and capped.json()["error"]["code"] == "hint_limit"
    assert (await mock(stack, "/stats"))["requests"] == 2
    status = (await student.get("/api/v1/hints/status", params={"problem": "sum"})).json()
    assert status == {
        "available": False,
        "reason": status["reason"],
        "used": 2,
        "limit": 2,
        "remaining": 0,
    }


async def test_no_hints_for_problems_you_cannot_open(stack: Stack) -> None:
    await mock(stack, "/admin/reset")
    await make_problem(stack, "hidden-one", publish=False)
    await enable(stack)
    student = await stack.user()
    resp = await student.post(
        "/api/v1/hints", json={"problem": "hidden-one", "language": "python3", "source": AC}
    )
    assert resp.status_code == 404
    assert (await mock(stack, "/stats"))["requests"] == 0
