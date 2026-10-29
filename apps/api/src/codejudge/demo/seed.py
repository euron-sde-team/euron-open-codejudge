"""The demo install (``make demo``): a judge that looks like it has been used for a month.

Everything that can go through the API does, as the people who would do it: staff create
and publish the problems (whose reference solutions the real judge must accept first),
students sign in and submit real programs in four languages that the real judge workers
compile and run, a teacher runs a class, an interviewer invites candidates who take the
assessment through the one-time link from their email (read back from Mailpit). Only the
month of history is written directly: it copies verdicts the real judge just produced
into earlier days, so every number on the dashboards traces back to a real judgement.

Idempotent: a second run finds the demo problem set and only prints the sign-in details.
"""

from __future__ import annotations

import asyncio
import os
import random
import re
import uuid
from datetime import UTC, date, datetime, timedelta
from typing import Any

import httpx
from sqlalchemy import func, select, update

from codejudge.core.config import get_settings
from codejudge.core.db import Database, import_all_models
from codejudge.core.security import hash_password
from codejudge.demo.problems import PROBLEMS, DemoProblem, groups_for, tests_for
from codejudge.users.models import User

API = os.environ.get("CJ_DEMO_API_URL", "http://api:8080")
MAILPIT = os.environ.get("CJ_DEMO_MAILPIT_URL", "http://mailpit:8025")
AI_URL = os.environ.get("CJ_DEMO_AI_URL", "")
CSRF = {"x-codejudge-csrf": "1"}
ADMIN_EMAIL = "admin@codejudge.local"
TEACHER = ("Priya Raman", "priya.raman@codejudge.local")
INTERVIEWER = ("Daniel Okafor", "daniel.okafor@codejudge.local")
STUDENTS = [
    "Aarav Mehta", "Sofia Rossi", "Kenji Watanabe", "Amara Nwosu", "Lucas Martin", "Zara Khan",
    "Mateo Garcia", "Ananya Iyer", "Noah Fischer", "Leila Haddad", "Ethan Brooks", "Mei Lin",
    "Omar Farouk", "Isabela Costa", "Rohan Das", "Hannah Schmidt", "Yusuf Demir", "Chloe Dubois",
    "Arjun Nair", "Grace Kim", "Tomas Novak", "Fatima Zahra", "Liam Walsh", "Nadia Petrova",
]  # fmt: skip
CANDIDATES = [
    ("Jordan Lee", "jordan.lee@example.com"),
    ("Samira Patel", "samira.patel@example.com"),
    ("Alex Moreau", "alex.moreau@example.com"),
]


def log(msg: str) -> None:
    print(f"demo: {msg}", flush=True)


def email_of(name: str) -> str:
    return re.sub(r"[^a-z.]", "", name.lower().replace(" ", ".")) + "@students.example"


class Client:
    """A signed-in person talking to the API."""

    def __init__(self, http: httpx.AsyncClient, name: str):
        self.http, self.name = http, name

    async def call(
        self, method: str, path: str, json: Any = None, ok: tuple[int, ...] = (200, 201, 202, 204)
    ) -> Any:
        for attempt in range(5):
            resp = await self.http.request(method, path, json=json)
            if resp.status_code == 429 and attempt < 4:
                await asyncio.sleep(float(resp.headers.get("retry-after", "2")))
                continue
            if resp.status_code not in ok:
                raise RuntimeError(
                    f"{self.name}: {method} {path} -> {resp.status_code} {resp.text[:300]}"
                )
            return (
                resp.json()
                if resp.content
                and resp.headers.get("content-type", "").startswith("application/json")
                else None
            )
        raise RuntimeError(f"{self.name}: {method} {path} kept hitting the rate limit")


async def sign_in(email: str, password: str, name: str) -> Client:
    http = httpx.AsyncClient(base_url=API, timeout=120, headers=CSRF)
    # Many sign-ins from one address trip the login rate limit: wait as it says.
    for _ in range(30):
        resp = await http.post("/api/v1/auth/login", json={"email": email, "password": password})
        if resp.status_code != 429:
            break
        await asyncio.sleep(float(resp.headers.get("retry-after", "5")))
    resp.raise_for_status()
    http.headers["authorization"] = f"Bearer {resp.json()['session_token']}"
    return Client(http, name)


