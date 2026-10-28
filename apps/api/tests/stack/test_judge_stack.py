"""Acceptance tests against the running stack with the REAL judge workers (make test-stack).

    make up && make test-stack

AC5: a judge worker killed in the middle of a job does not lose it: another worker claims
it after the lease and judges it, and the verdict is applied exactly once.
AC12: a burst of submissions (correct, wrong, slow and hostile ones mixed) across the
workers all get their right verdicts; a hostile program does not change anyone else's.
AC13: the five-minute path: create a problem, add tests and a solution, publish, submit,
and get a verdict from the real sandbox.

They talk to the API on the published port and use the docker CLI only to kill a judge
container (AC5); they never touch any other container.
"""

from __future__ import annotations

import asyncio
import os
import shutil
import time
import uuid
from pathlib import Path
from typing import Any

import httpx
import pytest

pytestmark = [pytest.mark.asyncio, pytest.mark.stack]

API = os.environ.get("CJ_STACK_URL", "http://localhost:4730")
ENV = Path(__file__).resolve().parents[4] / "deploy/compose/.env"
ADMIN_EMAIL = "admin@codejudge.local"

if os.environ.get("CJ_STACK") != "1":
    pytest.skip("needs the running stack (make up, then make test-stack)", allow_module_level=True)


async def docker(*args: str, check: bool = True) -> str:
    """Run the docker CLI without blocking the event loop."""
    exe = shutil.which("docker")
    assert exe, "the docker CLI is needed for the stack tests"
    proc = await asyncio.create_subprocess_exec(
        exe, *args, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    out, err = await proc.communicate()
    if check and proc.returncode != 0:
        raise RuntimeError(f"docker {' '.join(args[:3])} failed: {err.decode()[:300]}")
    return out.decode()


def demo_password() -> str:
    for line in ENV.read_text().splitlines():
        if line.startswith("CJ_DEMO_PASSWORD="):
            return line.split("=", 1)[1]
    raise RuntimeError("CJ_DEMO_PASSWORD missing from deploy/compose/.env (run make env)")


async def admin() -> httpx.AsyncClient:
    password = demo_password()
    client = httpx.AsyncClient(base_url=API, timeout=60, headers={"x-codejudge-csrf": "1"})
    resp = await client.post(
        "/api/v1/auth/login", json={"email": ADMIN_EMAIL, "password": password}
    )
    if resp.status_code != 200:
        # A stack without the demo seed: create the admin with the CLI inside the api container.
        await docker(
            "compose",
            "--env-file",
            str(ENV),
            "-f",
            str(ENV.parent / "compose.yaml"),
            "exec",
            "-T",
            "-e",
            f"CODEJUDGE_ADMIN_PASSWORD={password}",
            "api",
            "codejudge",
            "create-admin",
            "--email",
            ADMIN_EMAIL,
        )
        resp = await client.post(
            "/api/v1/auth/login", json={"email": ADMIN_EMAIL, "password": password}
        )
    resp.raise_for_status()
    client.headers["authorization"] = f"Bearer {resp.json()['session_token']}"
    return client


async def ok(c: httpx.AsyncClient, method: str, path: str, json: Any = None) -> Any:
    resp = await c.request(method, path, json=json)
    for _ in range(10):  # the per-person submission limit says how long to wait
        if resp.status_code != 429:
            break
        await asyncio.sleep(float(resp.headers.get("retry-after", "5")))
        resp = await c.request(method, path, json=json)
    assert resp.status_code < 300, f"{method} {path}: {resp.status_code} {resp.text[:300]}"
    return resp.json() if resp.content else None


async def judged(c: httpx.AsyncClient, sid: str, timeout_s: float = 180) -> dict[str, Any]:
    deadline = time.monotonic() + timeout_s
    while True:
        s = await ok(c, "GET", f"/api/v1/submissions/{sid}")
        if s["status"] == "done":
            return dict(s)
        assert time.monotonic() < deadline, f"not judged in {timeout_s}s: {s}"
        await asyncio.sleep(0.5)


async def problem(c: httpx.AsyncClient, *, time_limit_ms: int = 1000) -> str:
    """AC13: create, add tests and a reference solution, publish (the real judge must
    accept the reference first)."""
    slug = f"stack-{uuid.uuid4().hex[:8]}"
    p = await ok(
        c,
        "POST",
        "/api/v1/problems",
        {
            "slug": slug,
            "title": "Stack Sum",
            "statement_md": "Add.",
            "time_limit_ms": time_limit_ms,
            "visibility": "public",
        },
    )
    tests = [{"name": "sample/1", "input": "1 2\n", "answer": "3\n"}] + [
        {"name": f"secret/{k}", "input": f"{k} {k * 3}\n", "answer": f"{k * 4}\n"}
        for k in range(1, 6)
    ]
    await ok(c, "POST", f"/api/v1/problems/{p['id']}/versions", {"tests": tests})
    await ok(
        c,
        "POST",
        f"/api/v1/problems/{p['id']}/references",
        {"name": "ok", "language": "cpp17", "source": SOURCES["cpp_ok"]},
    )
    await ok(c, "POST", f"/api/v1/problems/{p['id']}/references/judge")
    deadline = time.monotonic() + 180
    while not (await ok(c, "GET", f"/api/v1/problems/{p['id']}/admin"))["publishable"]:
        assert time.monotonic() < deadline, "the reference solution was never judged"
        await asyncio.sleep(1)
    await ok(c, "POST", f"/api/v1/problems/{p['id']}/publish")
    return slug


async def remove(c: httpx.AsyncClient, slug: str) -> None:
    """Tests leave nothing behind in the demo data."""
    p = await ok(c, "GET", f"/api/v1/problems/{slug}")
    await c.delete(f"/api/v1/problems/{p['id']}")


async def sign_in(email: str, password: str) -> httpx.AsyncClient:
    client = httpx.AsyncClient(base_url=API, timeout=60, headers={"x-codejudge-csrf": "1"})
    for _ in range(10):  # many sign-ins at once meet the login limit: wait as it says
        resp = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
        if resp.status_code != 429:
            break
        await asyncio.sleep(float(resp.headers.get("retry-after", "5")))
    resp.raise_for_status()
    client.headers["authorization"] = f"Bearer {resp.json()['session_token']}"
    return client


async def students(c: httpx.AsyncClient, n: int) -> list[httpx.AsyncClient]:
    """n people, signed in: a burst comes from a class, not from one account."""
    password = demo_password()
    out = []
    for _ in range(n):
        email = f"stack-{uuid.uuid4().hex[:10]}@example.test"
        body = {"email": email, "name": "Stack Tester", "role": "student", "password": password}
        await ok(c, "POST", "/api/v1/users", body)
        out.append(await sign_in(email, password))
    return out


SOURCES = {
    "cpp_ok": '#include <iostream>\nint main(){long long a,b;std::cin>>a>>b;std::cout<<a+b<<"\\n";}\n',
    "py_ok": "a, b = map(int, input().split())\nprint(a + b)\n",
    "java_ok": "import java.util.*;\npublic class Main{public static void main(String[] x){Scanner s=new Scanner(System.in);System.out.println(s.nextLong()+s.nextLong());}}\n",
    "js_ok": "const [a,b]=require('fs').readFileSync(0,'utf8').trim().split(/\\s+/).map(Number);console.log(a+b);\n",
    "py_wa": "a, b = map(int, input().split())\nprint(a - b)\n",
    "cpp_tle": "int main(){volatile unsigned long long x=0;for(;;)x++;}\n",
    "py_bomb": "import os\nwhile True:\n    try:\n        os.fork()\n    except OSError:\n        pass\n",
    "py_net": "import socket\ntry:\n    socket.create_connection(('redis', 6379), timeout=1)\n    print('ESCAPED')\nexcept OSError:\n    a, b = map(int, input().split())\n    print(a + b)\n",
    "py_slow_ok": "import time\ns = 0\nfor i in range(70_000_000):\n    s += i\na, b = map(int, input().split())\nprint(a + b)\n",
}


async def test_the_five_minute_path_gives_a_real_verdict() -> None:
    c = await admin()
    slug = await problem(c)
    for key, language, want in (
        ("py_ok", "python3", "AC"),
        ("java_ok", "java21", "AC"),
        ("js_ok", "javascript", "AC"),
        ("py_wa", "python3", "WA"),
    ):
        s = await ok(
            c,
            "POST",
            "/api/v1/submissions",
            {"problem": slug, "language": language, "source": SOURCES[key]},
        )
        assert (await judged(c, s["id"]))["verdict"] == want, key
    await remove(c, slug)
    await c.aclose()


async def test_a_burst_with_hostile_programs_gets_every_verdict_right() -> None:
    """AC12: hostile programs share the workers with honest ones and change nothing."""
    c = await admin()
    slug = await problem(c)
    plan = [("cpp_ok", "cpp17", "AC"), ("py_ok", "python3", "AC"), ("py_wa", "python3", "WA"),
            ("cpp_tle", "cpp17", "TLE"), ("py_bomb", "python3", None), ("py_net", "python3", "AC"),
            ("java_ok", "java21", "AC"), ("js_ok", "javascript", "AC")] * 4  # fmt: skip
    people = await students(c, 8)
    sent = []
    for k, (key, language, want) in enumerate(plan):
        s = await ok(
            people[k % len(people)],
            "POST",
            "/api/v1/submissions",
            {"problem": slug, "language": language, "source": SOURCES[key]},
        )
        sent.append((s["id"], key, want))
    for sid, key, want in sent:
        got = await judged(c, sid, timeout_s=600)
        if want is None:  # a fork bomb ends as TLE or RE; it must not be AC or crash the judge
            assert got["verdict"] in ("TLE", "RE"), (key, got["verdict"])
        else:
            assert got["verdict"] == want, (key, got["verdict"], got.get("error"))
    await remove(c, slug)
    for person in people:
        await person.aclose()
    await c.aclose()


async def judge_containers() -> list[str]:
    out = await docker(
        "ps",
        "--filter",
        "label=com.docker.compose.project=codejudge",
        "--filter",
        "label=com.docker.compose.service=judge",
        "--format",
        "{{.Names}}",
    )
    return sorted(n for n in out.split() if n)


async def test_a_worker_killed_mid_job_does_not_lose_or_double_count_it() -> None:
    """AC5: kill the worker that is judging; the job is reclaimed after the lease and
    judged once by a surviving worker."""
    workers = await judge_containers()
    hostnames = {
        w: (await docker("inspect", "-f", "{{.Config.Hostname}}", w)).strip() for w in workers
    }
    if len(workers) < 2:
        pytest.skip("needs at least two judge workers (CJ_JUDGES=2, the default)")
    c = await admin()
    slug = await problem(c, time_limit_ms=10_000)
    (person,) = await students(c, 1)
    s = await ok(
        person,
        "POST",
        "/api/v1/submissions",
        {"problem": slug, "language": "python3", "source": SOURCES["py_slow_ok"]},
    )
    victim = None
    deadline = time.monotonic() + 60
    while victim is None and time.monotonic() < deadline:
        row = await ok(c, "GET", f"/api/v1/submissions/{s['id']}")
        if row["status"] == "judging" and row.get("worker"):
            victim = next(
                (w for w, host in hostnames.items() if host and host in row["worker"]), None
            )
        await asyncio.sleep(0.2)
    assert victim, "never saw the job being judged"
    await docker("kill", victim)
    try:
        final = await judged(c, s["id"], timeout_s=300)
        assert final["verdict"] == "AC", final
        assert final["worker"] and hostnames[victim] not in final["worker"]
        problem_row = await ok(c, "GET", f"/api/v1/problems/{slug}")
        assert problem_row["accepted_count"] == 1 and problem_row["submissions_count"] == 1
    finally:
        await docker("start", victim, check=False)
        await remove(c, slug)
        await person.aclose()
        await c.aclose()
