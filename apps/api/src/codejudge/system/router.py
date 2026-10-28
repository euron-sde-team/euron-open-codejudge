"""Health, readiness, metrics and deployment info."""

from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable
from typing import Any

from fastapi import APIRouter, Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from sqlalchemy import func, select, text

from codejudge import __version__
from codejudge.auth.dependencies import Staff
from codejudge.core.deps import ContainerDep, SessionDep
from codejudge.core.schemas import ApiModel
from codejudge.problems.models import Problem
from codejudge.problems.service import languages_out
from codejudge.submissions.models import Submission
from codejudge.users.models import User

router = APIRouter(tags=["system"])


@router.get("/healthz", summary="Liveness")
async def healthz() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/health", summary="Liveness (alias of /healthz)")
async def health() -> dict[str, str]:
    return {"status": "ok", "version": __version__}


async def _probe(name: str, coro: Awaitable[Any]) -> tuple[str, dict[str, Any]]:
    t0 = time.perf_counter()
    try:
        await asyncio.wait_for(coro, timeout=2)
        return name, {"ok": True, "ms": round((time.perf_counter() - t0) * 1000, 1)}
    except Exception as exc:
        return name, {"ok": False, "error": type(exc).__name__}


@router.get("/readyz", summary="Readiness: Postgres reachable (Redis reported too)")
async def readyz(container: ContainerDep, response: Response) -> dict[str, Any]:
    async def pg() -> None:
        async with container.db.engine.connect() as conn:
            await conn.execute(text("select 1"))

    probes = [_probe("postgres", pg())]
    if container.kv.backend == "redis":
        probes.append(_probe("redis", container.kv.ping()))
    checks = dict(await asyncio.gather(*probes))
    # Without Redis the API still serves problems, results and scoreboards; only new
    # judging waits. So Postgres alone decides readiness and Redis reports as degraded.
    ok = checks["postgres"]["ok"]
    response.status_code = 200 if ok else 503
    degraded = not all(c["ok"] for c in checks.values())
    return {"status": "degraded" if degraded else "ready", "checks": checks}


@router.get("/metrics", summary="Prometheus metrics", include_in_schema=False)
async def metrics() -> Response:
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


class JudgeInfo(ApiModel):
    waiting: int
    in_progress: int
    workers: int


class SystemInfo(ApiModel):
    version: str
    environment: str
    storage: str
    key_mode: str
    cache: str
    mail: str
    redis: bool
    judge: JudgeInfo | None
    languages: list[str]
    problems: int
    users: int
    submissions: int


@router.get("/api/v1/system", response_model=SystemInfo, tags=["system"])
async def system(_: Staff, session: SessionDep, container: ContainerDep) -> SystemInfo:
    s = container.settings
    redis_ok = await container.queue.ping()
    judge = JudgeInfo(**await container.queue.depth()) if redis_ok else None

    async def count(model: Any) -> int:
        return int(await session.scalar(select(func.count()).select_from(model)) or 0)

    return SystemInfo(
        version=__version__,
        environment=s.environment,
        storage=s.storage,
        key_mode=s.key_mode,
        cache=s.cache_backend,
        mail=s.mail_backend,
        redis=redis_ok,
        judge=judge,
        languages=[lang.name for lang in languages_out()],
        problems=await count(Problem),
        users=await count(User),
        submissions=await count(Submission),
    )