async def wait_api() -> None:
    async with httpx.AsyncClient(base_url=API, timeout=5) as http:
        for _ in range(120):
            try:
                if (await http.get("/healthz")).status_code == 200:
                    return
            except httpx.HTTPError:
                pass
            await asyncio.sleep(1)
    raise SystemExit(f"the API at {API} did not come up")


async def ensure_admin(db: Database, password: str) -> None:
    async with db.sessionmaker() as session:
        if await session.scalar(select(User.id).where(User.email == ADMIN_EMAIL)) is None:
            session.add(
                User(
                    email=ADMIN_EMAIL,
                    name="Morgan Ellis",
                    role="admin",
                    password_hash=hash_password(password),
                )
            )
            await session.commit()


async def wait_judged(
    client: Client, ids: list[str], timeout_s: float = 900
) -> list[dict[str, Any]]:
    """Wait until the real judge has judged every submission."""
    deadline = asyncio.get_running_loop().time() + timeout_s
    done: dict[str, dict[str, Any]] = {}
    while len(done) < len(ids):
        for sid in ids:
            if sid not in done:
                s = await client.call("GET", f"/api/v1/submissions/{sid}")
                if s["status"] == "done":
                    done[sid] = s
        if len(done) < len(ids):
            if asyncio.get_running_loop().time() > deadline:
                raise SystemExit(
                    f"the judge did not finish {len(ids) - len(done)} submissions; is a judge worker running?"
                )
            await asyncio.sleep(1)
    return [done[i] for i in ids]


# ── problems ─────────────────────────────────────────────────────────────────────────
async def create_problem(admin: Client, p: DemoProblem) -> dict[str, Any]:
    problem: dict[str, Any] = await admin.call(
        "POST", "/api/v1/problems",
        {"slug": p.slug, "title": p.title, "statement_md": p.statement, "difficulty": p.difficulty, "tags": p.tags,
         "time_limit_ms": p.time_limit_ms, "memory_limit_mb": p.memory_limit_mb, "source": "Euron Open CodeJudge demo set",
         "license": "MIT"},
    )  # fmt: skip
    body: dict[str, Any] = {"tests": tests_for(p), "groups": groups_for(p), "note": "demo tests"}
    if p.checker:
        body["checker"] = p.checker
    if p.checker_source:
        body["checker_source"] = p.checker_source
    await admin.call("POST", f"/api/v1/problems/{problem['id']}/versions", body)
    for language, source in p.references.items():
        await admin.call(
            "POST",
            f"/api/v1/problems/{problem['id']}/references",
            {"name": f"reference {language}", "language": language, "source": source},
        )
    await admin.call("POST", f"/api/v1/problems/{problem['id']}/references/judge")
    return problem


async def publish_all(admin: Client, problems: dict[str, dict[str, Any]]) -> None:
    pending = dict(problems)
    deadline = asyncio.get_running_loop().time() + 900
    while pending:
        for slug, p in list(pending.items()):
            detail = await admin.call("GET", f"/api/v1/problems/{p['id']}/admin")
            if detail["publishable"]:
                await admin.call("POST", f"/api/v1/problems/{p['id']}/publish")
                del pending[slug]
            elif any("got" in b for b in detail["publish_blockers"]):
                raise SystemExit(
                    f"{slug}: a reference solution failed: {detail['publish_blockers']}"
                )
        if pending:
            if asyncio.get_running_loop().time() > deadline:
                raise SystemExit(f"references still not judged for: {', '.join(pending)}")
            await asyncio.sleep(2)


