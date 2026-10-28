"""Problem management paths: server limits, editing, test content, checkers, import warnings."""

from __future__ import annotations

import io
import zipfile

import pytest
import yaml

from tests.integration.conftest import Stack, make_problem

pytestmark = pytest.mark.asyncio

CHECKER = "import sys\nsys.exit(42)\n"


async def test_the_server_limits_apply_to_every_problem(stack: Stack) -> None:
    too_slow = await stack.client.post(
        "/api/v1/problems", json={"slug": "slow", "title": "Slow", "time_limit_ms": 20_000}
    )
    assert too_slow.status_code == 400 and too_slow.json()["error"]["code"] == "limit_too_high"
    too_big = await stack.client.post(
        "/api/v1/problems", json={"slug": "big", "title": "Big", "memory_limit_mb": 4096}
    )
    assert too_big.json()["error"]["code"] == "limit_too_high"
    p = await stack.ok("POST", "/api/v1/problems", {"slug": "fine", "title": "Fine"}, status=201)
    edit = await stack.client.patch(f"/api/v1/problems/{p['id']}", json={"time_limit_ms": 20_000})
    assert edit.status_code == 400 and edit.json()["error"]["code"] == "limit_too_high"


async def test_editing_publishing_and_deleting(stack: Stack) -> None:
    a = await make_problem(stack, "first")
    b = await make_problem(stack, "second", publish=False)
    clash = await stack.client.patch(f"/api/v1/problems/{b['id']}", json={"slug": "first"})
    assert clash.status_code == 409 and clash.json()["error"]["code"] == "slug_taken"
    taken = await stack.client.post("/api/v1/problems", json={"slug": "first", "title": "Again"})
    assert taken.status_code == 409
    renamed = await stack.ok(
        "PATCH",
        f"/api/v1/problems/{b['id']}",
        {"title": "Second, renamed", "tags": ["Graphs", "graphs", " dp "]},
    )
    assert renamed["title"] == "Second, renamed" and renamed["tags"] == ["graphs", "dp"]
    await stack.ok("POST", f"/api/v1/problems/{a['id']}/unpublish")
    student = await stack.user()
    assert (await student.get("/api/v1/problems/first")).status_code == 404
    assert (await stack.client.delete(f"/api/v1/problems/{a['id']}")).status_code == 204
    assert (await stack.client.get(f"/api/v1/problems/{a['id']}")).status_code == 404
    assert (await stack.client.get("/api/v1/problems/no-such-slug")).status_code == 404


async def test_lists_filter_by_text_tag_difficulty_and_status(stack: Stack) -> None:
    await make_problem(stack, "alpha")
    await make_problem(stack, "beta", publish=False)
    p = await stack.ok("GET", "/api/v1/problems/alpha")
    await stack.ok("PATCH", f"/api/v1/problems/{p['id']}", {"tags": ["math"], "difficulty": "hard"})
    assert [x["slug"] for x in (await stack.ok("GET", "/api/v1/problems?q=alp"))["items"]] == [
        "alpha"
    ]
    assert [x["slug"] for x in (await stack.ok("GET", "/api/v1/problems?tag=math"))["items"]] == [
        "alpha"
    ]
    assert [
        x["slug"] for x in (await stack.ok("GET", "/api/v1/problems?difficulty=hard"))["items"]
    ] == ["alpha"]
    assert [
        x["slug"] for x in (await stack.ok("GET", "/api/v1/problems?status=draft"))["items"]
    ] == ["beta"]
    async with stack.anonymous() as anon:
        listed = (await anon.get("/api/v1/problems")).json()
        assert [x["slug"] for x in listed["items"]] == ["alpha"] and listed["items"][0][
            "mine"
        ] is None
        tags = (await anon.get("/api/v1/problem-tags")).json()
        assert tags == [{"tag": "math", "problems": 1}]
        languages = (await anon.get("/api/v1/languages")).json()
        assert {lang["id"] for lang in languages} == {"python3", "cpp17", "java21", "javascript"}


async def test_staff_read_test_content_and_others_cannot(stack: Stack) -> None:
    p = await make_problem(stack)
    resp = await stack.client.get(
        f"/api/v1/problems/{p['id']}/tests/secret/1", params={"part": "answer"}
    )
    assert (
        resp.status_code == 200
        and resp.text == "42\n"
        and resp.headers["cache-control"] == "no-store"
    )
    assert (await stack.client.get(f"/api/v1/problems/{p['id']}/tests/secret/1")).text == "40 2\n"
    assert (
        await stack.client.get(f"/api/v1/problems/{p['id']}/tests/secret/99")
    ).status_code == 404


async def test_a_custom_checker_survives_new_versions_and_export(stack: Stack) -> None:
    p = await stack.ok(
        "POST", "/api/v1/problems", {"slug": "anyans", "title": "Any Answer"}, status=201
    )
    tests = [
        {"name": "sample/1", "input": "1\n", "answer": "1\n"},
        {"name": "secret/1", "input": "2\n", "answer": "2\n"},
    ]
    missing = await stack.client.post(
        f"/api/v1/problems/{p['id']}/versions",
        json={"tests": tests, "checker": {"kind": "custom", "language": "python3"}},
    )
    assert (
        missing.status_code == 400 and missing.json()["error"]["code"] == "checker_source_required"
    )
    await stack.ok(
        "POST",
        f"/api/v1/problems/{p['id']}/versions",
        {
            "tests": tests,
            "checker": {"kind": "custom", "language": "python3"},
            "checker_source": CHECKER,
        },
        status=201,
    )
    # A later version without new checker source keeps the stored one.
    v2 = await stack.ok(
        "POST",
        f"/api/v1/problems/{p['id']}/versions",
        {"tests": [*tests, {"name": "secret/2", "input": "3\n", "answer": "3\n"}]},
        status=201,
    )
    assert v2["number"] == 2 and v2["checker"]["kind"] == "custom"
    exported = (await stack.client.get(f"/api/v1/problems/{p['id']}/export")).content
    z = zipfile.ZipFile(io.BytesIO(exported))
    assert z.read("output_validators/checker/checker.py").decode() == CHECKER
    assert yaml.safe_load(z.read("problem.yaml"))["validation"] == "custom"
    dup = await stack.client.post(
        f"/api/v1/problems/{p['id']}/versions", json={"tests": [tests[0], tests[0]]}
    )
    assert dup.status_code == 400 and dup.json()["error"]["code"] == "duplicate_test"
    only_samples = await stack.client.post(
        f"/api/v1/problems/{p['id']}/versions", json={"tests": [tests[0]]}
    )
    assert only_samples.json()["error"]["code"] == "no_hidden_tests"


