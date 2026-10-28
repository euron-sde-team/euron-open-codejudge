"""Health and system endpoints, the background tasks, the CLI, live verdicts and list filters."""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from codejudge import cli
from codejudge.core.config import get_settings
from codejudge.core.container import Container
from codejudge.submissions import tasks
from tests.integration.conftest import Stack, login, make_problem

pytestmark = pytest.mark.asyncio
AC = "print(sum(map(int, input().split())))"


async def test_health_readiness_and_metrics(stack: Stack) -> None:
    async with stack.anonymous() as anon:
        assert (await anon.get("/healthz")).json() == {"status": "ok"}
        assert (await anon.get("/health")).json()["status"] == "ok"
        ready = await anon.get("/readyz")
        assert ready.status_code == 200 and ready.json()["checks"]["postgres"]["ok"]
        assert ready.json()["checks"]["redis"]["ok"]
        metrics = await anon.get("/metrics")
        assert metrics.status_code == 200 and "python_info" in metrics.text
        assert (await anon.get("/api/v1/system")).status_code == 401


async def test_system_info_is_for_staff(stack: Stack) -> None:
    await make_problem(stack)
    info = await stack.ok("GET", "/api/v1/system")
    assert info["redis"] is True and info["judge"] is not None
    assert info["problems"] == 1 and info["users"] >= 1 and "Python 3" in info["languages"]
    student = await stack.user()
    assert (await student.get("/api/v1/system")).status_code == 403
    queue = await stack.ok("GET", "/api/v1/judge/queue")
    assert set(queue) == {"waiting", "in_progress", "workers"}


@pytest.fixture
def settings_overrides(request: pytest.FixtureRequest) -> dict[str, Any]:
    return getattr(request, "param", {})


@pytest.mark.parametrize("settings_overrides", [{"redis_url": ""}], indirect=True)
async def test_without_redis_the_api_serves_but_judging_waits(stack: Stack) -> None:
    async with stack.anonymous() as anon:
        ready = await anon.get("/readyz")
        assert ready.status_code == 200 and "redis" not in ready.json()["checks"]
    info = await stack.ok("GET", "/api/v1/system")
    assert info["redis"] is False and info["judge"] is None
    p = await stack.ok(
        "POST", "/api/v1/problems", {"slug": "noredis", "title": "No Redis"}, status=201
    )
    await stack.ok(
        "POST",
        f"/api/v1/problems/{p['id']}/versions",
        {"tests": [{"name": "secret/1", "input": "1", "answer": "1"}]},
        status=201,
    )
    resp = await stack.client.post(
        "/api/v1/submissions",
        json={"problem": "noredis", "language": "python3", "source": "print(1)"},
    )
    assert resp.status_code == 503 and resp.json()["error"]["code"] == "judging_unavailable"


async def test_old_runs_are_purged_and_submissions_kept(stack: Stack) -> None:
    await make_problem(stack)
    student = await stack.user()
    run = (
        await student.post(
            "/api/v1/runs", json={"problem": "sum", "language": "python3", "source": AC}
        )
    ).json()
    fresh = (
        await student.post(
            "/api/v1/runs", json={"problem": "sum", "language": "python3", "source": AC}
        )
    ).json()
    sub = (
        await student.post(
            "/api/v1/submissions", json={"problem": "sum", "language": "python3", "source": AC}
        )
    ).json()
    for sid in (run["id"], fresh["id"], sub["id"]):
        await stack.verdict(sid, student)
    engine = create_async_engine(stack.settings.database_url)
    async with engine.begin() as conn:
        old = datetime.now(UTC) - timedelta(days=2)
        await conn.execute(
            text("UPDATE submissions SET created_at = :t WHERE id IN (:a, :b)"),
            {"t": old, "a": run["id"], "b": sub["id"]},
        )
    container = Container.build(stack.settings)
    try:
        assert await tasks.purge_runs(container) == 1
        assert await tasks.purge_runs(container) == 0
    finally:
        await container.close()
    async with engine.connect() as conn:
        left = {str(r[0]) for r in await conn.execute(text("SELECT id FROM submissions"))}
    await engine.dispose()
    assert run["id"] not in left and fresh["id"] in left and sub["id"] in left


async def test_queue_depth_is_published(stack: Stack, caplog: pytest.LogCaptureFixture) -> None:
    container = Container.build(stack.settings)
    try:
        with caplog.at_level(logging.INFO, logger="codejudge.worker"):
            assert await tasks.queue_depth(container) == 0
        assert any(r.getMessage() == "judge queue" for r in caplog.records)
        assert tasks.QUEUE_WORKERS._value.get() >= 0  # type: ignore[attr-defined]
    finally:
        await container.close()
    offline = Container.build(stack.settings.model_copy(update={"redis_url": ""}))
    try:
        assert await tasks.queue_depth(offline) == 0
    finally:
        await offline.close()


