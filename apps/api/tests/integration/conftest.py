"""Integration harness: the real API served over HTTP from a background thread, against
real Postgres and Redis, with a *fake judge* consuming the real job stream.

    make test-integration      (starts Postgres and Redis containers if needed)

The fake judge reads jobs from the Redis Stream through the consumer group, exactly like a
judge worker, and posts results to ``/internal/judge/results`` with the judge token. It
decides verdicts from a marker in the source (``#VERDICT:WA``, ``#VERDICT:TLE``, a score
with ``#SCORE:40``), so the API's flow (queueing, ingestion, idempotency, scoreboards,
gradebooks) is tested fast and deterministically. Real compilation and sandboxing are
covered by ``tests/judge`` inside the judge image and by the end-to-end suite.

Isolation: every run uses its own database (``TEST_DATABASE_URL``) and Redis DB index
(``TEST_REDIS_URL``), so two suites can run at once without stealing each other's jobs.
The suite drops and recreates the database, so it refuses any database whose name does not
contain "test" and any non-local host unless ALLOW_REMOTE_TEST_DB=true.
"""

from __future__ import annotations

import asyncio
import contextlib
import os
import re
import socket
import threading
import time
from collections.abc import AsyncIterator, Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx
import pytest
import redis.asyncio as aioredis
import uvicorn
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from codejudge.core.config import Settings
from codejudge.core.contract import (
    GroupResult,
    JudgeJob,
    JudgeResult,
    TestResult,
    Verdict,
    overall,
)

TEST_DB = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+asyncpg://codejudge:codejudge@localhost:4742/codejudge_test"
)
TEST_REDIS = os.environ.get("TEST_REDIS_URL", "redis://localhost:4779/15")
ADMIN = {"email": "admin@example.test", "password": "Admin-Pass-123"}
CSRF = {"x-codejudge-csrf": "1"}
JUDGE_TOKEN = "test-only-judge-token-with-32-plus-bytes-ok"
STREAM, GROUP = "judge:jobs", "judges"


def _guard(url: str) -> None:
    parsed = urlparse(url.replace("+asyncpg", ""))
    if "test" not in (parsed.path or ""):
        raise RuntimeError(f"refusing {parsed.path!r}: the test database name must contain 'test'")
    if (
        parsed.hostname not in ("localhost", "127.0.0.1", "postgres")
        and os.environ.get("ALLOW_REMOTE_TEST_DB") != "true"
    ):
        raise RuntimeError("refusing a non-local test database (set ALLOW_REMOTE_TEST_DB=true)")


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


class Served:
    """An ASGI app (or import string) served by uvicorn on a thread, with its own loop."""

    def __init__(self, app: Any, port: int | None = None) -> None:
        self.port = port or free_port()
        self.url = f"http://127.0.0.1:{self.port}"
        config = uvicorn.Config(app, host="127.0.0.1", port=self.port, log_level="warning")
        self.server = uvicorn.Server(config)
        self.thread = threading.Thread(target=self.server.run, daemon=True)

    def start(self, health: str = "/healthz") -> Served:
        self.thread.start()
        deadline = time.time() + 60
        while time.time() < deadline:
            try:
                if httpx.get(self.url + health, timeout=1).status_code < 500:
                    return self
            except httpx.HTTPError:
                pass
            time.sleep(0.1)
        raise RuntimeError(f"server on {self.url} did not start")

    def stop(self) -> None:
        self.server.should_exit = True
        self.thread.join(timeout=15)


@pytest.fixture(scope="session")
def mock_ai() -> Iterator[str]:
    served = Served("mockai.app:app").start()
    yield served.url
    served.stop()


