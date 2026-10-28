"""Problem packages: build, import and export in the Kattis problem package format.

The judge reads a package as a zip with ``data/sample/*.in|.ans`` and ``data/secret/**``.
CodeJudge stores exactly that, so the package a problem is judged with is also what it
exports, and a package exported by DOMjudge or Kattis tooling imports unchanged:

    problem.yaml                    name, limits, validation (Kattis keys)
    problem_statement/problem.md    statement (Markdown; problem.en.md also read)
    data/sample/<n>.in|.ans         public samples
    data/secret/[<group>/]<n>.in|.ans
    data/secret/<group>/test_group.yaml (or testdata.yaml)  score for IOI style groups
    output_validators/<name>/<file> custom checker source (Kattis convention)
    submissions/accepted/<file>     reference solutions (imported as expected AC)

Builds are deterministic (sorted entries, fixed timestamps), so the same tests give the
same SHA-256 and re-uploading identical data creates no new version.
"""

from __future__ import annotations

import hashlib
import io
import re
import zipfile
from dataclasses import dataclass, field
from pathlib import PurePosixPath
from typing import Any

import yaml

from codejudge.core.contract import CheckerSpec, GroupSpec, TestSpec

FIXED_TIME = (2026, 1, 1, 0, 0, 0)
SAMPLE_PREVIEW_BYTES = 64_000
MAX_ENTRIES = 20_000

LANGUAGE_BY_SUFFIX = {
    ".py": "python3",
    ".cpp": "cpp17",
    ".cc": "cpp17",
    ".java": "java21",
    ".js": "javascript",
}


class PackageFormatError(ValueError):
    pass


@dataclass
class Test:
    name: str  # relative to data/, without extension: "sample/1", "secret/g1/03"
    group: str
    sample: bool
    input: bytes
    answer: bytes


@dataclass
class Package:
    title: str = ""
    statement_md: str = ""
    time_limit_ms: int | None = None
    memory_limit_mb: int | None = None
    source: str | None = None
    license: str | None = None
    tests: list[Test] = field(default_factory=list)
    groups: list[GroupSpec] = field(default_factory=list)
    checker: CheckerSpec = field(default_factory=CheckerSpec)
    checker_source: bytes | None = None
    references: list[tuple[str, str, str]] = field(default_factory=list)  # (name, language, source)

    def test_specs(self) -> list[TestSpec]:
        return [TestSpec(name=t.name, group=t.group, sample=t.sample) for t in self.tests]


# ── build ────────────────────────────────────────────────────────────────────────────
def build(pkg: Package) -> bytes:
    """The zip the judge reads (and the problem exports), deterministic for equal input."""
    entries: dict[str, bytes] = {}
    meta: dict[str, Any] = {"name": pkg.title or "untitled"}
    if pkg.source:
        meta["source"] = pkg.source
    if pkg.license:
        meta["license"] = pkg.license
    limits: dict[str, Any] = {}
    if pkg.time_limit_ms:
        limits["time_limit"] = pkg.time_limit_ms / 1000
    if pkg.memory_limit_mb:
        limits["memory"] = pkg.memory_limit_mb
    if limits:
        meta["limits"] = limits
    scored = any(g.name != "secret" for g in pkg.groups if g.name != "sample")
    if scored:
        meta["type"] = "scoring"
    if pkg.checker.kind == "custom":
        meta["validation"] = "custom"
    elif pkg.checker.kind == "float":
        meta["validator_flags"] = (
            f"float_absolute_tolerance {pkg.checker.float_abs} "
            f"float_relative_tolerance {pkg.checker.float_rel}"
        )
    elif not pkg.checker.case_sensitive:
        meta["validator_flags"] = "case_insensitive"
    entries["problem.yaml"] = yaml.safe_dump(meta, sort_keys=True).encode()
    if pkg.statement_md:
        entries["problem_statement/problem.md"] = pkg.statement_md.encode()
    for t in pkg.tests:
        entries[f"data/{t.name}.in"] = t.input
        entries[f"data/{t.name}.ans"] = t.answer
    for g in pkg.groups:
        if g.name not in ("sample", "secret"):
            entries[f"data/secret/{g.name}/test_group.yaml"] = yaml.safe_dump(
                {"score": g.points}
            ).encode()
    if pkg.checker.kind == "custom" and pkg.checker_source is not None and pkg.checker.path:
        entries[pkg.checker.path] = pkg.checker_source
    for name, language, src in pkg.references:
        suffix = next((s for s, lang in LANGUAGE_BY_SUFFIX.items() if lang == language), ".txt")
        entries[f"submissions/accepted/{_safe(name)}{suffix}"] = src.encode()
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for name in sorted(entries):
            info = zipfile.ZipInfo(name, date_time=FIXED_TIME)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            z.writestr(info, entries[name])
    return buf.getvalue()


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _safe(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9_\-]+", "_", name).strip("_")[:60] or "solution"


