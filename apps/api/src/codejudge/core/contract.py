"""The contract between the control plane and the judge workers.

The API puts a ``JudgeJob`` on the job stream; a worker judges it and posts a
``JudgeResult`` back to the API's internal endpoint. Both sides import only this module, so
the worker never depends on the API's database models (it has no database access at all).

Test data never travels in the job: the job names a test package by its SHA-256, and the
worker fetches and verifies it. The worker hands a program only the input of a test; the
expected answer stays outside the sandbox and is compared there.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Verdict(StrEnum):
    """A submission's or a test's outcome. Order in ``SEVERITY`` decides the overall verdict
    when tests disagree (the first failing test in order wins; see ``overall``)."""

    PENDING = "PENDING"
    JUDGING = "JUDGING"
    AC = "AC"  # Accepted
    WA = "WA"  # Wrong Answer
    TLE = "TLE"  # Time Limit Exceeded
    MLE = "MLE"  # Memory Limit Exceeded
    RE = "RE"  # Runtime Error
    OLE = "OLE"  # Output Limit Exceeded
    CE = "CE"  # Compilation Error
    SKIPPED = "SKIPPED"  # not run (an earlier test in a stop-on-failure group failed)
    IE = "IE"  # Internal Error: the judge failed, not the program


FINAL = frozenset(
    {
        Verdict.AC,
        Verdict.WA,
        Verdict.TLE,
        Verdict.MLE,
        Verdict.RE,
        Verdict.OLE,
        Verdict.CE,
        Verdict.IE,
    }
)

CheckerKind = Literal["exact", "tokens", "float", "custom"]
SubmissionContext = Literal["practice", "contest", "assignment", "assessment", "reference", "run"]


class LanguageRef(_Model):
    id: str = Field(pattern=r"^[a-z][a-z0-9_]{1,31}$")


class CheckerSpec(_Model):
    """How output is compared. ``tokens`` ignores whitespace differences (the default);
    ``float`` also accepts numbers within the tolerance; ``custom`` runs the problem's
    checker program (testlib style: input, expected, output; exit 0 accepts)."""

    kind: CheckerKind = "tokens"
    float_abs: float = Field(1e-6, ge=0)
    float_rel: float = Field(1e-6, ge=0)
    case_sensitive: bool = True
    # For ``custom``: the checker's language, its source inside the test package, and its
    # exit code convention ("kattis": 42 accepts, 43 rejects; "testlib": 0 accepts).
    language: str | None = None
    path: str | None = None
    protocol: Literal["kattis", "testlib"] = "kattis"


class TestSpec(_Model):
    """One test inside the package: ``<name>.in`` and ``<name>.ans``."""

    name: str = Field(pattern=r"^[A-Za-z0-9_.\-/]{1,200}$")
    group: str
    sample: bool = False


class GroupSpec(_Model):
    """A subtask. Its points are earned when every test in it passes (IOI style); a
    problem with one group of 100 points is plain pass/fail."""

    name: str = Field(pattern=r"^[A-Za-z0-9_\-]{1,64}$")
    points: float = Field(ge=0)
    # Stop running the group's tests after the first failure (saves time; the remaining
    # tests are SKIPPED). Points are all or nothing either way.
    stop_on_failure: bool = True


class Limits(_Model):
    time_ms: int = Field(ge=100, le=60_000)
    memory_mb: int = Field(ge=16, le=8192)
    output_mb: int = Field(64, ge=1, le=1024)


class JudgeJob(_Model):
    job_id: str
    attempt: int = Field(1, ge=1)
    submission_id: str
    language: str
    source: str
    # The package that holds the tests (and the custom checker, when there is one).
    package_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    limits: Limits
    checker: CheckerSpec = CheckerSpec()
    groups: list[GroupSpec]
    tests: list[TestSpec]
    # Run only these tests (samples for "run on samples"); empty means all of them.
    only_tests: list[str] = Field(default_factory=list)
    # "Run" with the user's own input: no package tests, no verdict, output returned.
    custom_input: str | None = None


class TestResult(_Model):
    name: str
    group: str
    verdict: Verdict
    time_ms: int = 0
    memory_kb: int = 0
    exit_code: int | None = None
    signal: int | None = None
    # Only for samples and custom runs: hidden tests' output never leaves the worker.
    output_preview: str | None = None
    checker_message: str | None = None


class GroupResult(_Model):
    name: str
    points: float
    earned: float
    verdict: Verdict


class JudgeResult(_Model):
    job_id: str
    attempt: int
    submission_id: str
    worker: str
    verdict: Verdict
    score: float = 0.0
    max_score: float = 0.0
    time_ms: int = 0
    memory_kb: int = 0
    compile_output: str | None = None
    tests: list[TestResult] = Field(default_factory=list)
    groups: list[GroupResult] = Field(default_factory=list)
    # "Run" with custom input: what the program printed.
    run_output: str | None = None
    judged_ms: int = 0
    error: str | None = None


class Heartbeat(_Model):
    job_id: str
    attempt: int
    worker: str
    status: Literal["compiling", "running"]
    tests_done: int = 0


def overall(tests: list[TestResult]) -> Verdict:
    """The submission's verdict: AC when every test passed, otherwise the verdict of the
    first test that did not (tests are judged in package order). An internal error
    anywhere wins, because then nothing else can be trusted."""
    if any(t.verdict == Verdict.IE for t in tests):
        return Verdict.IE
    for t in tests:
        if t.verdict not in (Verdict.AC, Verdict.SKIPPED):
            return t.verdict
    return Verdict.AC
