"""A finished judgement survives an API outage: the worker keeps posting it (it is never
judged again or turned into an internal error) and stops only when told to."""

from __future__ import annotations

import threading

import httpx

from codejudge.core.contract import JudgeResult, Verdict
from codejudge.judge.worker import ApiClient

RESULT = JudgeResult(job_id="j", attempt=1, submission_id="s", worker="w", verdict=Verdict.AC)


def client_with(responses: list[int]) -> tuple[ApiClient, list[int]]:
    seen: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        code = responses[min(len(seen), len(responses) - 1)]
        seen.append(code)
        if code == 0:
            raise httpx.ConnectError("api down")
        return httpx.Response(code)

    api = ApiClient("http://api", "token")
    api.http = httpx.Client(base_url="http://api", transport=httpx.MockTransport(handler))
    return api, seen


def test_a_result_is_posted_after_an_outage(monkeypatch: object) -> None:
    api, seen = client_with([0, 503, 502, 0, 200])
    never = threading.Event()
    waits: list[float] = []
    never.wait = lambda timeout=None: waits.append(timeout or 0) or False  # type: ignore[method-assign]
    assert api.post_result(RESULT, never) is True
    assert seen == [0, 503, 502, 0, 200] and len(waits) == 4


def test_an_already_applied_result_counts_as_posted() -> None:
    api, _ = client_with([409])
    assert api.post_result(RESULT, threading.Event()) is True


def test_stopping_gives_up_without_acknowledging() -> None:
    api, seen = client_with([0])
    stopping = threading.Event()
    stopping.set()
    assert api.post_result(RESULT, stopping) is False and len(seen) == 1