# ── import ───────────────────────────────────────────────────────────────────────────
def parse(data: bytes) -> Package:
    """Read a Kattis style package (zip). Accepts a single top-level folder around it."""
    try:
        archive = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile as exc:
        raise PackageFormatError("not a zip file") from exc
    with archive:
        infos = [i for i in archive.infolist() if not i.is_dir()]
        if len(infos) > MAX_ENTRIES:
            raise PackageFormatError(f"too many files ({len(infos)})")
        names = [i.filename for i in infos]
        for name in names:
            path = PurePosixPath(name)
            if path.is_absolute() or ".." in path.parts:
                raise PackageFormatError(f"unsafe path {name!r}")
        prefix = _common_prefix(names)
        files = {n[len(prefix) :]: n for n in names if not PurePosixPath(n).name.startswith(".")}

        def read(name: str) -> bytes:
            return archive.read(files[name])

        pkg = Package()
        meta: dict[str, Any] = {}
        if "problem.yaml" in files:
            loaded = yaml.safe_load(read("problem.yaml")) or {}
            if not isinstance(loaded, dict):
                raise PackageFormatError("problem.yaml must be a mapping")
            meta = loaded
        title: Any = meta.get("name")
        pkg.title = str(
            (title.get("en") if isinstance(title, dict) else title)
            or prefix.strip("/")
            or "Imported problem"
        )
        pkg.source = _str(meta.get("source"))
        pkg.license = _str(meta.get("license"))
        limits = meta.get("limits") or {}
        if isinstance(limits, dict):
            if "time_limit" in limits:
                pkg.time_limit_ms = round(float(limits["time_limit"]) * 1000)
            if "memory" in limits:
                pkg.memory_limit_mb = int(limits["memory"])
        for candidate in (
            "problem_statement/problem.md",
            "problem_statement/problem.en.md",
            "statement/problem.en.md",
            "statement/problem.md",
        ):
            if candidate in files:
                pkg.statement_md = read(candidate).decode("utf-8", errors="replace")
                break
        pkg.checker = _checker(meta, files)
        if pkg.checker.kind == "custom" and pkg.checker.path:
            pkg.checker_source = read(pkg.checker.path)

        pkg.tests, pkg.groups = _tests(
            files,
            read,
            scoring=meta.get("type") == "scoring" or "scoring" in str(meta.get("type", "")),
        )
        if not pkg.tests:
            raise PackageFormatError("the package has no tests under data/sample or data/secret")
        for fname in sorted(files):
            parts = PurePosixPath(fname).parts
            if len(parts) == 3 and parts[0] == "submissions" and parts[1] == "accepted":
                language = LANGUAGE_BY_SUFFIX.get(PurePosixPath(fname).suffix)
                if language:
                    pkg.references.append(
                        (
                            PurePosixPath(fname).stem,
                            language,
                            read(fname).decode("utf-8", errors="replace"),
                        )
                    )
        return pkg


def _str(v: object) -> str | None:
    return str(v)[:200] if v else None


