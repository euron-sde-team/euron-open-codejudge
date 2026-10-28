"""Process-wide services, built once in the app lifespan and shared by every request.

Holding them in one object (on ``app.state``) instead of module globals keeps the app
factory re-entrant and lets tests build an isolated container per app.
"""

from __future__ import annotations

from dataclasses import dataclass

import httpx

from codejudge.core.aws import aws_client
from codejudge.core.config import Settings
from codejudge.core.db import Database
from codejudge.core.kv import KV, create_kv
from codejudge.core.queue import JudgeQueue
from codejudge.core.sealing import KeySealer, KmsSealer, LocalSealer
from codejudge.core.storage import LocalStorage, ObjectStorage, S3Storage


def build_http_client(timeout_s: float) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        timeout=httpx.Timeout(timeout_s, connect=5.0),
        limits=httpx.Limits(max_connections=100, max_keepalive_connections=20),
        follow_redirects=False,
    )


@dataclass
class Container:
    settings: Settings
    db: Database
    kv: KV
    # Outbound calls the control plane makes itself: the optional AI hint provider.
    http: httpx.AsyncClient
    sealer: KeySealer
    storage: ObjectStorage
    queue: JudgeQueue

    @classmethod
    def build(cls, settings: Settings) -> Container:
        kv = create_kv(settings.redis_url, settings.memory_cache_max_bytes)
        sealer: KeySealer = (
            KmsSealer(aws_client(settings, "kms"), settings.kms_key_id)
            if settings.key_mode == "kms"
            else LocalSealer(settings.local_master_key)
        )
        storage: ObjectStorage = (
            S3Storage(aws_client(settings, "s3"), settings.objects_bucket)
            if settings.storage == "s3"
            else LocalStorage(settings.local_storage_dir)
        )
        return cls(
            settings=settings,
            db=Database(
                settings.database_url,
                pool_size=settings.db_pool_size,
                max_overflow=settings.db_max_overflow,
            ),
            kv=kv,
            http=build_http_client(10.0),
            sealer=sealer,
            storage=storage,
            queue=JudgeQueue(settings.redis_url),
        )

    async def close(self) -> None:
        await self.http.aclose()
        await self.queue.close()
        await self.kv.close()
        await self.db.dispose()
