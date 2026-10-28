"""Judge one job: compile, run every test in the sandbox, compare, score.

The program sees only the input of the test it is running: the input is its stdin, its
output goes to a file outside the sandbox, and the expected answer is compared there. The
package itself is never mounted into the program's sandbox. Custom checkers (problem
setter code) run in a sandbox of their own with read-only access to the three files they
need.

Verdicts are decided from measurements, in this order: the sandbox failed to start
(internal error); output at the limit; the time limit (CPU time over the limit, or the wall
clock ran out); memory over the limit; a non-zero exit or a signal (runtime
error); then the checker (accepted or wrong answer). Only sample tests return output and
checker messages: for hidden tests those would reveal the answers.
"""

from __future__ import annotations

import logging
import shutil
import signal
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from codejudge.core.contract import (
    GroupResult,
    JudgeJob,
    JudgeResult,
    TestResult,
    TestSpec,
    Verdict,
    overall,
)
from codejudge.judge import checkers
from codejudge.judge.languages import Language
from codejudge.judge.packages import PackageCache, PackageError, test_files
from codejudge.judge.sandbox import Mount, RunLimits, RunResult, Sandbox

log = logging.getLogger(__name__)

PREVIEW_BYTES = 4096
COMPILE_OUTPUT_BYTES = 16_000
RUN_OUTPUT_BYTES = 64_000
OOM_MARKERS = (b"MemoryError", b"std::bad_alloc", b"OutOfMemoryError", b"heap out of memory")


class InternalError(Exception):
    """The judge, not the program, failed: the submission gets IE and is retried."""


@dataclass(frozen=True)
class JudgeConfig:
    work_dir: Path
    compile_time_s: float
    compile_memory_mb: int
    max_output_bytes: int
    wall_factor: float
    wall_extra_s: float
    worker: str


Progress = Callable[[str, int], None]