# ── the run ──────────────────────────────────────────────────────────────────────────
async def run() -> None:
    password = os.environ.get("CJ_DEMO_PASSWORD", "")
    if not password:
        raise SystemExit("Set CJ_DEMO_PASSWORD (make demo passes the stack's .env)")
    import_all_models()
    settings = get_settings()
    db = Database(settings.database_url, pool_size=2, max_overflow=0)
    rng = random.Random(7)
    try:
        await wait_api()
        await ensure_admin(db, password)
        admin = await sign_in(ADMIN_EMAIL, password, "admin")
        existing = await admin.call("GET", "/api/v1/problems?q=sum-of-two")
        if existing["items"]:
            log("already seeded")
            print_logins(password)
            return

        # People.
        teacher_email, interviewer_email = TEACHER[1], INTERVIEWER[1]
        for name, email, role in (
            (TEACHER[0], teacher_email, "staff"),
            (INTERVIEWER[0], interviewer_email, "staff"),
        ):
            await admin.call(
                "POST",
                "/api/v1/users",
                {"email": email, "name": name, "role": role, "password": password},
            )
        for name in STUDENTS:
            await admin.call(
                "POST",
                "/api/v1/users",
                {"email": email_of(name), "name": name, "role": "student", "password": password},
            )
        log(f"{len(STUDENTS)} students, a teacher and an interviewer")

        if AI_URL:
            await admin.call(
                "PATCH",
                "/api/v1/org/settings",
                {
                    "site_name": "CodeJudge Demo",
                    "ai_enabled": True,
                    "ai_base_url": AI_URL,
                    "ai_model": "mock-hint",
                    "ai_max_hints_per_problem": 3,
                },
            )

        # Problems, published only once the real judge accepts their reference solutions.
        problems = {p.slug: await create_problem(admin, p) for p in PROBLEMS}
        log(f"{len(problems)} problems created; the judge is checking their reference solutions")
        await publish_all(admin, problems)
        log("problems published")

        students = [await sign_in(email_of(n), password, n) for n in STUDENTS]
        teacher = await sign_in(teacher_email, password, TEACHER[0])
        interviewer = await sign_in(interviewer_email, password, INTERVIEWER[0])

        # Practice: real submissions, judged by the real judge.
        ids: list[tuple[Client, str]] = []
        for k, student in enumerate(students[:16]):
            # Coin Change is left to the plagiarism demo: there, only the planted copy and an
            # independent solution exist, so the check shows exactly what it is for.
            practice = [x for x in PROBLEMS if x.slug != "coin-change"]
            for p in rng.sample(practice, 4 + k % 3):
                if p.wrong and rng.random() < 0.55:
                    language, source = rng.choice(p.wrong)
                    s = await student.call(
                        "POST",
                        "/api/v1/submissions",
                        {"problem": p.slug, "language": language, "source": source},
                    )
                    ids.append((student, s["id"]))
                language, source = rng.choice(list(p.references.items()))
                s = await student.call(
                    "POST",
                    "/api/v1/submissions",
                    {"problem": p.slug, "language": language, "source": source},
                )
                ids.append((student, s["id"]))
        log(f"{len(ids)} practice submissions sent; the judge is running them")
        judged = await wait_judged(admin, [i for _, i in ids])
        verdicts: dict[str, int] = {}
        for s in judged:
            verdicts[s["verdict"]] = verdicts.get(s["verdict"], 0) + 1
        log("practice verdicts: " + ", ".join(f"{v} {n}" for v, n in sorted(verdicts.items())))

        # A planted copy for the plagiarism check: same program, renamed and reordered.
        coin = next(p for p in PROBLEMS if p.slug == "coin-change")
        copy_src = (
            "import sys\n\n\ndef read():\n    return list(map(int, sys.stdin.read().split()))\n\n\n"
            "vals = read()\ncount, goal = vals[0], vals[1]\ndenoms = vals[2:2 + count]\nBIG = 1 << 30\n"
            "table = [0] + [BIG] * goal\nfor amount in range(1, goal + 1):\n    for d in denoms:\n"
            "        if d <= amount and table[amount - d] + 1 < table[amount]:\n            table[amount] = table[amount - d] + 1\n"
            "print(table[goal] if table[goal] < BIG else -1)\n"
        )
        own_src = (
            "import sys\n\nk, t, *coins = map(int, sys.stdin.read().split())\nINF = 1 << 30\nbest = [0] + [INF] * t\n"
            "for value in range(1, t + 1):\n    for c in coins:\n        if c <= value and best[value - c] + 1 < best[value]:\n"
            "            best[value] = best[value - c] + 1\nprint(best[t] if best[t] < INF else -1)\n"
        )
        plag = [await students[16].call("POST", "/api/v1/submissions", {"problem": coin.slug, "language": "python3", "source": own_src}),
                await students[17].call("POST", "/api/v1/submissions", {"problem": coin.slug, "language": "python3", "source": copy_src})]  # fmt: skip
        await wait_judged(admin, [s["id"] for s in plag])

        # Contests: a running IOI round with live submissions, a past ICPC contest, an upcoming cup.
        now = datetime.now(UTC)
        live = await admin.call("POST", "/api/v1/contests", {
            "slug": "weekly-round-42", "title": "Weekly Round 42", "format": "ioi",
            "description_md": "Three problems, partial scores per subtask. Best score per problem counts.",
            "starts_at": (now - timedelta(hours=1)).isoformat(), "ends_at": (now + timedelta(days=2)).isoformat(),
            "visibility": "public", "registration": "open",
        })  # fmt: skip
        for slug in ("range-sums", "grid-escape", "longest-increasing"):
            await admin.call(
                "POST", f"/api/v1/contests/{live['id']}/problems", {"problem": slug, "points": 100}
            )
        live_ids = []
        for student in students[:12]:
            await student.call("POST", f"/api/v1/contests/{live['slug']}/register")
            for slug in rng.sample(["range-sums", "grid-escape", "longest-increasing"], 2):
                p = next(x for x in PROBLEMS if x.slug == slug)
                language, source = (
                    rng.choice(p.wrong + list(p.references.items()))
                    if p.wrong
                    else rng.choice(list(p.references.items()))
                )
                s = await student.call(
                    "POST",
                    "/api/v1/submissions",
                    {
                        "problem": slug,
                        "language": language,
                        "source": source,
                        "context": "contest",
                        "context_id": live["id"],
                    },
                )
                live_ids.append(s["id"])
        await students[3].call(
            "POST",
            f"/api/v1/contests/{live['slug']}/clarifications",
            {"question": "In Range Sums, can a query have a greater than b?", "problem_label": "A"},
        )
        await admin.call(
            "POST",
            f"/api/v1/contests/{live['id']}/announcements",
            {"answer": "Reminder: subtask scores add up; your best submission per problem counts."},
        )
        await wait_judged(admin, live_ids)
        log(f"Weekly Round 42 running with {len(live_ids)} judged submissions")

        past = await admin.call("POST", "/api/v1/contests", {
            "slug": "autumn-sprint-2026", "title": "Autumn Sprint 2026", "format": "icpc",
            "description_md": "Two hours, ICPC rules: solved count, then penalty minutes.",
            "starts_at": (now - timedelta(minutes=5)).isoformat(), "ends_at": (now + timedelta(days=1)).isoformat(),
            "freeze_at": None, "visibility": "public", "registration": "open", "penalty_minutes": 20,
        })  # fmt: skip
        for slug in ("sum-of-two", "balanced-brackets", "word-frequency", "coin-change"):
            await admin.call("POST", f"/api/v1/contests/{past['id']}/problems", {"problem": slug})
        past_ids = []
        for k, student in enumerate(students[:14]):
            await student.call("POST", f"/api/v1/contests/{past['slug']}/register")
            for slug in ("sum-of-two", "balanced-brackets", "word-frequency", "coin-change")[
                : 1 + (k * 7) % 4
            ]:
                p = next(x for x in PROBLEMS if x.slug == slug)
                if p.wrong and rng.random() < 0.5:
                    language, source = rng.choice(p.wrong)
                    s = await student.call(
                        "POST",
                        "/api/v1/submissions",
                        {
                            "problem": slug,
                            "language": language,
                            "source": source,
                            "context": "contest",
                            "context_id": past["id"],
                        },
                    )
                    past_ids.append(s["id"])
                language, source = rng.choice(list(p.references.items()))
                s = await student.call(
                    "POST",
                    "/api/v1/submissions",
                    {
                        "problem": slug,
                        "language": language,
                        "source": source,
                        "context": "contest",
                        "context_id": past["id"],
                    },
                )
                past_ids.append(s["id"])
        await wait_judged(admin, past_ids)

        await admin.call("POST", "/api/v1/contests", {
            "slug": "winter-cup-2026", "title": "Winter Cup 2026", "format": "icpc",
            "description_md": "Five problems, three hours, a 30 minute freeze at the end.",
            "starts_at": (now + timedelta(days=5)).isoformat(), "ends_at": (now + timedelta(days=5, hours=3)).isoformat(),
            "freeze_at": (now + timedelta(days=5, hours=2, minutes=30)).isoformat(), "visibility": "public", "registration": "open",
        })  # fmt: skip

        # Class: a teacher, a roster that joined with the code, three assignments.
        klass = await teacher.call(
            "POST",
            "/api/v1/classes",
            {
                "name": "CS201: Data Structures",
                "description": "Autumn term, Tuesdays and Thursdays.",
            },
        )
        for student in students[:18]:
            await student.call("POST", "/api/v1/classes/join", {"code": klass["join_code"]})
        week3 = await teacher.call("POST", f"/api/v1/classes/{klass['id']}/assignments", {
            "title": "Week 3: Stacks and arrays", "description_md": "Warm up with arrays, then a stack.",
            "opens_at": (now - timedelta(minutes=10)).isoformat(), "due_at": (now + timedelta(days=1)).isoformat(),
            "late_policy": "penalty", "penalty_percent": 20,
            "problems": [{"problem": "second-largest", "points": 40}, {"problem": "balanced-brackets", "points": 60}],
        })  # fmt: skip
        week4 = await teacher.call("POST", f"/api/v1/classes/{klass['id']}/assignments", {
            "title": "Week 4: Graphs", "description_md": "Breadth-first and depth-first search.",
            "opens_at": (now - timedelta(minutes=10)).isoformat(), "due_at": (now + timedelta(days=4)).isoformat(),
            "late_policy": "accept",
            "problems": [{"problem": "grid-escape", "points": 50}, {"problem": "count-islands", "points": 50}],
        })  # fmt: skip
        await teacher.call("POST", f"/api/v1/classes/{klass['id']}/assignments", {
            "title": "Week 5: Dynamic programming", "description_md": "Two classic DP problems.",
            "opens_at": (now + timedelta(days=3)).isoformat(), "due_at": (now + timedelta(days=10)).isoformat(),
            "late_policy": "refuse", "problems": [{"problem": "coin-change", "points": 50}, {"problem": "longest-increasing", "points": 50}],
        })  # fmt: skip
        class_ids = []
        for k, student in enumerate(students[:18]):
            for assignment, slugs in (
                (week3, ("second-largest", "balanced-brackets")),
                (week4, ("grid-escape", "count-islands")),
            ):
                for slug in slugs[: 1 + k % 2]:
                    p = next(x for x in PROBLEMS if x.slug == slug)
                    language, source = (
                        rng.choice(p.wrong)
                        if p.wrong and k % 4 == 0
                        else rng.choice(list(p.references.items()))
                    )
                    s = await student.call(
                        "POST",
                        "/api/v1/submissions",
                        {
                            "problem": slug,
                            "language": language,
                            "source": source,
                            "context": "assignment",
                            "context_id": assignment["id"],
                        },
                    )
                    class_ids.append(s["id"])
        await wait_judged(admin, class_ids)
        log(f"class with {len(class_ids)} judged assignment submissions")

        # Interview: invitations by email; one candidate takes the assessment end to end.
        screen = await interviewer.call("POST", "/api/v1/assessments", {
            "title": "Backend Engineer: Coding Screen",
            "instructions_md": "Solve as many as you can in 60 minutes. Use any of the four languages. Explain trade-offs in comments.",
            "duration_minutes": 60,
            "problems": [{"problem": "pair-sum", "points": 40}, {"problem": "word-frequency", "points": 30}, {"problem": "rotate-matrix", "points": 30}],
        })  # fmt: skip
        result = await interviewer.call(
            "POST",
            f"/api/v1/assessments/{screen['id']}/invitations",
            {"candidates": [{"email": e, "name": n} for n, e in CANDIDATES]},
        )
        invited = result["invitations"]
        await take_assessment(screen, invited)
        revoke = next((i for i in invited if i["email"] == CANDIDATES[2][1]), None)
        if revoke:
            await interviewer.call(
                "POST", f"/api/v1/assessments/{screen['id']}/invitations/{revoke['id']}/revoke"
            )

        # Plagiarism run over Coin Change (the planted copy should be the top pair).
        await teacher.call(
            "POST", "/api/v1/plagiarism/runs", {"scope": "problem", "scope_id": coin.slug}
        )

        # A hint, so the AI usage shows up (the demo points AI at the mock LLM).
        if AI_URL:
            await students[5].call(
                "POST",
                "/api/v1/hints",
                {
                    "problem": "longest-increasing",
                    "language": "cpp17",
                    "source": PROBLEMS[7].wrong[0][1],
                    "question": "Why is my solution too slow?",
                },
                ok=(200, 201, 400, 403, 409, 429),
            )

        await move_into_past(db, rng, uuid.UUID(past["id"]), uuid.UUID(week3["id"]))
        await backfill_history(db, rng)
        log("a month of history written from the real verdicts")
        print_logins(password)
    finally:
        await db.dispose()


