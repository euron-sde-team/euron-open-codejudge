"""AC9: an invited candidate with no account takes a timed assessment; the interviewer gets
the report. Through the real API, with the invitation email read from the log backend."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from codejudge.assessments.service import token_hash
from codejudge.core import mail
from tests.integration.conftest import TEST_DB, Stack, make_problem

pytestmark = pytest.mark.asyncio

AC = "print(sum(map(int, input().split())))"


async def assessment(stack: Stack, **extra: Any) -> dict[str, Any]:
    body = {
        "title": "Backend engineer screen",
        "instructions_md": "Solve both.",
        "duration_minutes": 45,
        "problems": [{"problem": "sum", "points": 60}, {"problem": "secret-sum", "points": 40}],
        **extra,
    }
    return await stack.ok("POST", "/api/v1/assessments", body, status=201)


async def invite(
    stack: Stack, a: dict[str, Any], email: str = "cand@example.test"
) -> tuple[dict[str, Any], str]:
    """The invitation and the raw token from the link in its email."""
    before = len(mail.OUTBOX)
    result = await stack.ok(
        "POST",
        f"/api/v1/assessments/{a['id']}/invitations",
        {"candidates": [{"email": email, "name": "Cand"}]},
        status=201,
    )
    assert result["failed"] == [] and len(mail.OUTBOX) == before + 1
    message = mail.OUTBOX[-1]
    assert message.to == email
    url = next(line for line in message.text.splitlines() if "/take/" in line)
    return result["invitations"][0], url.rsplit("/take/", 1)[1].strip()


def candidate(stack: Stack, token: str) -> httpx.AsyncClient:
    """A browser with no account: only the invitation token."""
    return httpx.AsyncClient(
        base_url=stack.api_url, timeout=30, headers={"x-codejudge-candidate": token}
    )


async def set_deadline(invitation_id: str, when: datetime) -> None:
    engine = create_async_engine(TEST_DB)
    async with engine.begin() as conn:
        await conn.execute(
            text("UPDATE invitations SET deadline_at = :d WHERE id = :i"),
            {"d": when, "i": invitation_id},
        )
    await engine.dispose()


async def submit(
    client: httpx.AsyncClient, invitation_id: str, problem: str, source: str = AC
) -> httpx.Response:
    return await client.post(
        "/api/v1/submissions",
        json={
            "problem": problem,
            "language": "python3",
            "source": source,
            "context": "assessment",
            "context_id": invitation_id,
        },
    )


async def problems_ready(stack: Stack) -> None:
    await make_problem(stack)
    await make_problem(stack, "secret-sum", visibility="private")


async def test_a_candidate_takes_a_timed_assessment_and_the_interviewer_gets_the_report(
    stack: Stack,
) -> None:
    await problems_ready(stack)
    a = await assessment(stack)
    inv, token = await invite(stack, a)
    assert inv["status"] == "invited" and inv["sent_at"]

    # Only a keyed hash of the token is stored.
    engine = create_async_engine(TEST_DB)
    async with engine.connect() as conn:
        stored = (
            await conn.execute(
                text("SELECT token_hash FROM invitations WHERE id = :i"), {"i": inv["id"]}
            )
        ).scalar_one()
        assert token not in str((await conn.execute(text("SELECT * FROM invitations"))).all())
    await engine.dispose()
    assert stored == token_hash(stack.settings, token)

    # Before opening the link the header is refused; opening it starts the timer.
    cand = candidate(stack, token)
    assert (await cand.get("/api/v1/candidate/assessment")).status_code == 401
    async with stack.anonymous() as anon:
        opened = await anon.post("/api/v1/candidate/session", json={"token": token})
    assert opened.status_code == 200, opened.text
    view = opened.json()
    assert view["status"] == "started" and 44 * 60 <= view["seconds_left"] <= 45 * 60
    assert [p["problem"]["slug"] for p in view["problems"]] == ["sum", "secret-sum"]
    assert view["total_points"] == 100

    # The candidate submits (no account) and sees their own verdicts, samples only.
    resp = await submit(cand, inv["id"], "sum")
    assert resp.status_code == 202, resp.text
    first = await stack.verdict(resp.json()["id"], cand)
    assert first["verdict"] == "AC" and first["user_id"] is None
    assert all(t["output"] is None for t in first["tests"] if not t["name"].startswith("sample/"))
    wrong = await submit(cand, inv["id"], "secret-sum", AC + " #VERDICT:WA")
    await stack.verdict(wrong.json()["id"], cand)
    for kind in ("paste", "tab_hidden", "tab_visible"):
        assert (
            await cand.post(
                "/api/v1/candidate/events", json={"kind": kind, "detail": {"chars": 120}}
            )
        ).status_code == 204
    view = (await cand.get("/api/v1/candidate/assessment")).json()
    assert [p["best_score"] for p in view["problems"]] == [60.0, 0.0]

    # Finishing ends it: no more submissions or reads with the link.
    assert (await cand.post("/api/v1/candidate/finish")).json()["status"] == "submitted"
    after = await submit(cand, inv["id"], "sum")
    assert after.status_code == 401 and after.json()["error"]["code"] == "assessment_submitted"
    async with stack.anonymous() as anon:
        assert (
            await anon.post("/api/v1/candidate/session", json={"token": token})
        ).status_code == 401

    report = await stack.ok("GET", f"/api/v1/assessments/{a['id']}/invitations/{inv['id']}/report")
    assert report["total"] == 60 and report["total_points"] == 100
    assert [(p["slug"], p["earned"], p["best_verdict"]) for p in report["problems"]] == [
        ("sum", 60.0, "AC"),
        ("secret-sum", 0.0, "WA"),
    ]
    assert [s["verdict"] for s in report["submissions"]] == ["AC", "WA"] and report["submissions"][
        0
    ]["source"] == AC
    assert [e["kind"] for e in report["events"]] == [
        "started",
        "paste",
        "tab_hidden",
        "tab_visible",
        "submitted",
    ]
    assert report["invitation"]["signals"] == 2 and "not proof" in report["signals_note"]
    assert report["invitation"]["status"] == "submitted"
    listed = await stack.ok("GET", f"/api/v1/assessments/{a['id']}/invitations")
    assert listed[0]["score"] == 60 and listed[0]["status"] == "submitted"
    await cand.aclose()


async def test_the_deadline_ends_the_assessment(stack: Stack) -> None:
    await problems_ready(stack)
    a = await assessment(stack)
    inv, token = await invite(stack, a)
    async with stack.anonymous() as anon:
        await anon.post("/api/v1/candidate/session", json={"token": token})
    cand = candidate(stack, token)
    assert (await submit(cand, inv["id"], "sum")).status_code == 202
    await set_deadline(inv["id"], datetime.now(UTC) - timedelta(seconds=1))
    late = await submit(cand, inv["id"], "sum")
    assert late.status_code == 401 and late.json()["error"]["code"] == "assessment_over"
    assert (await cand.get("/api/v1/candidate/assessment")).status_code == 401
    listed = await stack.ok("GET", f"/api/v1/assessments/{a['id']}/invitations")
    assert listed[0]["status"] == "expired"
    await cand.aclose()


async def test_a_candidate_reaches_only_their_own_assessment(stack: Stack) -> None:
    await problems_ready(stack)
    await make_problem(stack, "not-in-it")
    a = await assessment(stack)
    other = await assessment(stack, title="Another role")
    inv, token = await invite(stack, a)
    other_inv, other_token = await invite(stack, other, "someone@example.test")
    async with stack.anonymous() as anon:
        await anon.post("/api/v1/candidate/session", json={"token": token})
        await anon.post("/api/v1/candidate/session", json={"token": other_token})
    cand = candidate(stack, token)
    # Another candidate's invitation, a problem outside the assessment, staff endpoints.
    assert (await submit(cand, other_inv["id"], "sum")).status_code == 404
    assert (await submit(cand, inv["id"], "not-in-it")).status_code == 404
    for path in (
        "/api/v1/assessments",
        f"/api/v1/assessments/{other['id']}",
        f"/api/v1/assessments/{a['id']}/invitations",
    ):
        assert (await cand.get(path)).status_code == 401, path
    # Another candidate's submission stays invisible.
    other_cand = candidate(stack, other_token)
    sid = (await submit(other_cand, other_inv["id"], "sum")).json()["id"]
    assert (await cand.get(f"/api/v1/submissions/{sid}")).status_code == 404
    assert (await cand.get("/api/v1/submissions")).json()["total"] == 0
    # A made-up token gets nothing.
    stranger = candidate(stack, "x" * 43)
    assert (await stranger.get("/api/v1/candidate/assessment")).status_code == 401
    # Staff preview a problem of the assessment without an invitation.
    assert (await submit(stack.client, a["id"], "sum")).status_code == 202
    for c in (cand, other_cand, stranger):
        await c.aclose()


async def test_revoked_and_resent_links(stack: Stack) -> None:
    await problems_ready(stack)
    a = await assessment(stack)
    inv, token = await invite(stack, a)
    # Resending issues a new link; the old one stops working.
    resent = await stack.ok("POST", f"/api/v1/assessments/{a['id']}/invitations/{inv['id']}/resend")
    assert resent["status"] == "invited"
    new_token = mail.OUTBOX[-1].text.split("/take/", 1)[1].split()[0]
    assert new_token != token
    async with stack.anonymous() as anon:
        assert (
            await anon.post("/api/v1/candidate/session", json={"token": token})
        ).status_code == 401
        assert (
            await anon.post("/api/v1/candidate/session", json={"token": new_token})
        ).status_code == 200
    cand = candidate(stack, new_token)
    assert (await cand.get("/api/v1/candidate/assessment")).status_code == 200
    await stack.ok("POST", f"/api/v1/assessments/{a['id']}/invitations/{inv['id']}/revoke")
    refused = await cand.get("/api/v1/candidate/assessment")
    assert refused.status_code == 401 and refused.json()["error"]["code"] == "link_revoked"
    assert (await submit(cand, inv["id"], "sum")).status_code == 401
    await cand.aclose()


async def test_the_window_and_the_closing_time_cap_the_timer(stack: Stack) -> None:
    await problems_ready(stack)
    closes = datetime.now(UTC) + timedelta(minutes=10)
    a = await assessment(stack, closes_at=closes.isoformat())
    _, token = await invite(stack, a)
    async with stack.anonymous() as anon:
        view = (await anon.post("/api/v1/candidate/session", json={"token": token})).json()
    assert view["seconds_left"] <= 10 * 60, "a 45 minute assessment closing in 10 minutes gets 10"

    later = await assessment(stack, opens_at=(datetime.now(UTC) + timedelta(days=1)).isoformat())
    _, early = await invite(stack, later, "early@example.test")
    async with stack.anonymous() as anon:
        resp = await anon.post("/api/v1/candidate/session", json={"token": early})
    assert resp.status_code == 403 and resp.json()["error"]["code"] == "not_open_yet"

    closed = await assessment(
        stack,
        opens_at=(datetime.now(UTC) - timedelta(days=2)).isoformat(),
        closes_at=(datetime.now(UTC) - timedelta(days=1)).isoformat(),
    )
    _, gone = await invite(stack, closed, "gone@example.test")
    async with stack.anonymous() as anon:
        resp = await anon.post("/api/v1/candidate/session", json={"token": gone})
    assert resp.status_code == 401 and resp.json()["error"]["code"] == "assessment_over"


async def test_only_staff_manage_assessments(stack: Stack) -> None:
    await problems_ready(stack)
    student = await stack.user()
    resp = await student.post(
        "/api/v1/assessments", json={"title": "x", "problems": [{"problem": "sum"}]}
    )
    assert resp.status_code == 403
    assert (await student.get("/api/v1/assessments")).status_code == 403


async def test_candidate_events_are_capped(stack: Stack) -> None:
    await problems_ready(stack)
    a = await assessment(stack)
    inv, token = await invite(stack, a)
    async with stack.anonymous() as anon:
        await anon.post("/api/v1/candidate/session", json={"token": token})
    engine = create_async_engine(TEST_DB)
    async with engine.begin() as conn:
        await conn.execute(
            text("UPDATE invitations SET events_count = 500 WHERE id = :i"), {"i": inv["id"]}
        )
    cand = candidate(stack, token)
    assert (await cand.post("/api/v1/candidate/events", json={"kind": "paste"})).status_code == 204
    async with engine.connect() as conn:
        n = (
            await conn.execute(
                text("SELECT count(*) FROM candidate_events WHERE invitation_id = :i"),
                {"i": inv["id"]},
            )
        ).scalar_one()
    await engine.dispose()
    assert n == 1, "only the 'started' event; the capped one is dropped"
    bad = await cand.post("/api/v1/candidate/events", json={"kind": "keylogger"})
    assert bad.status_code == 422
    await cand.aclose()


async def test_the_background_task_expires_finished_time(stack: Stack) -> None:
    from codejudge.assessments.service import expire
    from codejudge.core.container import Container

    await problems_ready(stack)
    a = await assessment(stack)
    inv, token = await invite(stack, a)
    async with stack.anonymous() as anon:
        await anon.post("/api/v1/candidate/session", json={"token": token})
    await set_deadline(inv["id"], datetime.now(UTC) - timedelta(minutes=1))
    container = Container.build(stack.settings)
    try:
        assert await expire(container) == 1
        assert await expire(container) == 0, "idempotent"
    finally:
        await container.close()
    listed = await stack.ok("GET", f"/api/v1/assessments/{a['id']}/invitations")
    assert listed[0]["status"] == "expired"
