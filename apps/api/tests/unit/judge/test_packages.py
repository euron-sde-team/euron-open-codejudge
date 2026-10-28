"""Test packages on the worker: safe unpacking, verification by hash, the shared cache."""

from __future__ import annotations

import hashlib
import io
import stat
import zipfile
from pathlib import Path

import pytest

from codejudge.judge import packages
from codejudge.judge.packages import PackageCache, PackageError


def zip_of(entries: dict[str, bytes], *, link: str | None = None) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for name, data in entries.items():
            z.writestr(name, data)
        if link:
            info = zipfile.ZipInfo(link)
            info.external_attr = (stat.S_IFLNK | 0o777) << 16
            z.writestr(info, "/etc/passwd")
    return buf.getvalue()


GOOD = {
    "data/sample/1.in": b"1 2\n",
    "data/sample/1.ans": b"3\n",
    "data/secret/g1/01.in": b"4 5\n",
    "data/secret/g1/01.ans": b"9\n",
}


class Store:
    def __init__(self) -> None:
        self.blobs: dict[str, bytes] = {}
        self.fetches = 0

    def add(self, data: bytes) -> str:
        sha = hashlib.sha256(data).hexdigest()
        self.blobs[sha] = data
        return sha

    def fetch(self, sha: str, dest: Path) -> None:
        self.fetches += 1
        dest.write_bytes(self.blobs[sha])


@pytest.mark.parametrize(
    "bad", ["/etc/cron.d/x", "../escape.in", "data/../../escape.in", "data\\secret\\1.in"]
)
def test_unsafe_paths_are_refused(tmp_path: Path, bad: str) -> None:
    (tmp_path / "p.zip").write_bytes(zip_of({**GOOD, bad: b"x"}))
    with pytest.raises(PackageError, match="unsafe path"):
        packages.unpack(tmp_path / "p.zip", tmp_path / "out")


def test_symlinks_are_refused(tmp_path: Path) -> None:
    (tmp_path / "p.zip").write_bytes(zip_of(GOOD, link="data/secret/link.in"))
    with pytest.raises(PackageError, match="not a plain file"):
        packages.unpack(tmp_path / "p.zip", tmp_path / "out")


def test_too_many_entries_and_too_large_are_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "p.zip").write_bytes(zip_of(GOOD))
    monkeypatch.setattr(packages, "MAX_ENTRIES", 2)
    with pytest.raises(PackageError, match="entries"):
        packages.unpack(tmp_path / "p.zip", tmp_path / "out")
    monkeypatch.setattr(packages, "MAX_ENTRIES", 100)
    monkeypatch.setattr(packages, "MAX_UNPACKED_BYTES", 5)
    with pytest.raises(PackageError, match="size limit"):
        packages.unpack(tmp_path / "p.zip", tmp_path / "out2")


def test_unpacked_files_are_read_only(tmp_path: Path) -> None:
    (tmp_path / "p.zip").write_bytes(zip_of({**GOOD, "data/secret/": b""}))
    packages.unpack(tmp_path / "p.zip", tmp_path / "out")
    f = tmp_path / "out/data/sample/1.in"
    assert f.read_bytes() == b"1 2\n" and not (f.stat().st_mode & 0o222)


def test_the_cache_fetches_once_and_verifies_the_hash(tmp_path: Path) -> None:
    store = Store()
    sha = store.add(zip_of(GOOD))
    cache = PackageCache(tmp_path / "cache", 10_000_000, store.fetch)
    first = cache.get(sha)
    assert (first / "data/secret/g1/01.ans").read_bytes() == b"9\n"
    assert cache.get(sha) == first and store.fetches == 1
    assert not list((tmp_path / "cache").glob(".*.zip")), "the download is removed after unpacking"


def test_a_tampered_package_is_refused_and_not_cached(tmp_path: Path) -> None:
    store = Store()
    sha = store.add(zip_of(GOOD))
    store.blobs[sha] = zip_of({**GOOD, "data/secret/g1/01.ans": b"0\n"})
    cache = PackageCache(tmp_path / "cache", 10_000_000, store.fetch)
    with pytest.raises(PackageError, match="checksum mismatch"):
        cache.get(sha)
    assert not (tmp_path / "cache" / sha).exists()


def test_least_recently_used_packages_are_evicted(tmp_path: Path) -> None:
    store = Store()
    shas = [
        store.add(zip_of({**GOOD, "data/secret/g1/01.in": bytes(4000) + bytes([k])}))
        for k in range(3)
    ]
    cache = PackageCache(tmp_path / "cache", 9000, store.fetch)
    for sha in shas:
        cache.get(sha)
    kept = {p.name for p in (tmp_path / "cache").iterdir() if not p.name.startswith(".")}
    assert shas[-1] in kept and shas[0] not in kept


def test_test_files_resolve_inside_the_package(tmp_path: Path) -> None:
    (tmp_path / "p.zip").write_bytes(zip_of(GOOD))
    packages.unpack(tmp_path / "p.zip", tmp_path / "pkg")
    inp, ans = packages.test_files(tmp_path / "pkg", "secret/g1/01")
    assert inp.read_bytes() == b"4 5\n" and ans.read_bytes() == b"9\n"
    with pytest.raises(PackageError, match="missing"):
        packages.test_files(tmp_path / "pkg", "secret/g1/02")
    (tmp_path / "outside.in").write_bytes(b"x")
    (tmp_path / "outside.ans").write_bytes(b"x")
    with pytest.raises(PackageError, match="outside"):
        packages.test_files(tmp_path / "pkg", "../../outside")


def test_sha256_of_a_file(tmp_path: Path) -> None:
    (tmp_path / "f").write_bytes(b"abc")
    assert packages.sha256_file(tmp_path / "f") == hashlib.sha256(b"abc").hexdigest()


def test_a_failed_download_leaves_nothing_behind_and_space_is_made_first(tmp_path: Path) -> None:
    from codejudge.judge.packages import PackageCache

    def broken(sha: str, dest: Path) -> None:
        dest.write_bytes(b"partial")
        raise OSError("connection reset")

    cache = PackageCache(tmp_path / "cache", 10_000, broken)
    stale = tmp_path / "cache" / ("b" * 64)
    stale.mkdir()
    (stale / "data").write_bytes(b"x" * 9_000)
    with pytest.raises(OSError, match="connection reset"):
        cache.get("a" * 64)
    leftovers = [p.name for p in (tmp_path / "cache").iterdir()]
    assert leftovers == [], leftovers  # the partial download is gone, the old package evicted
