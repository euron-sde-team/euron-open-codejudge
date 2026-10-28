"""Periodic tasks of the submissions domain."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

from prometheus_client import Gauge
from sqlalchemy import delete, select

from codejudge.core.container import Container
from codejudge.core.tasks import periodic
from codejudge.submissions.models import Submission

log = logging.getLogger("codejudge.worker")

RUNS_KEPT = timedelta(days=1)
BATCH = 1000


@periodic("submissions.purge_runs")
async def purge_runs(container: Container) -> int:
    """Runs on samples or custom input are scratch work: drop them after a day."""
    cutoff = datetime.now(UTC) - RUNS_KEPT
    async with container.db.sessionmaker() as session:
        ids = (
            await session.scalars(
                select(Submission.id)
                .where(Submission.context == "run", Submission.created_at < cutoff)
                .limit(BATCH)
            )
        ).all()
        if not ids:
            return 0
        await session.execute(delete(Submission).where(Submission.id.in_(ids)))
        await session.commit()
        return len(ids)


QUEUE_WAITING = Gauge("codejudge_judge_queue_waiting", "Judge jobs waiting for a worker")
QUEUE_IN_PROGRESS = Gauge("codejudge_judge_queue_in_progress", "Judge jobs being judged")
QUEUE_WORKERS = Gauge("codejudge_judge_workers", "Judge workers known to the job stream")


@periodic("submissions.queue_depth")
async def queue_depth(container: Container) -> int:
    """Publish the queue depth: a Prometheus gauge, and a log line that the CloudWatch
    metric filter turns into the queue-depth alarm on AWS. Never reports work done, so it
    does not keep the worker ticking on its own."""
    if not await container.queue.ping():
        return 0
    depth = await container.queue.depth()
    QUEUE_WAITING.set(depth["waiting"])
    QUEUE_IN_PROGRESS.set(depth["in_progress"])
    QUEUE_WORKERS.set(depth["workers"])
    log.info("judge queue", extra=depth)
    return 0