class Judge:
    def __init__(
        self,
        config: JudgeConfig,
        languages: dict[str, Language],
        packages: PackageCache,
        sandbox: Sandbox | None = None,
    ):
        self.config = config
        self.languages = languages
        self.packages = packages
        self.sandbox = sandbox or Sandbox()

    # ── entry point ──────────────────────────────────────────────────────────────────
    def judge(self, job: JudgeJob, progress: Progress | None = None) -> JudgeResult:
        started = time.monotonic()
        work = self.config.work_dir / f"{job.job_id}-{job.attempt}"
        shutil.rmtree(work, ignore_errors=True)
        work.mkdir(parents=True)
        result = JudgeResult(
            job_id=job.job_id,
            attempt=job.attempt,
            submission_id=job.submission_id,
            worker=self.config.worker,
            verdict=Verdict.IE,
            max_score=sum(g.points for g in job.groups),
        )
        try:
            self._judge(job, work, result, progress or (lambda _s, _n: None))
        except (InternalError, PackageError, OSError) as exc:
            log.exception("internal error judging %s", job.submission_id)
            result.verdict, result.error = Verdict.IE, str(exc)[:500]
        finally:
            shutil.rmtree(work, ignore_errors=True)
        result.judged_ms = round((time.monotonic() - started) * 1000)
        return result

    def _judge(self, job: JudgeJob, work: Path, result: JudgeResult, progress: Progress) -> None:
        language = self.languages.get(job.language)
        if language is None:
            raise InternalError(f"language {job.language!r} is not installed on this worker")
        box = work / "box"
        box.mkdir()
        (box / language.source).write_text(job.source, encoding="utf-8")

        progress("compiling", 0)
        ok, output = self._compile(language, box, work)
        result.compile_output = output or None
        if not ok:
            result.verdict = Verdict.CE
            return

        if job.custom_input is not None:
            self._run_custom(job, language, box, work, result)
            return

        package = self.packages.get(job.package_sha256)
        checker = self._prepare_checker(job, package, work)
        wanted = set(job.only_tests)
        tests = [t for t in job.tests if not wanted or t.name in wanted]
        by_group: dict[str, list[TestSpec]] = {}
        for t in tests:
            by_group.setdefault(t.group, []).append(t)

        done = 0
        for group in job.groups:
            failed = False
            group_tests: list[TestResult] = []
            for spec in by_group.get(group.name, []):
                if failed and group.stop_on_failure:
                    group_tests.append(
                        TestResult(name=spec.name, group=group.name, verdict=Verdict.SKIPPED)
                    )
                    continue
                progress("running", done)
                tr = self._run_test(job, language, box, work, package, spec, checker)
                group_tests.append(tr)
                done += 1
                failed = failed or tr.verdict != Verdict.AC
                if tr.verdict == Verdict.IE:
                    raise InternalError(tr.checker_message or f"test {spec.name} failed to run")
            result.tests.extend(group_tests)
            ran = [t for t in group_tests if t.verdict != Verdict.SKIPPED]
            earned = (
                group.points if ran and all(t.verdict == Verdict.AC for t in group_tests) else 0.0
            )
            result.groups.append(
                GroupResult(
                    name=group.name,
                    points=group.points,
                    earned=earned,
                    verdict=overall(group_tests) if group_tests else Verdict.SKIPPED,
                )
            )

        result.verdict = overall(result.tests)
        result.score = sum(g.earned for g in result.groups)
        measured = [t for t in result.tests if t.verdict != Verdict.SKIPPED]
        result.time_ms = max((t.time_ms for t in measured), default=0)
        result.memory_kb = max((t.memory_kb for t in measured), default=0)

    # ── compile ──────────────────────────────────────────────────────────────────────
    def _compile(self, language: Language, box: Path, work: Path) -> tuple[bool, str]:
        if not language.compile:
            return True, ""
        cfg = self.config
        limits = RunLimits(
            cpu_ms=round(cfg.compile_time_s * 1000),
            wall_ms=round(cfg.compile_time_s * 2000),
            address_mb=cfg.compile_memory_mb if language.memory_mode == "address" else None,
            output_bytes=64 << 20,
            processes=64,
            tmp_mb=256,
            env=tuple(language.env),
        )
        argv = language.command(language.compile, mem_mb=cfg.compile_memory_mb, stack_mb=64)
        run = self.sandbox.run(
            argv,
            limits=limits,
            mounts=[Mount(box, "/box", writable=True)],
            stdin=None,
            stdout=work / "compile.out",
            stderr=work / "compile.err",
            log=work / "compile.log",
        )
        if run.launch_failed:
            raise InternalError("the sandbox failed to start the compiler: " + run.log[-300:])
        text = _read(work / "compile.out", COMPILE_OUTPUT_BYTES) + _read(
            work / "compile.err", COMPILE_OUTPUT_BYTES
        )
        text = text.replace("/box/", "")[:COMPILE_OUTPUT_BYTES]
        if run.wall_timed_out or run.cpu_ms > limits.cpu_ms:
            return False, (text + "\nCompilation took longer than the limit.").strip()
        return run.ok, text

    # ── run one test ─────────────────────────────────────────────────────────────────
    def _limits(self, job: JudgeJob, language: Language) -> RunLimits:
        cpu_ms = language.time_limit_ms(job.limits.time_ms)
        wall_ms = round(cpu_ms * self.config.wall_factor + self.config.wall_extra_s * 1000)
        mem = job.limits.memory_mb
        return RunLimits(
            cpu_ms=cpu_ms,
            wall_ms=wall_ms,
            address_mb=mem + language.memory_overhead_mb
            if language.memory_mode == "address"
            else None,
            output_bytes=min(job.limits.output_mb << 20, self.config.max_output_bytes),
            processes=language.threads,
            stack_mb=min(mem, 256),
            env=tuple(language.env),
        )

    def _execute(
        self, job: JudgeJob, language: Language, box: Path, work: Path, stdin: Path
    ) -> tuple[RunResult, RunLimits]:
        limits = self._limits(job, language)
        argv = language.command(language.run, mem_mb=job.limits.memory_mb, stack_mb=limits.stack_mb)
        run = self.sandbox.run(
            argv,
            limits=limits,
            mounts=[Mount(box, "/box")],
            stdin=stdin,
            stdout=work / "run.out",
            stderr=work / "run.err",
            log=work / "run.log",
        )
        return run, limits

    def classify(
        self, run: RunResult, limits: RunLimits, job: JudgeJob, language: Language, stderr: bytes
    ) -> Verdict:
        if run.launch_failed:
            return Verdict.IE
        # Output first: once a write is cut at the limit, C stdio marks the stream failed and
        # later writes return without a system call, so a program printing in a loop never
        # gets SIGXFSZ and spins until the CPU limit. Output at the cap is the evidence.
        if run.output_bytes >= limits.output_bytes or run.signal == signal.SIGXFSZ:
            return Verdict.OLE
        if run.wall_timed_out or run.cpu_ms > limits.cpu_ms or run.signal == signal.SIGXCPU:
            return Verdict.TLE
        limit_kb = job.limits.memory_mb * 1024
        oom = any(marker in stderr for marker in OOM_MARKERS)
        if language.memory_mode == "rss":
            if oom or run.memory_kb > (job.limits.memory_mb + language.memory_overhead_mb) * 1024:
                return Verdict.MLE
        elif not run.ok and (oom or run.memory_kb >= limit_kb * 0.9):
            return Verdict.MLE
        if not run.ok:
            return Verdict.RE
        return Verdict.AC

    def _run_test(
        self,
        job: JudgeJob,
        language: Language,
        box: Path,
        work: Path,
        package: Path,
        spec: TestSpec,
        checker: Path | None,
    ) -> TestResult:
        inp, ans = test_files(package, spec.name)
        run, limits = self._execute(job, language, box, work, inp)
        stderr = _read_bytes(work / "run.err", 8192)
        verdict = self.classify(run, limits, job, language, stderr)
        message = ""
        if verdict == Verdict.IE:
            message = "the sandbox failed to start the program: " + run.log[-300:]
        elif verdict == Verdict.AC:
            verdict, message = self._check(job, work, inp, ans, checker)
        tr = TestResult(
            name=spec.name,
            group=spec.group,
            verdict=verdict,
            time_ms=min(run.cpu_ms, limits.cpu_ms + 1) if verdict == Verdict.TLE else run.cpu_ms,
            memory_kb=run.memory_kb,
            exit_code=run.exit_code,
            signal=run.signal,
        )
        if spec.sample:
            tr.output_preview = _read(work / "run.out", PREVIEW_BYTES)
            tr.checker_message = checkers.message(message) or None
        elif verdict == Verdict.IE:
            tr.checker_message = message[:300]
        return tr

    def _check(
        self, job: JudgeJob, work: Path, inp: Path, ans: Path, checker: Path | None
    ) -> tuple[Verdict, str]:
        output = work / "run.out"
        if job.checker.kind != "custom":
            check = checkers.compare(ans, output, job.checker)
            return (Verdict.AC if check.ok else Verdict.WA), check.message
        assert checker is not None
        return self._run_checker(job, work, checker, inp, ans, output)

    # ── custom checkers ──────────────────────────────────────────────────────────────
    def _prepare_checker(self, job: JudgeJob, package: Path, work: Path) -> Path | None:
        spec = job.checker
        if spec.kind != "custom":
            return None
        if not spec.language or not spec.path:
            raise InternalError("custom checker without a language and a path")
        language = self.languages.get(spec.language)
        if language is None:
            raise InternalError(f"checker language {spec.language!r} is not installed")
        source = package / spec.path
        if not source.is_file():
            raise InternalError(f"checker source {spec.path!r} is not in the package")
        box = work / "checker"
        box.mkdir()
        (box / language.source).write_bytes(source.read_bytes())
        ok, output = self._compile(language, box, work)
        if not ok:
            raise InternalError("the problem's checker does not compile: " + output[:300])
        return box

    def _run_checker(
        self, job: JudgeJob, work: Path, box: Path, inp: Path, ans: Path, output: Path
    ) -> tuple[Verdict, str]:
        spec = job.checker
        language = self.languages[spec.language or ""]
        files = work / "checkfiles"
        shutil.rmtree(files, ignore_errors=True)
        files.mkdir()
        feedback = files / "feedback"
        feedback.mkdir()
        feedback.chmod(0o777)
        for src, name in ((inp, "input"), (ans, "answer"), (output, "output")):
            shutil.copyfile(src, files / name)
        if spec.protocol == "kattis":
            args, stdin = ["/check/input", "/check/answer", "/check/feedback/"], output
        else:
            args, stdin = ["/check/input", "/check/output", "/check/answer"], None
        limits = RunLimits(
            cpu_ms=10_000,
            wall_ms=20_000,
            address_mb=1024 if language.memory_mode == "address" else None,
            output_bytes=1 << 20,
            processes=language.threads,
            env=tuple(language.env),
        )
        argv = language.command(language.run, mem_mb=512, stack_mb=64) + args
        run = self.sandbox.run(
            argv,
            limits=limits,
            mounts=[
                Mount(box, "/box"),
                Mount(files, "/check"),
                Mount(feedback, "/check/feedback", writable=True),
            ],
            stdin=stdin,
            stdout=work / "check.out",
            stderr=work / "check.err",
            log=work / "check.log",
        )
        decision = checkers.custom_verdict(spec.protocol, run.exit_code)
        message = (
            _read(feedback / "judgemessage.txt", 400)
            or _read(work / "check.err", 400)
            or _read(work / "check.out", 400)
        )
        if decision is None:
            raise InternalError(
                f"the checker failed (exit {run.exit_code}, signal {run.signal}): {message[:200]}"
            )
        return (Verdict.AC if decision else Verdict.WA), message

    # ── run with custom input ────────────────────────────────────────────────────────
    def _run_custom(
        self, job: JudgeJob, language: Language, box: Path, work: Path, result: JudgeResult
    ) -> None:
        stdin = work / "custom.in"
        stdin.write_text(job.custom_input or "", encoding="utf-8")
        run, limits = self._execute(job, language, box, work, stdin)
        stderr = _read_bytes(work / "run.err", 8192)
        verdict = self.classify(run, limits, job, language, stderr)
        if verdict == Verdict.IE:
            raise InternalError("the sandbox failed to start the program: " + run.log[-300:])
        result.verdict = verdict
        result.time_ms, result.memory_kb = run.cpu_ms, run.memory_kb
        out = _read(work / "run.out", RUN_OUTPUT_BYTES)
        err = stderr.decode("utf-8", errors="replace").strip()
        result.run_output = out + (f"\n--- stderr ---\n{err}" if err else "")


def _read(path: Path, limit: int) -> str:
    return _read_bytes(path, limit).decode("utf-8", errors="replace")


def _read_bytes(path: Path, limit: int) -> bytes:
    try:
        with path.open("rb") as f:
            return f.read(limit)
    except FileNotFoundError:
        return b""