async def take_assessment(screen: dict[str, Any], invited: list[dict[str, Any]]) -> None:
    """The first candidate opens the link from their email and takes the assessment."""
    token = await token_from_mail(CANDIDATES[0][1])
    if token is None:
        log(
            "Mailpit not reachable: the invitations were sent, but no candidate took the assessment"
        )
        return
    async with httpx.AsyncClient(base_url=API, timeout=120, headers=CSRF) as http:
        resp = await http.post("/api/v1/candidate/session", json={"token": token})
        resp.raise_for_status()
        session = resp.json()
        http.headers["x-codejudge-candidate"] = token
        invitation_id = session.get("invitation_id") or session.get("invitation", {}).get("id")
        cand = Client(http, CANDIDATES[0][0])
        ids = []
        for slug in ("pair-sum", "word-frequency", "rotate-matrix"):
            p = next(x for x in PROBLEMS if x.slug == slug)
            if slug == "word-frequency":
                await cand.call(
                    "POST", "/api/v1/candidate/events", {"kind": "tab_hidden", "detail": {}}
                )
                await cand.call(
                    "POST", "/api/v1/candidate/events", {"kind": "tab_visible", "detail": {}}
                )
                language, source = p.wrong[0]
                s = await cand.call(
                    "POST",
                    "/api/v1/submissions",
                    {
                        "problem": slug,
                        "language": language,
                        "source": source,
                        "context": "assessment",
                        "context_id": invitation_id,
                    },
                )
                ids.append(s["id"])
            if slug == "rotate-matrix":
                await cand.call(
                    "POST", "/api/v1/candidate/events", {"kind": "paste", "detail": {"chars": 412}}
                )
            language, source = next(iter(p.references.items()))
            s = await cand.call(
                "POST",
                "/api/v1/submissions",
                {
                    "problem": slug,
                    "language": language,
                    "source": source,
                    "context": "assessment",
                    "context_id": invitation_id,
                },
            )
            ids.append(s["id"])
        for _ in range(600):
            states = [(await cand.call("GET", f"/api/v1/submissions/{i}"))["status"] for i in ids]
            if all(st == "done" for st in states):
                break
            await asyncio.sleep(1)
        await cand.call("POST", "/api/v1/candidate/finish")
    log(f"{CANDIDATES[0][0]} took the assessment through the emailed link")
    del screen, invited


