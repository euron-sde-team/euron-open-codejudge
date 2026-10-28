"""Winnowing (Schleimer, Wilkerson and Aiken, 2003), the algorithm behind MOSS.

Every run of ``K`` consecutive tokens is hashed; in each window of ``W`` consecutive
hashes the smallest one is kept (the rightmost on ties). Any match of at least
``K + W - 1`` tokens is then guaranteed to share a fingerprint, while noise shorter than
``K`` tokens never does. Because fingerprints form a set, moving whole functions around
does not lower the similarity.

Similarity is the Jaccard index of the two fingerprint sets; coverage is the share of each
side's fingerprints found in the other (a short program copied into a long one has high
coverage on the short side). Matches are mapped back to line ranges for the side-by-side
view.
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field

from codejudge.plagiarism.tokens import Token, tokenize

K = 5
W = 4
# Fingerprints a program needs before it is compared at all: tiny programs (a dozen
# tokens) look alike whatever their origin.
MIN_FINGERPRINTS = 6


def _hash(tokens: Sequence[Token]) -> int:
    digest = hashlib.blake2b("\x1f".join(t.text for t in tokens).encode(), digest_size=8)
    return int.from_bytes(digest.digest(), "big")


@dataclass
class Document:
    """One program's fingerprints: hash -> line ranges (first and last line of the k-gram)."""

    key: str
    fingerprints: dict[int, list[tuple[int, int]]] = field(default_factory=dict)

    @property
    def hashes(self) -> set[int]:
        return set(self.fingerprints)


def fingerprint(key: str, source: str, language: str, k: int = K, w: int = W) -> Document:
    tokens = tokenize(source, language)
    doc = Document(key)
    if len(tokens) < k:
        return doc
    grams = [
        (_hash(tokens[i : i + k]), tokens[i].line, tokens[i + k - 1].line)
        for i in range(len(tokens) - k + 1)
    ]
    if len(grams) < w:
        chosen: Iterable[int] = range(len(grams))
    else:
        picked: set[int] = set()
        for start in range(len(grams) - w + 1):
            window = grams[start : start + w]
            low = min(h for h, _, _ in window)
            # Rightmost minimum, as in the paper: consecutive windows then pick the same one.
            offset = max(i for i, (h, _, _) in enumerate(window) if h == low)
            picked.add(start + offset)
        chosen = sorted(picked)
    for i in chosen:
        h, first, last = grams[i]
        doc.fingerprints.setdefault(h, []).append((first, last))
    return doc


def merge(ranges: Iterable[tuple[int, int]]) -> list[tuple[int, int]]:
    """Overlapping or adjacent line ranges joined into one."""
    out: list[tuple[int, int]] = []
    for start, end in sorted(ranges):
        if out and start <= out[-1][1] + 1:
            out[-1] = (out[-1][0], max(out[-1][1], end))
        else:
            out.append((start, end))
    return out


@dataclass(frozen=True)
class Match:
    similarity: float
    coverage_a: float
    coverage_b: float
    ranges_a: list[tuple[int, int]]
    ranges_b: list[tuple[int, int]]


def compare(a: Document, b: Document, ignore: set[int] | None = None) -> Match | None:
    """None when either side has too few fingerprints to judge."""
    ha, hb = a.hashes, b.hashes
    if ignore:
        ha, hb = ha - ignore, hb - ignore
    if len(ha) < MIN_FINGERPRINTS or len(hb) < MIN_FINGERPRINTS:
        return None
    shared = ha & hb
    union = ha | hb
    return Match(
        similarity=round(len(shared) / len(union), 4),
        coverage_a=round(len(shared) / len(ha), 4),
        coverage_b=round(len(shared) / len(hb), 4),
        ranges_a=merge(r for h in shared for r in a.fingerprints[h]),
        ranges_b=merge(r for h in shared for r in b.fingerprints[h]),
    )


def common(documents: Sequence[Document], share: float = 0.6) -> set[int]:
    """Fingerprints in more than ``share`` of the documents: template code everyone was
    given, or the obvious idiom. Ignored only when there are enough documents to tell."""
    if len(documents) < 6:
        return set()
    counts: dict[int, int] = {}
    for d in documents:
        for h in d.hashes:
            counts[h] = counts.get(h, 0) + 1
    limit = share * len(documents)
    return {h for h, n in counts.items() if n > limit}
