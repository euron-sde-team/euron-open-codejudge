"""The judge worker process: take jobs from the stream, judge them, report back.

Jobs live in a Redis Stream read through a consumer group. A worker takes one job at a
time; while judging it re-claims its own message every heartbeat, which keeps the job's
idle time low. A worker that dies stops doing that, so after the lease the job's idle time
passes the threshold and any other worker claims it (``XAUTOCLAIM``) and judges it again.
The result is posted (with retries) before the message is acknowledged, and the API
accepts only the first final result per job, so a job is never lost and never counted
twice. After ``max_attempts`` deliveries the job is reported as an internal error instead
of looping forever.

The worker holds no database or storage credentials: it reaches the stream and the API's
token-protected internal endpoints, nothing else.
"""

from __future__ import annotations

import contextlib
import logging
import signal
import socket
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from types import FrameType
from typing import Any, Literal

import httpx
import redis
from prometheus_client import Counter, Histogram, start_http_server

from codejudge.core.config import JudgeSettings, get_judge_settings
from codejudge.core.contract import Heartbeat, JudgeJob, JudgeResult, Verdict
from codejudge.judge import languages
from codejudge.judge.packages import PackageCache
from codejudge.judge.runner import Judge, JudgeConfig

log = logging.getLogger("codejudge.judge")

STREAM = "judge:jobs"
GROUP = "judges"
MAX_ATTEMPTS = 3

JUDGED = Counter("codejudge_judge_jobs_total", "Jobs judged, by verdict", ["verdict"])
DURATION = Histogram(
    "codejudge_judge_seconds",
    "Time to judge one job",
    buckets=(0.1, 0.25, 0.5, 1, 2, 5, 10, 30, 60, 120),
)


@dataclass
class _Progress:
    stage: Literal["compiling", "running"] = "compiling"
    done: int = 0


class ApiClient:
    """The API's internal judge endpoints, authenticated with the shared judge token."""

    def __init__(self, base_url: str, token: str):
        self.http = httpx.Client(
            base_url=base_url.rstrip("/"),
            headers={"Authorization": f"Bearer {token}"},
            timeout=httpx.Timeout(30.0, connect=5.0),
        )

    def fetch_package(self, sha256: str, dest: Path) -> None:
        with self.http.stream("GET", f"/internal/judge/packages/{sha256}") as resp:
            resp.raise_for_status()
            with dest.open("wb") as out:
                for chunk in resp.iter_bytes(1 << 20):
                    out.write(chunk)

    def post_result(self, result: JudgeResult) -> None:
        delay = 1.0
        for attempt in range(1, 7):
            try:
                resp = self.http.post("/internal/judge/results", content=result.model_dump_json())
                # 409: a result for this job was already accepted (another attempt won).
                if resp.status_code in (200, 202, 409):
                    return
                resp.raise_for_status()
            except httpx.HTTPError as exc:
                if attempt == 6:
                    raise
                log.warning("posting result for %s failed (%s); retrying", result.job_id, exc)
                time.sleep(delay)
                delay = min(delay * 2, 30)

    def heartbeat(self, beat: Heartbeat) -> None:
        # Progress is informational: the lease does not depend on it, so failures are ignored.
        with contextlib.suppress(httpx.HTTPError):
            self.http.post("/internal/judge/heartbeat", content=beat.model_dump_json(), timeout=5.0)


