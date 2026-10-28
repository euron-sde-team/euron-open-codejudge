"""Compare a program's output with the expected answer, outside the sandbox.

Built-in checkers follow the Kattis default output validator: output is a sequence of
whitespace separated tokens; ``tokens`` compares them exactly (optionally ignoring case),
``float`` also accepts numbers within an absolute or relative tolerance, and ``exact``
compares bytes after normalising line endings and trailing whitespace at the end of lines
and of the file. Custom checkers are programs (see ``runner``); this module only reads
their verdicts.

Files are compared in streaming chunks, so a 64 MB output does not need 64 MB of tokens in
memory at once.
"""

from __future__ import annotations

import math
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

from codejudge.core.contract import CheckerSpec

CHUNK = 1 << 16
MAX_MESSAGE = 200


@dataclass(frozen=True)
class Check:
    ok: bool
    message: str = ""


def tokens(path: Path) -> Iterator[bytes]:
    """Whitespace separated tokens of a file, read in chunks."""
    rest = b""
    with path.open("rb") as f:
        while chunk := f.read(CHUNK):
            parts = (rest + chunk).split()
            # A token may continue in the next chunk unless the chunk ended in whitespace.
            rest = b"" if chunk[-1:].isspace() else (parts.pop() if parts else b"")
            yield from parts
    if rest:
        yield rest


def _show(token: bytes) -> str:
    text = token[:40].decode("utf-8", errors="replace")
    return text + ("..." if len(token) > 40 else "")


def _numbers_close(expected: bytes, got: bytes, spec: CheckerSpec) -> bool:
    try:
        e, g = float(expected), float(got)
    except ValueError:
        return False
    if math.isnan(e) or math.isnan(g):
        return math.isnan(e) and math.isnan(g)
    if math.isinf(e) or math.isinf(g):
        return e == g
    diff = abs(e - g)
    return diff <= spec.float_abs or diff <= spec.float_rel * abs(e)


def compare_tokens(answer: Path, output: Path, spec: CheckerSpec) -> Check:
    expected, got = tokens(answer), tokens(output)
    position = 0
    while True:
        e, g = next(expected, None), next(got, None)
        position += 1
        if e is None and g is None:
            return Check(True)
        if e is None:
            return Check(False, f"extra output after {position - 1} tokens: {_show(g or b'')}")
        if g is None:
            return Check(False, f"output ended early: expected {_show(e)} at token {position}")
        if e == g or (not spec.case_sensitive and e.lower() == g.lower()):
            continue
        if spec.kind == "float" and _numbers_close(e, g, spec):
            continue
        return Check(False, f"token {position}: expected {_show(e)}, got {_show(g)}")


def _lines(path: Path) -> Iterator[bytes]:
    with path.open("rb") as f:
        for line in f:
            yield line.rstrip(b"\r\n").rstrip()


def compare_exact(answer: Path, output: Path) -> Check:
    """Line by line, ignoring trailing whitespace on each line and blank lines at the end."""
    expected, got = list(_trim_tail(_lines(answer))), _lines(output)
    for number, e in enumerate(expected, start=1):
        g = next(got, None)
        if g is None:
            return Check(False, f"output ended early at line {number}")
        if g != e:
            return Check(False, f"line {number} differs: expected {_show(e)}, got {_show(g)}")
    if any(line for line in got):
        return Check(False, f"extra output after line {len(expected)}")
    return Check(True)


def _trim_tail(lines: Iterator[bytes]) -> list[bytes]:
    out = list(lines)
    while out and not out[-1]:
        out.pop()
    return out


def compare(answer: Path, output: Path, spec: CheckerSpec) -> Check:
    if spec.kind == "exact":
        return compare_exact(answer, output)
    if spec.kind in ("tokens", "float"):
        return compare_tokens(answer, output, spec)
    raise ValueError(f"checker {spec.kind!r} is a program, not a built-in comparison")


# Exit codes of custom checkers. Kattis output validators: 42 accepts, 43 rejects.
# testlib checkers: 0 accepts, 1 wrong answer, 2 presentation error (counted as wrong).
KATTIS_ACCEPT, KATTIS_REJECT = 42, 43


def custom_verdict(protocol: str, exit_code: int | None) -> bool | None:
    """True: accepted; False: wrong answer; None: the checker itself failed (internal error)."""
    if protocol == "kattis":
        return {KATTIS_ACCEPT: True, KATTIS_REJECT: False}.get(exit_code or -1)
    return {0: True, 1: False, 2: False}.get(exit_code if exit_code is not None else -1)


def message(text: str) -> str:
    return text.strip()[:MAX_MESSAGE]
