"""Accounts and sessions: users by admins, role rules, sign-in, lockout, sign-out, CSRF."""

from __future__ import annotations

import httpx
import pytest

from tests.integration.conftest import ADMIN, CSRF, Stack, login

pytestmark = pytest.mark.asyncio
PASSWORD = "User-Pass-123"


async def make(stack: Stack, role: str, email: str) -> dict[str, str]:
    body = {"email": email, "name": role.title(), "role": role, "password": PASSWORD}
    user: dict[str, str] = await stack.ok("POST", "/api/v1/users", body, status=201)
    return user


async def test_admins_manage_users_and_staff_cannot(stack: Stack) -> None:
    await make(stack, "staff", "staff@example.test")
    staff = await login(stack.api_url, {"email": "staff@example.test", "password": PASSWORD})
    assert (await staff.get("/api/v1/users")).status_code == 200  # staff may read the roster
    body = {"email": "x@example.test", "name": "X", "role": "admin", "password": PASSWORD}
    assert (await staff.post("/api/v1/users", json=body)).status_code == 403
    student = await make(stack, "student", "student@example.test")
    assert (
        await staff.patch(f"/api/v1/users/{student['id']}", json={"role": "staff"})
    ).status_code == 403
    duplicate = await stack.client.post(
        "/api/v1/users", json={**body, "email": "STUDENT@example.test", "role": "student"}
    )
    assert duplicate.status_code == 409 and duplicate.json()["error"]["code"] == "email_taken"
    weak = await stack.client.post(
        "/api/v1/users", json={**body, "email": "w@example.test", "password": "short"}
    )
    assert weak.status_code in (400, 422)
    await staff.aclose()


async def test_role_changes_end_the_old_session(stack: Stack) -> None:
    student = await make(stack, "student", "s@example.test")
    client = await login(stack.api_url, {"email": "s@example.test", "password": PASSWORD})
    assert (await client.get("/api/v1/auth/me")).json()["role"] == "student"
    await stack.ok("PATCH", f"/api/v1/users/{student['id']}", {"role": "staff"})
    assert (await client.get("/api/v1/auth/me")).status_code == 401
    await stack.ok("PATCH", f"/api/v1/users/{student['id']}", {"disabled": True})
    resp = await httpx.AsyncClient(base_url=stack.api_url).post(
        "/api/v1/auth/login", json={"email": "s@example.test", "password": PASSWORD}
    )
    assert resp.status_code == 401 and resp.json()["error"]["code"] == "account_disabled"
    missing = await stack.client.patch(
        "/api/v1/users/00000000-0000-0000-0000-000000000000", json={"name": "x"}
    )
    assert missing.status_code == 404
    await client.aclose()


async def test_the_last_active_admin_stays(stack: Stack) -> None:
    me = (await stack.ok("GET", "/api/v1/auth/me"))["id"]
    own = await stack.client.patch(f"/api/v1/users/{me}", json={"role": "staff"})
    assert own.status_code == 403  # nobody changes their own role
    other = await make(stack, "admin", "second@example.test")
    second = await login(stack.api_url, {"email": "second@example.test", "password": PASSWORD})
    # With two active admins one may demote the other...
    await stack.ok("PATCH", f"/api/v1/users/{other['id']}", {"role": "staff"})
    # ...and a disabled admin can always be demoted: it does not keep anyone in charge.
    third = await make(stack, "admin", "third@example.test")
    await stack.ok("PATCH", f"/api/v1/users/{third['id']}", {"disabled": True})
    await stack.ok("PATCH", f"/api/v1/users/{third['id']}", {"role": "staff"})
    await second.aclose()


