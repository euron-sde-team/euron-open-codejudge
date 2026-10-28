"""The background worker's tick and the command line wiring."""

from __future__ import annotations

from typing import Any

import pytest
import yaml

from codejudge import cli, worker
from codejudge.core import tasks

pytestmark = pytest.mark.asyncio


async def test_a_tick_runs_every_task_and_survives_a_failing_one(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ran: list[str] = []

    async def ok(_container: Any) -> int:
        ran.append("ok")
        return 2

    async def idle(_container: Any) -> int:
        ran.append("idle")
        return 0

    async def broken(_container: Any) -> int:
        ran.append("broken")
        raise RuntimeError("boom")

    monkeypatch.setattr(tasks, "_TASKS", {"broken": broken, "ok": ok, "idle": idle})
    assert await worker.tick(None) is True  # type: ignore[arg-type]
    assert ran == ["broken", "ok", "idle"]
    monkeypatch.setattr(tasks, "_TASKS", {"idle": idle})
    assert await worker.tick(None) is False  # type: ignore[arg-type]


def test_periodic_registers_by_name() -> None:
    @tasks.periodic("test.registered")
    async def task(_container: Any) -> int:
        return 0

    try:
        assert tasks.tasks()["test.registered"] is task
    finally:
        tasks._TASKS.pop("test.registered", None)


def test_the_worker_imports_every_task_module() -> None:
    worker.import_task_modules()
    names = set(tasks.tasks())
    assert {"submissions.purge_runs", "submissions.queue_depth"} <= names
    assert any(n.startswith("assessments.") for n in names) and any(
        n.startswith("plagiarism.") for n in names
    )


def test_openapi_prints_the_whole_api(capsys: pytest.CaptureFixture[str]) -> None:
    cli.main(["openapi"])
    doc = yaml.safe_load(capsys.readouterr().out)
    assert doc["info"]["title"] == "Euron Open CodeJudge"
    assert "/api/v1/submissions" in doc["paths"] and "/internal/judge/results" not in doc["paths"]


@pytest.mark.parametrize(
    ("argv", "fn"),
    [
        (["serve", "--port", "9000"], "_serve"),
        (["judge"], "_judge"),
        (["worker"], "_worker"),
        (["migrate"], "_migrate"),
        (["revision", "-m", "x"], "_revision"),
        (["create-admin", "--email", "a@example.test"], "_admin"),
        (["seed-demo"], "_seed"),
    ],
)
def test_each_command_dispatches(monkeypatch: pytest.MonkeyPatch, argv: list[str], fn: str) -> None:
    called: list[Any] = []
    monkeypatch.setattr(cli, fn, lambda args: called.append(args))
    # Rebind the parser's defaults to the patched functions.
    cli.main(argv)
    assert called, f"{argv[0]} did not reach {fn}"


def test_a_weak_admin_password_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CODEJUDGE_ADMIN_PASSWORD", "short")
    with pytest.raises(SystemExit, match="password needs"):
        cli.main(["create-admin", "--email", "a@example.test"])


def test_a_command_is_required() -> None:
    with pytest.raises(SystemExit):
        cli.main([])
