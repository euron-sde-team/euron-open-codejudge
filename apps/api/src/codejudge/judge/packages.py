"""Test packages on the worker: fetched by SHA-256, verified, unpacked once, reused.

A package is a zip in the Kattis problem package layout (``data/sample/*.in|.ans``,
``data/secret/**/*.in|.ans``, optional checker sources). The worker fetches it from the
API's internal endpoint (it has no storage credentials), refuses it unless its SHA-256
matches the job, unpacks it into ``<cache>/<sha256>/`` through a temporary directory and an
atomic rename, and evicts the least recently used packages beyond the cache budget.

Unpacking refuses absolute paths, ``..``, symlinks and devices, and caps entry count and
total size, so a hostile or broken archive cannot write outside its directory or fill the
disk.
"""

from __future__ import annotations

import hashlib
import os
import shutil
import stat
import threading
import zipfile
from collections.abc import Callable
from pathlib import Path, PurePosixPath

MAX_ENTRIES = 20_000
MAX_UNPACKED_BYTES = 2_000_000_000


class PackageError(Exception):
    pass


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def safe_members(archive: zipfile.ZipFile) -> list[zipfile.ZipInfo]:
    members = archive.infolist()
    if len(members) > MAX_ENTRIES:
        raise PackageError(f"package has {len(members)} entries (limit {MAX_ENTRIES})")
    total = 0
    for info in members:
        name = PurePosixPath(info.filename)
        if name.is_absolute() or ".." in name.parts or "\\" in info.filename:
            raise PackageError(f"unsafe path in package: {info.filename!r}")
        mode = info.external_attr >> 16
        if mode and not (stat.S_ISREG(mode) or stat.S_ISDIR(mode)):
            raise PackageError(f"package entry is not a plain file: {info.filename!r}")
        total += info.file_size
        if total > MAX_UNPACKED_BYTES:
            raise PackageError("package unpacks to more than the size limit")
    return members


def unpack(archive_path: Path, target: Path) -> None:
    with zipfile.ZipFile(archive_path) as archive:
        for info in safe_members(archive):
            dest = target / info.filename
            if info.is_dir():
                dest.mkdir(parents=True, exist_ok=True)
                continue
            dest.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(info) as src, dest.open("wb") as out:
                shutil.copyfileobj(src, out, 1 << 20)
            dest.chmod(0o444)


class PackageCache:
    """Unpacked packages by SHA-256, shared by the jobs of one worker."""

    def __init__(self, root: str | Path, max_bytes: int, fetch: Callable[[str, Path], None]):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.max_bytes = max_bytes
        self._fetch = fetch
        self._lock = threading.Lock()

    def get(self, sha256: str) -> Path:
        """The unpacked package directory, fetching and verifying it on first use."""
        with self._lock:
            target = self.root / sha256
            if (target / ".complete").exists():
                os.utime(target)
                return target
            download = self.root / f".{sha256}.zip"
            self._fetch(sha256, download)
            try:
                got = sha256_file(download)
                if got != sha256:
                    raise PackageError(f"package checksum mismatch: wanted {sha256}, got {got}")
                staging = self.root / f".{sha256}.tmp"
                shutil.rmtree(staging, ignore_errors=True)
                staging.mkdir()
                unpack(download, staging)
                (staging / ".complete").touch()
                shutil.rmtree(target, ignore_errors=True)
                staging.rename(target)
            finally:
                download.unlink(missing_ok=True)
            self._evict(keep=sha256)
            return target

    def _evict(self, keep: str) -> None:
        entries = [p for p in self.root.iterdir() if p.is_dir() and not p.name.startswith(".")]
        sizes = {p: _size(p) for p in entries}
        total = sum(sizes.values())
        for p in sorted(entries, key=lambda e: e.stat().st_mtime):
            if total <= self.max_bytes:
                break
            if p.name == keep:
                continue
            total -= sizes[p]
            shutil.rmtree(p, ignore_errors=True)


def _size(path: Path) -> int:
    return sum(f.stat().st_size for f in path.rglob("*") if f.is_file())


def test_files(package: Path, name: str) -> tuple[Path, Path]:
    """The input and answer of a test named like ``sample/1`` or ``secret/group1/07``."""
    base = package / "data" / name
    inp, ans = base.with_name(base.name + ".in"), base.with_name(base.name + ".ans")
    if not inp.is_file() or not ans.is_file():
        raise PackageError(f"test {name!r} is missing its .in or .ans file")
    if package.resolve() not in inp.resolve().parents:
        raise PackageError(f"test {name!r} points outside the package")
    return inp, ans
