"""The hint prompt and the rules that decide whether a hint may be asked for at all."""

from __future__ import annotations

import uuid

import pytest

from codejudge.core.contexts import Submitter
from codejudge.hints.service import build_messages, refusal
from codejudge.org.models import OrgSettings

STUDENT = Submitter(user_id=uuid.uuid4(), candidate_id=None, role="student")
CANDIDATE = Submitter(user_id=None, candidate_id=uuid.uuid4(), role="candidate")


def settings(**values: object) -> OrgSettings:
    base: dict[str, object] = {
        "ai_enabled": True,
        "ai_base_url": "http://ollama:11434/v1",
        "ai_model": "qwen",
        "ai_max_hints_per_problem": 3,
        "ai_allowed_in_practice": True,
        "ai_allowed_in_assignments": False,
    }
    base.update(values)
    return OrgSettings(**base)


def test_a_hidden_failing_test_is_named_but_never_shown() -> None:
    messages = build_messages(
        title="Sum",
        statement="Add two numbers.",
        samples=[{"name": "sample/1", "input": "1 2\n", "output": "3\n"}],
        language="python3",
        source="print(0)",
        verdict="WA",
        failing_test="secret/7",
        compile_output=None,
        question=None,
    )
    text = messages[1]["content"]
    assert messages[0]["role"] == "system" and "not" in messages[0]["content"]
    assert "secret/7" in text and "hidden test; its data is not available" in text
    assert "1 2" in text and "print(0)" in text and "Give a hint." in text


def test_long_inputs_are_truncated() -> None:
    text = build_messages(
        title="T", statement="s" * 50_000, samples=[], language="cpp17", source="x" * 50_000,
        verdict="CE", failing_test=None, compile_output="e" * 10_000, question="why?",
    )[1]["content"]  # fmt: skip
    assert len(text) < 25_000 and "The student asks: why?" in text


@pytest.mark.parametrize(
    ("values", "who", "context", "code"),
    [
        ({"ai_enabled": False}, STUDENT, "practice", "ai_disabled"),
        ({"ai_base_url": None}, STUDENT, "practice", "ai_disabled"),
        ({"ai_max_hints_per_problem": 0}, STUDENT, "practice", "ai_disabled"),
        ({}, STUDENT, "contest", "ai_not_allowed"),
        ({}, STUDENT, "assessment", "ai_not_allowed"),
        ({}, CANDIDATE, "practice", "ai_not_allowed"),
        ({}, STUDENT, "assignment", "ai_not_allowed"),
        ({"ai_allowed_in_practice": False}, STUDENT, "practice", "ai_not_allowed"),
    ],
)
def test_refusals(values: dict[str, object], who: Submitter, context: str, code: str) -> None:
    why = refusal(settings(**values), who, context)
    assert why is not None and why[0] == code


def test_allowed_where_the_settings_allow() -> None:
    assert refusal(settings(), STUDENT, "practice") is None
    assert refusal(settings(ai_allowed_in_assignments=True), STUDENT, "assignment") is None
    # Contests stay closed whatever the settings say.
    assert refusal(settings(ai_allowed_in_assignments=True), STUDENT, "contest") is not None
