"""Output comparison: the Kattis default validator semantics, outside the sandbox."""

from __future__ import annotations

from pathlib import Path

import pytest

from codejudge.core.contract import CheckerSpec
from codejudge.judge import checkers


def files(tmp_path: Path, answer: str | bytes, output: str | bytes) -> tuple[Path, Path]:
    a, o = tmp_path / "answer", tmp_path / "output"
    a.write_bytes(answer if isinstance(answer, bytes) else answer.encode())
    o.write_bytes(output if isinstance(output, bytes) else output.encode())
    return a, o


@pytest.mark.parametrize(
    ("answer", "output", "ok"),
    [
        ("3\n", "3", True),
        ("1 2 3\n", "1\n2\n   3\n\n", True),
        ("1 2 3\n", "1 2", False),
        ("1 2\n", "1 2 3", False),
        ("YES\n", "yes\n", False),
        ("", "", True),
        ("", "\n\n", True),
    ],
)
def test_tokens_ignore_whitespace_only(tmp_path: Path, answer: str, output: str, ok: bool) -> None:
    assert checkers.compare(*files(tmp_path, answer, output), CheckerSpec()).ok is ok


def test_messages_say_where_it_went_wrong(tmp_path: Path) -> None:
    wrong = checkers.compare(*files(tmp_path, "1 2 3", "1 5 3"), CheckerSpec())
    assert "token 2" in wrong.message and "expected 2" in wrong.message and "got 5" in wrong.message
    short = checkers.compare(*files(tmp_path, "1 2", "1"), CheckerSpec())
    assert "ended early" in short.message
    extra = checkers.compare(*files(tmp_path, "1", "1 9"), CheckerSpec())
    assert "extra output" in extra.message


def test_long_tokens_are_shortened_in_messages(tmp_path: Path) -> None:
    check = checkers.compare(*files(tmp_path, "a" * 100, "b" * 100), CheckerSpec())
    assert not check.ok and "..." in check.message and len(check.message) < 200


def test_case_insensitive_mode(tmp_path: Path) -> None:
    spec = CheckerSpec(case_sensitive=False)
    assert checkers.compare(*files(tmp_path, "Yes\n", "YES"), spec).ok


@pytest.mark.parametrize(
    ("answer", "output", "ok"),
    [
        ("3.14159265", "3.1415927", True),  # within 1e-6 absolute
        ("1000000", "1000000.5", True),  # within 1e-6 relative
        ("1.0", "1.1", False),
        ("nan", "nan", True),
        ("nan", "1", False),
        ("inf", "inf", True),
        ("inf", "-inf", False),
        ("1.0", "abc", False),
        ("word", "word", True),  # non numbers still compare as tokens
    ],
)
def test_float_tolerance(tmp_path: Path, answer: str, output: str, ok: bool) -> None:
    spec = CheckerSpec(kind="float", float_abs=1e-6, float_rel=1e-6)
    assert checkers.compare(*files(tmp_path, answer, output), spec).ok is ok


def test_tokens_split_across_read_chunks(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A token cut by a chunk boundary is still one token."""
    monkeypatch.setattr(checkers, "CHUNK", 4)
    numbers = " ".join(str(10**6 + k) for k in range(200))
    assert list(checkers.tokens(files(tmp_path, numbers, "")[0])) == [
        n.encode() for n in numbers.split()
    ]
    assert checkers.compare(*files(tmp_path, numbers, numbers.replace(" ", "\n")), CheckerSpec()).ok
    assert not checkers.compare(*files(tmp_path, numbers, numbers[:-1]), CheckerSpec()).ok


def test_exact_ignores_trailing_whitespace_and_blank_lines_at_the_end(tmp_path: Path) -> None:
    spec = CheckerSpec(kind="exact")
    assert checkers.compare(*files(tmp_path, "a b\nc\n", "a b  \r\nc\n\n\n"), spec).ok
    assert not checkers.compare(*files(tmp_path, "a b\nc\n", "a  b\nc\n"), spec).ok
    ended = checkers.compare(*files(tmp_path, "a\nb\n", "a\n"), spec)
    assert not ended.ok and "line 2" in ended.message
    extra = checkers.compare(*files(tmp_path, "a\n", "a\nb\n"), spec)
    assert not extra.ok and "extra output" in extra.message
    differs = checkers.compare(*files(tmp_path, "a\n", "z\n"), spec)
    assert "line 1 differs" in differs.message


def test_custom_is_not_a_builtin(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="program"):
        checkers.compare(
            *files(tmp_path, "1", "1"), CheckerSpec(kind="custom", language="python3", path="x.py")
        )


@pytest.mark.parametrize(
    ("protocol", "code", "verdict"),
    [
        ("kattis", 42, True),
        ("kattis", 43, False),
        ("kattis", 0, None),  # an exit 0 is not an answer in the Kattis convention
        ("kattis", None, None),
        ("testlib", 0, True),
        ("testlib", 1, False),
        ("testlib", 2, False),
        ("testlib", 3, None),
        ("testlib", None, None),
    ],
)
def test_custom_checker_exit_codes(protocol: str, code: int | None, verdict: bool | None) -> None:
    assert checkers.custom_verdict(protocol, code) is verdict


def test_message_is_trimmed() -> None:
    assert checkers.message("  " + "x" * 500 + "\n") == "x" * checkers.MAX_MESSAGE


def test_tokens_match_split_for_any_chunking(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Linear tokenizing across chunk boundaries gives exactly what bytes.split gives."""
    import random

    rng = random.Random(1)
    f = tmp_path / "f"
    for _ in range(200):
        data = bytes(rng.choice(b"ab \n\t") for _ in range(rng.randint(0, 120)))
        f.write_bytes(data)
        for size in (1, 2, 3, 7, 64):
            monkeypatch.setattr(checkers, "CHUNK", size)
            assert list(checkers.tokens(f)) == data.split()


def test_a_huge_single_token_is_wrong_at_once(tmp_path: Path) -> None:
    (tmp_path / "a").write_bytes(b"x\n")
    (tmp_path / "o").write_bytes(b"x" * (checkers.MAX_TOKEN_BYTES * 3))
    check = checkers.compare_tokens(tmp_path / "a", tmp_path / "o", CheckerSpec())
    assert not check.ok and "longer than" in check.message