async def test_create_admin_from_the_command_line(
    stack: Stack, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("DATABASE_URL", stack.settings.database_url)
    monkeypatch.setenv("CODEJUDGE_ADMIN_PASSWORD", "Cli-Admin-123")
    get_settings.cache_clear()
    try:
        await asyncio.to_thread(
            cli.main, ["create-admin", "--email", "cli@example.test", "--name", "Cli"]
        )
        await login(stack.api_url, {"email": "cli@example.test", "password": "Cli-Admin-123"})
        # Running it again resets the password and keeps the account an admin.
        monkeypatch.setenv("CODEJUDGE_ADMIN_PASSWORD", "Cli-Admin-456")
        await asyncio.to_thread(cli.main, ["create-admin", "--email", "CLI@example.test"])
        client = await login(
            stack.api_url, {"email": "cli@example.test", "password": "Cli-Admin-456"}
        )
        assert (await client.get("/api/v1/auth/me")).json()["role"] == "admin"
    finally:
        get_settings.cache_clear()


async def test_live_verdicts_stream_until_done(stack: Stack) -> None:
    await make_problem(stack)
    student = await stack.user()
    stack.judge.paused.set()
    sid = (
        await student.post(
            "/api/v1/submissions", json={"problem": "sum", "language": "python3", "source": AC}
        )
    ).json()["id"]
    events: list[dict[str, Any]] = []

    async def read() -> None:
        async with student.stream("GET", f"/api/v1/submissions/{sid}/events") as resp:
            assert resp.headers["content-type"].startswith("text/event-stream")
            async for line in resp.aiter_lines():
                if line.startswith("data: "):
                    events.append(json.loads(line[6:]))

    reader = asyncio.create_task(read())
    await asyncio.sleep(0.5)
    stack.judge.paused.clear()
    await asyncio.wait_for(reader, 20)
    assert (
        events[0]["status"] == "queued"
        and events[-1]["status"] == "done"
        and events[-1]["verdict"] == "AC"
    )
    # Once judged, the stream answers at once with the final state.
    async with student.stream("GET", f"/api/v1/submissions/{sid}/events") as resp:
        lines = [line async for line in resp.aiter_lines() if line.startswith("data: ")]
    assert json.loads(lines[0][6:])["status"] == "done"
    other = await stack.user()
    assert (await other.get(f"/api/v1/submissions/{sid}/events")).status_code == 404
    assert (await other.get(f"/api/v1/submissions/{sid}")).status_code == 404


async def test_submission_lists_filter_and_stay_private(stack: Stack) -> None:
    await make_problem(stack)
    ada = await stack.user(name="Ada")
    bob = await stack.user(name="Bob")
    ids = []
    for client, src in ((ada, AC), (ada, AC + "  #VERDICT:WA"), (bob, AC)):
        ids.append(
            (
                await client.post(
                    "/api/v1/submissions",
                    json={"problem": "sum", "language": "python3", "source": src},
                )
            ).json()["id"]
        )
    for sid in ids:
        await stack.verdict(sid)
    mine = (await ada.get("/api/v1/submissions")).json()
    assert mine["total"] == 2 and all(s["source"] is None for s in mine["items"])
    assert (await ada.get("/api/v1/submissions?verdict=wa")).json()["total"] == 1
    everyone = await stack.ok("GET", "/api/v1/submissions?problem=sum")
    assert everyone["total"] >= 3 and {s["user_name"] for s in everyone["items"]} >= {"Ada", "Bob"}
    bob_id = (await bob.get("/api/v1/auth/me")).json()["id"]
    assert (await stack.ok("GET", f"/api/v1/submissions?user_id={bob_id}"))["total"] == 1
    # Staff see their own reference runs under "mine"; they made no practice submission.
    assert (await stack.ok("GET", "/api/v1/submissions?mine=true&context=practice"))["total"] == 0
    assert (await stack.ok("GET", "/api/v1/submissions?context=practice"))["total"] >= 3
    assert (await ada.get(f"/api/v1/submissions/{ids[2]}")).status_code == 404


async def test_only_live_judges_count_and_gone_ones_are_forgotten(
    stack: Stack, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A judge replaced by a new container leaves its name in the consumer group; it must
    not show as online, and the queue task forgets it."""
    import redis.asyncio as aioredis

    from codejudge.core import queue as queue_module
    from tests.integration.conftest import GROUP, STREAM, TEST_REDIS

    r = aioredis.Redis.from_url(TEST_REDIS, decode_responses=True)
    await r.xgroup_createconsumer(STREAM, GROUP, "gone-judge")
    container = Container.build(stack.settings)
    try:
        names = {c["name"] for c in await r.xinfo_consumers(STREAM, GROUP)}
        assert "gone-judge" in names
        monkeypatch.setattr(queue_module, "ONLINE_IDLE_MS", -1)
        assert (await container.queue.depth())["workers"] == 0
        monkeypatch.setattr(queue_module, "STALE_IDLE_MS", -1)
        assert await container.queue.prune_consumers() >= 1
        names = {c["name"] for c in await r.xinfo_consumers(STREAM, GROUP)}
        assert "gone-judge" not in names
    finally:
        await container.close()
        await r.aclose()
