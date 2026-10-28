"""AC1: every failure class gets its verdict, in every language."""

from __future__ import annotations

import pytest
from tests.judge.conftest import job, source

from codejudge.core.contract import Verdict
from codejudge.judge.runner import Judge

LANGUAGES = ["python3", "cpp17", "java21", "javascript"]
CASES = [
    ("ac", Verdict.AC),
    ("wa", Verdict.WA),
    ("tle", Verdict.TLE),
    ("mle", Verdict.MLE),
    ("re", Verdict.RE),
    ("ce", Verdict.CE),
    ("ole", Verdict.OLE),
]


@pytest.mark.parametrize("language", LANGUAGES)
@pytest.mark.parametrize(("program", "expected"), CASES)
def test_verdict(
    judge: Judge, sum_package: str, language: str, program: str, expected: Verdict
) -> None:
    result = judge.judge(
        job(sum_package, language, source(language, program), time_ms=1000, memory_mb=64)
    )
    assert result.verdict == expected, (
        result.verdict,
        result.compile_output,
        result.tests,
        result.error,
    )
    if expected == Verdict.AC:
        assert result.score == result.max_score == 100
        assert all(t.verdict == Verdict.AC for t in result.tests)
    if expected == Verdict.WA:
        # The first failing test decides; samples show the checker's message, hidden tests never.
        failing = next(t for t in result.tests if t.verdict == Verdict.WA)
        assert failing.name == "sample/1" and failing.checker_message
        assert all(
            t.output_preview is None for t in result.tests if not t.name.startswith("sample/")
        )
    if expected == Verdict.CE:
        assert result.compile_output


def test_sleeping_forever_is_a_time_limit(judge: Judge, sum_package: str) -> None:
    result = judge.judge(job(sum_package, "python3", source("python3", "sleep"), time_ms=500))
    assert result.verdict == Verdict.TLE


def test_custom_input_returns_output(judge: Judge, sum_package: str) -> None:
    result = judge.judge(job(sum_package, "cpp17", source("cpp17", "ac"), custom_input="20 22\n"))
    assert result.verdict == Verdict.AC and result.run_output and result.run_output.strip() == "42"


def test_cpu_time_is_measured(judge: Judge, sum_package: str) -> None:
    busy = "s = 0\nfor i in range(3_000_000):\n    s += i\na, b = map(int, input().split())\nprint(a + b)\n"
    result = judge.judge(job(sum_package, "python3", busy))
    assert result.verdict == Verdict.AC and 50 < result.time_ms < 2000
