"""Periodic tasks of the submissions domain."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, select

from codejudge.core.container import Container
from codejudge.core.tasks import periodic
from codejudge.submissions.models import Submission

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
