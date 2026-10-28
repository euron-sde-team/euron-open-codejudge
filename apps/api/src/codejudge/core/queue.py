"""The judge job stream and live submission events, both in Redis.

Jobs go on a Redis Stream that judge workers read through a consumer group (see
``codejudge.judge.worker`` for leases and redelivery). Verdict updates are published on a
per-submission channel so the browser sees "judging test 3", then the verdict, without
polling; a subscriber that connects late still reads the current state from the database
first, so a missed message only delays the view, it never loses the result.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import redis.asyncio as aioredis

from codejudge.core.contract import JudgeJob
from codejudge.core.errors import AppError

STREAM = "judge:jobs"
GROUP = "judges"


class JudgingUnavailableError(AppError):
    status_code = 503
    code = "judging_unavailable"


class JudgeQueue:
    def __init__(self, url: str) -> None:
        self.redis: aioredis.Redis | None = aioredis.Redis.from_url(url) if url else None

    def _client(self) -> aioredis.Redis:
        if self.redis is None:
            raise JudgingUnavailableError(
                "Judging needs Redis: set REDIS_URL and start a judge worker"
            )
        return self.redis

    async def enqueue(self, job: JudgeJob) -> None:
        await self._client().xadd(STREAM, {"job": job.model_dump_json()})

    async def depth(self) -> dict[str, int]:
        """Jobs waiting and jobs in progress (for the dashboard and the alarms)."""
        r = self._client()
        try:
            groups = await r.xinfo_groups(STREAM)
        except aioredis.ResponseError:
            return {"waiting": 0, "in_progress": 0, "workers": 0}
        length = int(await r.xlen(STREAM))
        pending = sum(int(g.get("pending", 0)) for g in groups)
        consumers = 0
        for g in groups:
            consumers += len(await r.xinfo_consumers(STREAM, g["name"]))
        return {"waiting": max(0, length - pending), "in_progress": pending, "workers": consumers}

    async def publish(self, submission_id: str, payload: str) -> None:
        if self.redis is not None:
            await self.redis.publish(f"submission:{submission_id}", payload)

    async def listen(self, submission_id: str) -> AsyncIterator[str]:
        r = self._client()
        pubsub = r.pubsub()
        await pubsub.subscribe(f"submission:{submission_id}")
        try:
            async for message in pubsub.listen():
                if message.get("type") == "message":
                    data = message["data"]
                    yield data.decode() if isinstance(data, bytes) else str(data)
        finally:
            await pubsub.unsubscribe()
            await pubsub.aclose()  # type: ignore[no-untyped-call]

    async def ping(self) -> bool:
        if self.redis is None:
            return False
        try:
            return bool(await self.redis.ping())
        except aioredis.RedisError:
            return False

    async def close(self) -> None:
        if self.redis is not None:
            await self.redis.aclose()