class Worker:
    def __init__(self, settings: JudgeSettings):
        self.settings = settings
        self.name = settings.worker_name or socket.gethostname()
        self.redis = redis.Redis.from_url(settings.redis_url, decode_responses=True)
        self.api = ApiClient(settings.api_internal_url, settings.judge_token)
        cache = PackageCache(
            Path(settings.cache_dir) / "packages", settings.cache_max_bytes, self.api.fetch_package
        )
        config = JudgeConfig(
            work_dir=Path(settings.work_dir),
            compile_time_s=settings.compile_time_limit_s,
            compile_memory_mb=settings.compile_memory_mb,
            max_output_bytes=settings.max_output_bytes,
            wall_factor=settings.wall_factor,
            wall_extra_s=settings.wall_extra_s,
            worker=self.name,
        )
        self.judge = Judge(config, languages.registry(settings.languages_file or None), cache)
        self.lease_ms = int(max(settings.heartbeat_s * 4, 60) * 1000)
        self.stopping = threading.Event()

    def ensure_group(self) -> None:
        try:
            self.redis.xgroup_create(STREAM, GROUP, id="0", mkstream=True)
        except redis.ResponseError as exc:
            if "BUSYGROUP" not in str(exc):
                raise

    def next_message(self) -> tuple[str, dict[str, str]] | None:
        # A job whose worker stopped heart-beating is reclaimed first.
        reply: Any = self.redis.xautoclaim(
            STREAM, GROUP, self.name, min_idle_time=self.lease_ms, count=1
        )
        claimed = reply[1]
        if claimed:
            msg_id, fields = claimed[0]
            return str(msg_id), dict(fields)
        got: Any = self.redis.xreadgroup(GROUP, self.name, {STREAM: ">"}, count=1, block=5000)
        if not got:
            return None
        msg_id, fields = got[0][1][0]
        return str(msg_id), dict(fields)

    def deliveries(self, msg_id: str) -> int:
        pending: Any = self.redis.xpending_range(STREAM, GROUP, min=msg_id, max=msg_id, count=1)
        return int(pending[0]["times_delivered"]) if pending else 1

    def process(self, msg_id: str, fields: dict[str, str]) -> None:
        job = JudgeJob.model_validate_json(fields["job"])
        job = job.model_copy(update={"attempt": self.deliveries(msg_id)})
        if job.attempt > MAX_ATTEMPTS:
            log.error(
                "job %s failed %d times; reporting an internal error", job.job_id, job.attempt - 1
            )
            self.api.post_result(
                JudgeResult(
                    job_id=job.job_id,
                    attempt=job.attempt,
                    submission_id=job.submission_id,
                    worker=self.name,
                    verdict=Verdict.IE,
                    error=f"the judge gave up after {MAX_ATTEMPTS} attempts",
                )
            )
            self.ack(msg_id)
            return

        state = _Progress()
        stop = threading.Event()

        def keep_alive() -> None:
            while not stop.wait(self.settings.heartbeat_s):
                # Re-claiming our own message resets its idle time: the lease is renewed.
                self.redis.xclaim(
                    STREAM, GROUP, self.name, min_idle_time=0, message_ids=[msg_id], justid=True
                )
                self.api.heartbeat(
                    Heartbeat(
                        job_id=job.job_id,
                        attempt=job.attempt,
                        worker=self.name,
                        status=state.stage,
                        tests_done=state.done,
                    )
                )

        def progress(stage: str, done: int) -> None:
            state.stage = "compiling" if stage == "compiling" else "running"
            state.done = done

        beat = threading.Thread(target=keep_alive, daemon=True)
        beat.start()
        try:
            with DURATION.time():
                result = self.judge.judge(job, progress)
        finally:
            stop.set()
            beat.join(timeout=5)
        JUDGED.labels(result.verdict.value).inc()
        self.api.post_result(result)
        self.ack(msg_id)
        log.info("judged %s: %s in %d ms", job.submission_id, result.verdict, result.judged_ms)

    def ack(self, msg_id: str) -> None:
        pipe = self.redis.pipeline()
        pipe.xack(STREAM, GROUP, msg_id)
        pipe.xdel(STREAM, msg_id)
        pipe.execute()

    def run(self) -> None:
        self.ensure_group()
        log.info("judge worker %s ready (%s)", self.name, ", ".join(self.judge.languages))
        while not self.stopping.is_set():
            try:
                message = self.next_message()
                if message is not None:
                    self.process(*message)
            except (redis.RedisError, httpx.HTTPError) as exc:
                log.warning("judge loop: %s; retrying in 2 s", exc)
                self.stopping.wait(2)
        log.info("judge worker %s stopped", self.name)


def main() -> None:
    settings = get_judge_settings()
    logging.basicConfig(level=settings.log_level)
    worker = Worker(settings)

    def stop(_sig: int, _frame: FrameType | None) -> None:
        # Finish the job in hand, then exit: a deploy never throws away a judgement.
        worker.stopping.set()

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    if settings.metrics_port:
        start_http_server(settings.metrics_port)
    worker.run()