async def test_sign_in_failures_lock_the_account(stack: Stack) -> None:
    await make(stack, "student", "lock@example.test")
    anon = httpx.AsyncClient(base_url=stack.api_url)
    for _ in range(5):
        wrong = await anon.post(
            "/api/v1/auth/login", json={"email": "lock@example.test", "password": "Wrong-Pass-123"}
        )
        assert wrong.status_code == 401
    locked = await anon.post(
        "/api/v1/auth/login", json={"email": "lock@example.test", "password": PASSWORD}
    )
    assert locked.status_code == 401 and locked.json()["error"]["code"] == "account_locked"
    unknown = await anon.post(
        "/api/v1/auth/login", json={"email": "nobody@example.test", "password": PASSWORD}
    )
    assert unknown.json()["error"]["code"] == "invalid_credentials"
    await anon.aclose()


async def test_password_change_ends_other_sessions(stack: Stack) -> None:
    await make(stack, "student", "pw@example.test")
    first = await login(stack.api_url, {"email": "pw@example.test", "password": PASSWORD})
    second = await login(stack.api_url, {"email": "pw@example.test", "password": PASSWORD})
    wrong = await first.post(
        "/api/v1/auth/password",
        json={"current_password": "nope-Nope-1", "new_password": "New-Pass-456"},
    )
    assert wrong.status_code == 401
    weak = await first.post(
        "/api/v1/auth/password", json={"current_password": PASSWORD, "new_password": "weak"}
    )
    assert weak.status_code in (400, 422)
    changed = await first.post(
        "/api/v1/auth/password", json={"current_password": PASSWORD, "new_password": "New-Pass-456"}
    )
    assert changed.status_code == 200
    first.headers["authorization"] = f"Bearer {changed.json()['session_token']}"
    assert (await first.get("/api/v1/auth/me")).status_code == 200
    assert (await second.get("/api/v1/auth/me")).status_code == 401
    await first.aclose()
    await second.aclose()


async def test_sign_out_revokes_the_token(stack: Stack) -> None:
    client = await login(stack.api_url, ADMIN)
    assert (await client.post("/api/v1/auth/logout")).status_code == 200
    resp = await client.get("/api/v1/auth/me")
    assert resp.status_code == 401 and resp.json()["error"]["code"] == "session_expired"
    anon = httpx.AsyncClient(base_url=stack.api_url)
    assert (await anon.post("/api/v1/auth/logout")).status_code == 200  # signing out twice is fine
    assert (await anon.get("/api/v1/auth/me")).json()["error"]["code"] == "not_signed_in"
    assert (
        await anon.get("/api/v1/auth/me", headers={"authorization": "Bearer garbage"})
    ).status_code == 401
    await client.aclose()
    await anon.aclose()


async def test_cookie_sessions_need_the_csrf_header_for_changes(stack: Stack) -> None:
    anon = httpx.AsyncClient(base_url=stack.api_url)
    resp = await anon.post("/api/v1/auth/login", json=ADMIN)
    cookie = resp.cookies.get("cj_session")
    assert cookie and "httponly" in resp.headers["set-cookie"].lower()
    browser = httpx.AsyncClient(base_url=stack.api_url, cookies={"cj_session": cookie})
    assert (await browser.get("/api/v1/auth/me")).status_code == 200  # reads need no header
    body = {"email": "c@example.test", "name": "C", "role": "student", "password": PASSWORD}
    refused = await browser.post("/api/v1/users", json=body)
    assert refused.status_code == 403 and refused.json()["error"]["code"] == "csrf_required"
    allowed = await browser.post("/api/v1/users", json=body, headers=CSRF)
    assert allowed.status_code == 201
    await anon.aclose()
    await browser.aclose()


async def test_the_session_endpoint_answers_signed_out_visitors_without_an_error(
    stack: Stack,
) -> None:
    async with stack.anonymous() as anon:
        resp = await anon.get("/api/v1/auth/session")
        assert resp.status_code == 200 and resp.json() == {"user": None}
        resp = await anon.get(
            "/api/v1/auth/session", headers={"authorization": "Bearer not-a-token"}
        )
        assert resp.status_code == 200 and resp.json() == {"user": None}
    mine = await stack.ok("GET", "/api/v1/auth/session")
    assert mine["user"]["email"] == "admin@example.test"