@pytest.fixture(scope="session")
async def database() -> AsyncIterator[str]:
    """A fresh database built by the migrations (so they are tested on every run)."""
    _guard(TEST_DB)
    admin_url = TEST_DB.rsplit("/", 1)[0] + "/postgres"
    name = TEST_DB.rsplit("/", 1)[1]
    engine = create_async_engine(admin_url, isolation_level="AUTOCOMMIT")
    async with engine.connect() as conn:
        await conn.execute(text(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)'))
        await conn.execute(text(f'CREATE DATABASE "{name}"'))
    await engine.dispose()
    from codejudge.migrations.runner import upgrade

    await asyncio.to_thread(upgrade, TEST_DB)
    yield TEST_DB


def make_settings(database: str, tmp_path: Path, **overrides: Any) -> Settings:
    values: dict[str, Any] = {
        "environment": "test",
        "database_url": database,
        "redis_url": TEST_REDIS,
        "session_secret": "test-only-session-secret-with-32-plus-bytes",
        "invite_token_pepper": "test-only-invite-pepper-with-32-plus-bytes",
        "local_master_key": "test-only-master-key-with-32-plus-bytes-ok",
        "judge_token": JUDGE_TOKEN,
        "local_storage_dir": str(tmp_path / "objects"),
        "public_url": "http://localhost:4710",
        "mail_backend": "log",
        "submit_rpm": 1000,
        # The option matrix (make test-matrix) reruns the suite against Floci S3 and KMS.
        "key_mode": os.environ.get("TEST_KEY_MODE", "local"),
        "storage": os.environ.get("TEST_STORAGE", "local"),
        "aws_endpoint_url": os.environ.get("TEST_AWS_ENDPOINT"),
        "s3_force_path_style": True,
        "kms_key_id": os.environ.get("TEST_KMS_KEY_ID", "alias/codejudge-local"),
        "objects_bucket": os.environ.get("TEST_OBJECTS_BUCKET", "codejudge-local-objects"),
    }
    values.update(overrides)
    return Settings(**values)


async def reset(database: str) -> None:
    """Empty every table and the job stream between tests."""
    engine = create_async_engine(database)
    async with engine.begin() as conn:
        tables = (
            await conn.execute(
                text(
                    "SELECT tablename FROM pg_tables WHERE schemaname = 'public' "
                    "AND tablename <> 'alembic_version'"
                )
            )
        ).scalars()
        names = ", ".join(f'"{t}"' for t in tables)
        if names:
            await conn.execute(text(f"TRUNCATE {names} RESTART IDENTITY CASCADE"))
    await engine.dispose()
    r = aioredis.Redis.from_url(TEST_REDIS)
    await r.flushdb()
    await r.aclose()


async def bootstrap_admin(database: str) -> None:
    from codejudge.core.db import Database
    from codejudge.core.security import hash_password
    from codejudge.users.models import User

    db = Database(database, pool_size=1, max_overflow=0)
    async with db.sessionmaker() as session:
        session.add(
            User(
                email=ADMIN["email"],
                name="Admin",
                role="admin",
                password_hash=hash_password(ADMIN["password"]),
            )
        )
        await session.commit()
    await db.dispose()


# ── the fake judge ───────────────────────────────────────────────────────────────────
MARKER = re.compile(r"#VERDICT:([A-Z]+)")
SCORE = re.compile(r"#SCORE:([0-9.]+)")


def fake_result(job: JudgeJob, worker: str = "fake") -> JudgeResult:
    """A plausible result for a job, decided by markers in its source."""
    if job.custom_input is not None:
        return JudgeResult(
            job_id=job.job_id, attempt=job.attempt, submission_id=job.submission_id,
            worker=worker, verdict=Verdict.AC, run_output=f"echo: {job.custom_input}",
            time_ms=5, memory_kb=1024,
        )  # fmt: skip
    found = MARKER.search(job.source)
    wanted = Verdict(found.group(1)) if found else Verdict.AC
    if wanted == Verdict.CE:
        return JudgeResult(
            job_id=job.job_id, attempt=job.attempt, submission_id=job.submission_id,
            worker=worker, verdict=Verdict.CE, compile_output="main.cpp:1: error: expected ';'",
            max_score=sum(g.points for g in job.groups),
        )  # fmt: skip
    wanted_score = float(m.group(1)) if (m := SCORE.search(job.source)) else None
    tests: list[TestResult] = []
    groups: list[GroupResult] = []
    wanted_tests = set(job.only_tests)
    failed = False
    budget = wanted_score
    for g in job.groups:
        mine = [
            t
            for t in job.tests
            if t.group == g.name and (not wanted_tests or t.name in wanted_tests)
        ]
        group_ok = True
        if budget is not None:
            group_ok = budget >= g.points
            budget = budget - g.points if group_ok else budget
        for t in mine:
            fail_here = (wanted != Verdict.AC and not t.sample and not failed) or not group_ok
            verdict = (wanted if wanted != Verdict.AC else Verdict.WA) if fail_here else Verdict.AC
            if fail_here and failed:
                verdict = Verdict.SKIPPED
            failed = failed or fail_here
            tests.append(
                TestResult(
                    name=t.name, group=t.group, verdict=verdict, time_ms=12, memory_kb=2048,
                    output_preview="3\n" if t.sample else None,
                )
            )  # fmt: skip
        earned = (
            g.points
            if mine and all(t.verdict == Verdict.AC for t in tests if t.group == g.name)
            else 0.0
        )
        groups.append(
            GroupResult(
                name=g.name,
                points=g.points,
                earned=earned,
                verdict=Verdict.AC if earned or not g.points else Verdict.WA,
            )
        )
    verdict = overall(tests)
    return JudgeResult(
        job_id=job.job_id, attempt=job.attempt, submission_id=job.submission_id, worker=worker,
        verdict=verdict, score=sum(g.earned for g in groups),
        max_score=sum(g.points for g in job.groups), tests=tests, groups=groups,
        time_ms=12, memory_kb=2048, judged_ms=20,
    )  # fmt: skip


@dataclass
class FakeJudge:
    """Consumes the job stream like a worker and posts results to the API."""

    api_url: str
    paused: asyncio.Event = field(default_factory=asyncio.Event)
    judged: list[str] = field(default_factory=list)
    task: asyncio.Task[None] | None = None

    async def run(self) -> None:
        r = aioredis.Redis.from_url(TEST_REDIS, decode_responses=True)
        with contextlib.suppress(aioredis.ResponseError):
            await r.xgroup_create(STREAM, GROUP, id="0", mkstream=True)
        headers = {"authorization": f"Bearer {JUDGE_TOKEN}", "content-type": "application/json"}
        held: list[tuple[str, dict[str, str]]] = []
        async with httpx.AsyncClient(base_url=self.api_url, headers=headers, timeout=30) as http:
            try:
                while True:
                    got = await r.xreadgroup(GROUP, "fake", {STREAM: ">"}, count=10, block=100)
                    for _, messages in got or []:
                        held.extend(messages)
                    # Paused: hold what was read (a read can race the pause) until resumed.
                    if self.paused.is_set():
                        await asyncio.sleep(0.05)
                        continue
                    while held:
                        msg_id, fields = held.pop(0)
                        job = JudgeJob.model_validate_json(fields["job"])
                        result = fake_result(job)
                        resp = await http.post(
                            "/internal/judge/results", content=result.model_dump_json()
                        )
                        assert resp.status_code in (200, 409), resp.text
                        self.judged.append(job.submission_id)
                        await r.xack(STREAM, GROUP, msg_id)
                        await r.xdel(STREAM, msg_id)
            finally:
                await r.aclose()

    def start(self) -> None:
        self.task = asyncio.create_task(self.run())

    async def stop(self) -> None:
        if self.task:
            self.task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self.task


# ── the stack ────────────────────────────────────────────────────────────────────────
@dataclass
class Stack:
    """The running API, a signed-in admin, the fake judge, and helpers."""

    api_url: str
    settings: Settings
    client: httpx.AsyncClient
    judge: FakeJudge
    mock_ai_url: str

    async def ok(self, method: str, path: str, json: Any = None, status: int | None = None) -> Any:
        resp = await self.client.request(method, path, json=json)
        expected = status or (201 if method == "POST" and resp.status_code == 201 else 200)
        assert resp.status_code == expected, f"{method} {path}: {resp.status_code} {resp.text}"
        return resp.json() if resp.content else None

    def anonymous(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(base_url=self.api_url, timeout=30)

    async def user(
        self, role: str = "student", email: str | None = None, name: str = "Test User"
    ) -> httpx.AsyncClient:
        """Create a user with the admin client and return a client signed in as them."""
        email = email or f"{role}-{time.monotonic_ns()}@example.test"
        password = "User-Pass-123"
        await self.ok(
            "POST",
            "/api/v1/users",
            {"email": email, "name": name, "role": role, "password": password},
            status=201,
        )
        return await login(self.api_url, {"email": email, "password": password})

    async def verdict(
        self, submission_id: str, client: httpx.AsyncClient | None = None, wait_s: float = 20
    ) -> dict[str, Any]:
        """The submission once it is judged."""
        c = client or self.client
        deadline = time.monotonic() + wait_s
        while True:
            resp = await c.get(f"/api/v1/submissions/{submission_id}")
            assert resp.status_code == 200, resp.text
            data: dict[str, Any] = resp.json()
            if data["status"] == "done":
                return data
            if time.monotonic() > deadline:
                raise AssertionError(f"submission {submission_id} was never judged: {data}")
            await asyncio.sleep(0.1)


async def login(base_url: str, creds: dict[str, str] = ADMIN) -> httpx.AsyncClient:
    client = httpx.AsyncClient(base_url=base_url, timeout=30, headers=CSRF)
    resp = await client.post("/api/v1/auth/login", json=creds)
    assert resp.status_code == 200, resp.text
    client.headers["authorization"] = f"Bearer {resp.json()['session_token']}"
    return client


@pytest.fixture
def settings_overrides() -> dict[str, Any]:
    """Tests override this to change the API's settings."""
    return {}


@pytest.fixture
async def stack(
    database: str, tmp_path: Path, mock_ai: str, settings_overrides: dict[str, Any]
) -> AsyncIterator[Stack]:
    from codejudge.main import create_app

    await reset(database)
    await bootstrap_admin(database)
    settings = make_settings(database, tmp_path, **settings_overrides)
    served = Served(create_app(settings)).start()
    judge = FakeJudge(served.url)
    judge.start()
    client = await login(served.url)
    try:
        yield Stack(served.url, settings, client, judge, mock_ai)
    finally:
        await client.aclose()
        await judge.stop()
        served.stop()


# ── problem helpers ──────────────────────────────────────────────────────────────────
SUM_TESTS = [
    {"name": "sample/1", "input": "1 2\n", "answer": "3\n"},
    {"name": "secret/1", "input": "40 2\n", "answer": "42\n"},
    {"name": "secret/2", "input": "-5 5\n", "answer": "0\n"},
]


async def make_problem(
    stack: Stack,
    slug: str = "sum",
    *,
    tests: list[dict[str, str]] | None = None,
    groups: list[dict[str, Any]] | None = None,
    publish: bool = True,
    visibility: str = "public",
) -> dict[str, Any]:
    """A problem with tests and an accepted reference solution, published by default."""
    problem: dict[str, Any] = await stack.ok(
        "POST", "/api/v1/problems",
        {"slug": slug, "title": slug.replace("-", " ").title(), "statement_md": "Add two numbers.", "visibility": visibility},
        status=201,
    )  # fmt: skip
    await stack.ok(
        "POST",
        f"/api/v1/problems/{problem['id']}/versions",
        {"tests": tests or SUM_TESTS, "groups": groups or []},
        status=201,
    )
    await stack.ok(
        "POST",
        f"/api/v1/problems/{problem['id']}/references",
        {"name": "ok", "language": "python3", "source": "print(sum(map(int, input().split())))"},
        status=201,
    )
    if publish:
        await stack.ok("POST", f"/api/v1/problems/{problem['id']}/references/judge")
        deadline = time.monotonic() + 20
        while True:
            admin = await stack.ok("GET", f"/api/v1/problems/{problem['id']}/admin")
            if admin["publishable"]:
                break
            assert time.monotonic() < deadline, admin["publish_blockers"]
            await asyncio.sleep(0.1)
        await stack.ok("POST", f"/api/v1/problems/{problem['id']}/publish")
    return problem