def _common_prefix(names: list[str]) -> str:
    """``myproblem/`` when every entry sits in one top-level folder, else ``""``."""
    firsts = {n.split("/", 1)[0] for n in names}
    if len(firsts) == 1 and all("/" in n for n in names):
        top = next(iter(firsts))
        # "data" or "problem_statement" alone at the top is the package itself, not a wrapper.
        if top not in ("data", "problem_statement", "output_validators", "submissions"):
            return top + "/"
    return ""


def _checker(meta: dict[str, Any], files: dict[str, str]) -> CheckerSpec:
    validation = str(meta.get("validation", "default"))
    if "custom" in validation:
        sources = sorted(
            n
            for n in files
            if n.startswith("output_validators/") and PurePosixPath(n).suffix in LANGUAGE_BY_SUFFIX
        )
        if not sources:
            raise PackageFormatError(
                "validation is custom but output_validators/ has no source in a supported language"
            )
        path = sources[0]
        return CheckerSpec(
            kind="custom",
            language=LANGUAGE_BY_SUFFIX[PurePosixPath(path).suffix],
            path=path,
            protocol="kattis",
        )
    flags = str(meta.get("validator_flags", "")).split()
    spec = CheckerSpec(kind="tokens", case_sensitive="case_insensitive" not in flags)
    for i, flag in enumerate(flags):
        if flag in (
            "float_tolerance",
            "float_absolute_tolerance",
            "float_relative_tolerance",
        ) and i + 1 < len(flags):
            value = float(flags[i + 1])
            spec.kind = "float"
            if flag in ("float_tolerance", "float_absolute_tolerance"):
                spec.float_abs = value
            if flag in ("float_tolerance", "float_relative_tolerance"):
                spec.float_rel = value
    return spec


def _tests(
    files: dict[str, str], read: Any, *, scoring: bool
) -> tuple[list[Test], list[GroupSpec]]:
    inputs = sorted(n for n in files if n.startswith("data/") and n.endswith(".in"))
    tests: list[Test] = []
    group_order: list[str] = []
    for path in inputs:
        stem = path[len("data/") : -len(".in")]
        answer = f"data/{stem}.ans"
        if answer not in files:
            continue
        parts = stem.split("/")
        if parts[0] not in ("sample", "secret"):
            continue
        group = "sample" if parts[0] == "sample" else (parts[1] if len(parts) > 2 else "secret")
        if group not in group_order:
            group_order.append(group)
        tests.append(
            Test(
                name=stem,
                group=group,
                sample=parts[0] == "sample",
                input=read(path),
                answer=read(answer),
            )
        )
    # Samples first, then hidden groups in name order (Kattis judges in lexicographic order).
    tests.sort(key=lambda t: (not t.sample, _natural(t.name)))
    groups: list[GroupSpec] = []
    hidden = [g for g in group_order if g != "sample"]
    if "sample" in group_order:
        groups.append(GroupSpec(name="sample", points=0, stop_on_failure=False))
    explicit: dict[str, float] = {}
    for g in hidden:
        for meta_name in (f"data/secret/{g}/test_group.yaml", f"data/secret/{g}/testdata.yaml"):
            if meta_name in files:
                loaded = yaml.safe_load(read(meta_name)) or {}
                if isinstance(loaded, dict) and "score" in loaded:
                    explicit[g] = float(str(loaded["score"]).split()[0])
    if hidden:
        # A scoring package names each group's points; groups it leaves out score nothing.
        default = 0.0 if scoring and explicit else round(100 / len(hidden), 4)
        for g in sorted(hidden, key=_natural):
            groups.append(GroupSpec(name=g, points=explicit.get(g, default)))
    return tests, groups


def _natural(text: str) -> list[object]:
    return [int(p) if p.isdigit() else p for p in re.split(r"(\d+)", text)]


def samples(pkg: Package) -> list[dict[str, str]]:
    """Sample tests as text for the statement page, size bounded."""
    out = []
    for t in pkg.tests:
        if t.sample:
            out.append(
                {
                    "name": t.name,
                    "input": t.input[:SAMPLE_PREVIEW_BYTES].decode("utf-8", errors="replace"),
                    "output": t.answer[:SAMPLE_PREVIEW_BYTES].decode("utf-8", errors="replace"),
                }
            )
    return out