async def test_an_import_clamps_limits_and_says_so(stack: Stack) -> None:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr(
            "big/problem.yaml",
            yaml.safe_dump(
                {
                    "name": {"en": "Big Limits"},
                    "limits": {"time_limit": 30, "memory": 512},
                    "validator_flags": "float_tolerance 0.001",
                }
            ),
        )
        z.writestr("big/problem_statement/problem.en.md", "A statement.")
        z.writestr("big/data/secret/a/1.in", "1")
        z.writestr("big/data/secret/a/1.ans", "1")
        z.writestr("big/data/secret/a/test_group.yaml", "score: 70")
        z.writestr("big/data/secret/b/1.in", "2")
        z.writestr("big/data/secret/b/1.ans", "2")
        z.writestr("big/data/secret/b/test_group.yaml", "score: 30")
    first = await stack.client.post(
        "/api/v1/problems/import", files={"file": ("big.zip", buf.getvalue(), "application/zip")}
    )
    assert first.status_code == 201, first.text
    body = first.json()
    assert any("Time limit lowered" in w for w in body["warnings"])
    admin = await stack.ok("GET", f"/api/v1/problems/{body['problem']['id']}/admin")
    assert (
        admin["time_limit_ms"] == stack.settings.max_time_limit_ms
        and admin["statement_md"] == "A statement."
    )
    assert admin["checker"] == "float"
    assert {g["name"]: g["points"] for g in admin["groups"]} == {"a": 70, "b": 30}
    again = await stack.client.post(
        "/api/v1/problems/import", files={"file": ("big.zip", buf.getvalue(), "application/zip")}
    )
    assert any("was taken" in w for w in again.json()["warnings"])
    bad = await stack.client.post(
        "/api/v1/problems/import", files={"file": ("x.zip", b"not a zip", "application/zip")}
    )
    assert bad.status_code == 400
    empty = io.BytesIO()
    with zipfile.ZipFile(empty, "w") as z:
        z.writestr("problem.yaml", "name: Empty")
    no_tests = await stack.client.post(
        "/api/v1/problems/import", files={"file": ("e.zip", empty.getvalue(), "application/zip")}
    )
    assert no_tests.status_code == 400 and "no tests" in no_tests.json()["error"]["message"]


async def test_replacing_tests_from_a_package_keeps_the_statement(stack: Stack) -> None:
    p = await make_problem(stack)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("data/sample/1.in", "2 2\n")
        z.writestr("data/sample/1.ans", "4\n")
        z.writestr("data/secret/1.in", "5 5\n")
        z.writestr("data/secret/1.ans", "10\n")
    v = await stack.client.post(
        f"/api/v1/problems/{p['id']}/package",
        files={"file": ("p.zip", buf.getvalue(), "application/zip")},
    )
    assert v.status_code == 201 and v.json()["number"] == 2
    detail = await stack.ok("GET", "/api/v1/problems/sum")
    assert detail["statement_md"] == "Add two numbers." and detail["samples"][0]["input"] == "2 2\n"
    assert detail["version"] == 2
    bad = await stack.client.post(
        f"/api/v1/problems/{p['id']}/package", files={"file": ("p.zip", b"nope", "application/zip")}
    )
    assert bad.status_code == 400 and bad.json()["error"]["code"] == "bad_package"


async def test_references_are_managed_and_validated(stack: Stack) -> None:
    p = await make_problem(stack, publish=False)
    bad = await stack.client.post(
        f"/api/v1/problems/{p['id']}/references",
        json={"name": "x", "language": "cobol", "source": "x"},
    )
    assert bad.status_code == 400 and bad.json()["error"]["code"] == "unknown_language"
    ref = await stack.ok(
        "POST",
        f"/api/v1/problems/{p['id']}/references",
        {"name": "slow", "language": "cpp17", "source": "int main(){}", "expected": "TLE"},
        status=201,
    )
    assert (
        await stack.client.delete(f"/api/v1/problems/{p['id']}/references/{ref['id']}")
    ).status_code == 204
    assert (
        await stack.client.delete(f"/api/v1/problems/{p['id']}/references/{ref['id']}")
    ).status_code == 404
    await stack.ok("POST", f"/api/v1/problems/{p['id']}/references/judge")
    queued = await stack.ok("POST", f"/api/v1/problems/{p['id']}/rejudge")
    assert queued["queued"] >= 1
    no_tests = await stack.ok(
        "POST", "/api/v1/problems", {"slug": "empty", "title": "Empty"}, status=201
    )
    assert (await stack.client.get(f"/api/v1/problems/{no_tests['id']}/export")).json()["error"][
        "code"
    ] == "no_tests"
    blocked = await stack.ok("GET", f"/api/v1/problems/{no_tests['id']}/admin")
    assert "add tests" in blocked["publish_blockers"]
