"""Organisation settings validation."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest
from pydantic import ValidationError

from codejudge.core.errors import AppError
from codejudge.org.schemas import SettingsUpdate
from codejudge.org.service import check_endpoint


def container(allow_private: bool) -> Any:
    return SimpleNamespace(settings=SimpleNamespace(ai_allow_private_endpoints=allow_private))


@pytest.mark.parametrize(
    "url",
    [
        "http://169.254.169.254/latest",
        "http://2852039166/",
        "ftp://models.example.com",
        "http://metadata/",
    ],
)
def test_metadata_and_odd_urls_are_refused(url: str) -> None:
    with pytest.raises(ValidationError):
        SettingsUpdate(ai_base_url=url)


def test_an_empty_url_clears_it() -> None:
    assert SettingsUpdate(ai_base_url="").ai_base_url == ""
    assert (
        SettingsUpdate(ai_base_url="https://api.example.com/v1/").ai_base_url
        == "https://api.example.com/v1"
    )


@pytest.mark.parametrize(
    "url", ["http://ollama:11434/v1", "http://127.0.0.1:8000/v1", "http://10.0.0.5/v1"]
)
def test_private_endpoints_follow_the_setting(url: str) -> None:
    check_endpoint(container(allow_private=True), url)
    with pytest.raises(AppError) as exc:
        check_endpoint(container(allow_private=False), url)
    assert exc.value.code == "ai_endpoint_private"
    check_endpoint(container(allow_private=False), "https://api.example.com/v1")
