"""AC2: hostile code is contained, and the worker keeps judging correctly afterwards.

Each program tries an escape and prints ``ESCAPED:<what>`` if it worked. The input is the
sample only, so its output comes back for inspection.
"""

from __future__ import annotations

import pytest

from codejudge.core.contract import GroupSpec, Verdict
from codejudge.judge.runner import Judge
from tests.judge.conftest import PROGRAMS, job, make_package, source

SAMPLE = {"sample/1": ("1 2\n", "done\n")}


@pytest.fixture(scope="module")
def sample_package(store) -> str:  # type: ignore[no-untyped-def]
    return store.add(make_package(SAMPLE))


def hostile(name: str) -> str:
    return (PROGRAMS / "hostile" / name).read_text()


def run(judge: Judge, package: str, language: str, code: str, **kw: object) -> object:
    return judge.judge(
        job(
            package,
            language,
            code,
            tests=SAMPLE,
            groups=[GroupSpec(name="sample", points=100)],
            **kw,
        )
    )  # type: ignore[arg-type]


@pytest.mark.parametrize("program", ["network.py", "secrets.py", "writes.py", "syscalls.py"])
def test_escape_attempts_fail(judge: Judge, sample_package: str, program: str) -> None:
    result = run(judge, sample_package, "python3", hostile(program))
    output = "".join(t.output_preview or "" for t in result.tests)  # type: ignore[attr-defined]
    assert "ESCAPED" not in output, output
    assert result.verdict == Verdict.AC, (result.verdict, output, result.error)  # type: ignore[attr-defined]


@pytest.mark.parametrize(
    ("language", "program"),
    [("python3", "forkbomb.py"), ("cpp17", "forkbomb.cpp"), ("python3", "threads.py")],
)
def test_process_bombs_are_contained(
    judge: Judge, sample_package: str, language: str, program: str
) -> None:
    result = run(judge, sample_package, language, hostile(program), time_ms=1000)
    output = "".join(t.output_preview or "" for t in result.tests)  # type: ignore[attr-defined]
    assert "ESCAPED" not in output
    assert result.verdict in (Verdict.TLE, Verdict.RE, Verdict.AC), result.verdict  # type: ignore[attr-defined]


def test_killing_everything_kills_only_the_sandbox(judge: Judge, sample_package: str) -> None:
    run(judge, sample_package, "python3", hostile("killall.py"))


def test_a_compiler_bomb_is_a_compilation_error(judge: Judge, sample_package: str) -> None:
    result = run(judge, sample_package, "cpp17", hostile("compilebomb.cpp"))
    assert result.verdict == Verdict.CE  # type: ignore[attr-defined]


def test_the_worker_still_judges_correctly_afterwards(judge: Judge, sum_package: str) -> None:
    for language in ("python3", "cpp17"):
        result = judge.judge(job(sum_package, language, source(language, "ac")))
        assert result.verdict == Verdict.AC and result.score == 100
