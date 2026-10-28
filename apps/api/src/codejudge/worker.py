"""Background worker: the periodic tasks every domain registers (core/tasks.py).

Stateless and safe to run as several replicas: each task claims its rows with
``FOR UPDATE SKIP LOCKED`` or plain conditional UPDATEs. SIGTERM finishes the tick in hand,
then exits. Prometheus metrics on WORKER_METRICS_PORT.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import signal

from prometheus_client import start_http_server

from codejudge.core.config import get_settings
from codejudge.core.container import Container
from codejudge.core.db import import_all_models
from codejudge.core.logs import configure_logging
from codejudge.core.tasks import tasks

log = logging.getLogger("codejudge.worker")


def import_task_modules() -> None:
    """Every module that registers a periodic task."""
    from codejudge.submissions import tasks as _submissions  # noqa: F401


async def tick(container: Container) -> bool:
    """One pass over every task. True when any of them did work (run again at once)."""
    busy = False
    for name, task in tasks().items():
        try:
            handled = await task(container)
        except Exception:
            log.exception("task %s failed", name)
            continue
        if handled:
            log.info("task done", extra={"task": name, "items": handled})
            busy = True
    return busy


async def main() -> None:
    settings = get_settings()
    configure_logging(settings.log_level)
    import_all_models()
    import_task_modules()
    if settings.worker_metrics_port:
        start_http_server(settings.worker_metrics_port)
    container = Container.build(settings)
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, stop.set)
    log.info("worker started")
    try:
        while not stop.is_set():
            try:
                busy = await tick(container)
            except Exception:
                log.exception("worker tick failed")
                busy = False
            if not busy:
                with contextlib.suppress(TimeoutError):
                    await asyncio.wait_for(stop.wait(), timeout=settings.worker_poll_interval_s)
    finally:
        await container.close()
        log.info("worker stopped")