async def token_from_mail(address: str) -> str | None:
    try:
        async with httpx.AsyncClient(base_url=MAILPIT, timeout=10) as http:
            for _ in range(30):
                found = (await http.get("/api/v1/search", params={"query": f"to:{address}"})).json()
                messages = found.get("messages") or []
                if messages:
                    body = (await http.get(f"/api/v1/message/{messages[0]['ID']}")).json()
                    m = re.search(
                        r"/take/([A-Za-z0-9_\-]+)", body.get("Text", "") + body.get("HTML", "")
                    )
                    if m:
                        return m.group(1)
                await asyncio.sleep(1)
    except httpx.HTTPError:
        return None
    return None


async def move_into_past(
    db: Database, rng: random.Random, contest_id: uuid.UUID, assignment_id: uuid.UUID
) -> None:
    """The finished contest and the past-due assignment ran for real just now (submissions
    are refused outside their window); move them, and their submissions in order, into
    the past so the demo has history with final standings and grades."""
    from codejudge.classrooms.models import Assignment
    from codejudge.contests.models import Contest
    from codejudge.submissions.models import Submission

    now = datetime.now(UTC)
    async with db.sessionmaker() as session:
        start = (now - timedelta(days=9)).replace(hour=14, minute=0, second=0, microsecond=0)
        await session.execute(
            update(Contest)
            .where(Contest.id == contest_id)
            .values(starts_at=start, ends_at=start + timedelta(hours=2), freeze_at=None)
        )
        subs = list(
            (
                await session.scalars(
                    select(Submission)
                    .where(Submission.context == "contest", Submission.context_id == contest_id)
                    .order_by(Submission.created_at)
                )
            ).all()
        )
        offsets = sorted(rng.randint(4, 118) for _ in subs)
        for s, minutes in zip(subs, offsets, strict=True):
            s.created_at = start + timedelta(minutes=minutes, seconds=rng.randint(0, 59))
            s.judged_at = s.created_at + timedelta(seconds=3)
        opens, due = now - timedelta(days=12), now - timedelta(days=5)
        await session.execute(
            update(Assignment)
            .where(Assignment.id == assignment_id)
            .values(opens_at=opens, due_at=due)
        )
        for s in (
            await session.scalars(
                select(Submission).where(
                    Submission.context == "assignment", Submission.context_id == assignment_id
                )
            )
        ).all():
            s.created_at = opens + timedelta(days=rng.randint(0, 6), hours=rng.randint(8, 22))
            s.judged_at = s.created_at + timedelta(seconds=3)
        await session.commit()


