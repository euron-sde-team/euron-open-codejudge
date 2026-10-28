"""Invitation tokens: random, stored only as a keyed hash, and turned into a link."""

from __future__ import annotations

from codejudge.assessments.service import SIGNALS_NOTE, link, new_token, token_hash
from codejudge.core.config import Settings


def settings(pepper: str = "pepper-one-with-at-least-32-bytes-ok") -> Settings:
    return Settings(invite_token_pepper=pepper, public_url="https://judge.example.test/")


def test_tokens_are_random_and_long() -> None:
    tokens = {new_token() for _ in range(100)}
    assert len(tokens) == 100 and all(len(t) >= 40 for t in tokens)


def test_the_hash_depends_on_the_pepper_and_never_contains_the_token() -> None:
    token = new_token()
    h1 = token_hash(settings(), token)
    assert h1 == token_hash(settings(), token) and len(h1) == 64 and token not in h1
    assert h1 != token_hash(settings("pepper-two-with-at-least-32-bytes-ok"), token)


def test_the_link_points_at_the_take_page() -> None:
    assert link(settings(), "abc") == "https://judge.example.test/take/abc"


def test_the_report_says_signals_are_not_proof() -> None:
    assert "not proof" in SIGNALS_NOTE
