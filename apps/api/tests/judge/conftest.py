"""Judge tests: run inside the judge image with production settings (make test-judge).

They exercise the real sandbox (nsjail, rlimits, syscall filter) and the real toolchains,
so they are skipped anywhere nsjail is not installed.
"""

from __future__ import annotations

import hashlib
import io
import os
import shutil
import uuid
import zipfile
from collections.abc import Iterator
from pathlib import Path

import pytest

from codejudge.core.contract import CheckerSpec, GroupSpec, JudgeJob, Limits, TestSpec
from codejudge.judge import languages
from codejudge.judge.packages import PackageCache
from codejudge.judge.runner import Judge, JudgeConfig

NSJAIL = "/usr/local/bin/nsjail"
PROGRAMS = Path(__file__).with_name("programs")

pytestmark = pytest.mark.judge

if not os.path.exists(NSJAIL):
    pytest.skip("needs the judge image (make test-judge)", allow_module_level=True)

SUM_TESTS = {
    "sample/1": ("1 2\n", "3\n"),
    "secret/1": ("40 2\n", "42\n"),
    "secret/2": ("-5 5\n", "0\n"),
    "secret/3": ("1000000000000 1000000000000\n", "2000000000000\n"),
}
SUFFIX = {"python3": "py", "cpp17": "cpp", "java21": "java", "javascript": "js"}


def make_package(tests: dict[str, tuple[str, str]], extra: dict[str, bytes] | None = None) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for name, (inp, ans) in tests.items():
            z.writestr(f"data/{name}.in", inp)
            z.writestr(f"data/{name}.ans", ans)
        for name, data in (extra or {}).items():
            z.writestr(name, data)
    return buf.getvalue()


class Packages:
    """An in-memory package store standing in for the API's internal endpoint."""

    def __init__(self) -> None:
        self.blobs: dict[str, bytes] = {}

    def add(self, data: bytes) -> str:
        sha = hashlib.sha256(data).hexdigest()
        self.blobs[sha] = data
        return sha

    def fetch(self, sha: str, dest: Path) -> None:
        dest.write_bytes(self.blobs[sha])


@pytest.fixture(scope="session")
def store() -> Packages:
    return Packages()


@pytest.fixture(scope="session")
def judge(store: Packages, tmp_path_factory: pytest.TempPathFactory) -> Iterator[Judge]:
    root = tmp_path_factory.mktemp("judge")
    cache = PackageCache(root / "cache", 500_000_000, store.fetch)
    config = JudgeConfig(
        work_dir=root / "work",
        compile_time_s=30,
        compile_memory_mb=1024,
        max_output_bytes=8 << 20,
        wall_factor=2.0,
        wall_extra_s=1.0,
        worker="test",
    )
    yield Judge(config, languages.registry(), cache)
    shutil.rmtree(root, ignore_errors=True)


@pytest.fixture(scope="session")
def sum_package(store: Packages) -> str:
    return store.add(make_package(SUM_TESTS))


def source(language: str, name: str) -> str:
    return (PROGRAMS / language / f"{name}.{SUFFIX[language]}").read_text()


def job(
    package: str,
    language: str,
    code: str,
    *,
    time_ms: int = 2000,
    memory_mb: int = 128,
    output_mb: int = 4,
    tests: dict[str, tuple[str, str]] = SUM_TESTS,
    checker: CheckerSpec | None = None,
    groups: list[GroupSpec] | None = None,
    custom_input: str | None = None,
) -> JudgeJob:
    return JudgeJob(
        job_id=uuid.uuid4().hex,
        submission_id=uuid.uuid4().hex,
        language=language,
        source=code,
        package_sha256=package,
        limits=Limits(time_ms=time_ms, memory_mb=memory_mb, output_mb=output_mb),
        checker=checker or CheckerSpec(),
        groups=groups or [GroupSpec(name="sample", points=0), GroupSpec(name="secret", points=100)],
        tests=[
            TestSpec(name=n, group=n.split("/")[0], sample=n.startswith("sample/")) for n in tests
        ],
        custom_input=custom_input,
    )