async def backfill_history(db: Database, rng: random.Random) -> None:
    """Copy today's real practice verdicts into the previous 30 days, a few per day, with
    a weekly rhythm, then rebuild the analytics rollups and the problem counters."""
    from codejudge.analytics.service import recount
    from codejudge.problems.models import Problem
    from codejudge.submissions.models import Submission

    async with db.sessionmaker() as session:
        real = list(
            (
                await session.scalars(
                    select(Submission).where(
                        Submission.context == "practice", Submission.status == "done"
                    )
                )
            ).all()
        )
        if not real:
            return
        now = datetime.now(UTC)
        buckets: set[tuple[uuid.UUID, str, date]] = set()
        for days_ago in range(1, 31):
            day = now - timedelta(days=days_ago)
            weekday = day.weekday()
            count = rng.randint(14, 30) if weekday < 5 else rng.randint(4, 12)
            for _ in range(count):
                src = rng.choice(real)
                at = day.replace(
                    hour=rng.randint(8, 22), minute=rng.randint(0, 59), second=rng.randint(0, 59)
                )
                session.add(
                    Submission(
                        id=uuid.uuid4(), user_id=src.user_id, problem_id=src.problem_id, version_id=src.version_id,
                        language=src.language, source=src.source, context="practice", status="done",
                        verdict=src.verdict, score=src.score, max_score=src.max_score, time_ms=src.time_ms,
                        memory_kb=src.memory_kb, compile_output=src.compile_output, tests=src.tests, groups=src.groups,
                        job_id=uuid.uuid4().hex, attempt=1, worker=src.worker, judged_ms=src.judged_ms,
                        created_at=at, judged_at=at + timedelta(seconds=rng.randint(1, 4)),
                    )
                )  # fmt: skip
                buckets.add((src.problem_id, src.language, at.date()))
        await session.flush()
        for problem_id, language, day_ in buckets:
            await recount(session, problem_id, language, day_)
        counted = ("practice", "contest", "assignment", "assessment")
        for p in (await session.scalars(select(Problem))).all():
            subs = (
                select(func.count())
                .select_from(Submission)
                .where(Submission.problem_id == p.id, Submission.context.in_(counted))
            )
            total = int(await session.scalar(subs) or 0)
            accepted = int(await session.scalar(subs.where(Submission.verdict == "AC")) or 0)
            solvers = int(
                await session.scalar(
                    select(func.count(func.distinct(Submission.user_id))).where(
                        Submission.problem_id == p.id,
                        Submission.context.in_(counted),
                        Submission.verdict == "AC",
                    )
                )
                or 0
            )
            await session.execute(
                update(Problem)
                .where(Problem.id == p.id)
                .values(submissions_count=total, accepted_count=accepted, solvers_count=solvers)
            )
        await session.commit()


def print_logins(password: str) -> None:
    log("sign in at http://localhost:4710 with any of these (password for all of them below)")
    log(f"  admin       {ADMIN_EMAIL}")
    log(f"  teacher     {TEACHER[1]}")
    log(f"  interviewer {INTERVIEWER[1]}")
    log(f"  student     {email_of(STUDENTS[0])}")
    log(f"  password    {password}")
    log("  candidate invitations: http://localhost:4725 (Mailpit)")
