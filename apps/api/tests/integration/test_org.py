"""Organisation settings and self sign-up."""

from __future__ import annotations

import pytest

from tests.integration.conftest import Stack

pytestmark = pytest.mark.asyncio

SIGNUP = {"email": "new.student@example.test", "name": "New Student", "password": "Student-Pass-9"}


async def test_public_settings_carry_no_secrets(stack: Stack) -> None:
    await stack.ok(
        "PATCH",
        "/api/v1/org/settings",
        {
            "ai_base_url": stack.mock_ai_url + "/v1",
            "ai_model": "mock",
            "ai_api_key": "sk-secret-123",
        },
    )
    async with stack.anonymous() as anon:
        resp = await anon.get("/api/v1/org/public")
    assert resp.status_code == 200
    body = resp.json()
    assert set(body) == {"site_name", "allow_signup", "default_language", "ai_enabled"}
    assert "sk-secret" not in resp.text and "mock" not in resp.text


async def test_the_ai_key_is_sealed_and_never_returned(stack: Stack) -> None:
    patched = await stack.ok(
        "PATCH",
        "/api/v1/org/settings",
        {
            "ai_base_url": stack.mock_ai_url + "/v1",
            "ai_model": "mock",
            "ai_api_key": "sk-secret-123",
        },
    )
    assert patched["ai_has_key"] is True and "sk-secret" not in str(patched)
    read = await stack.client.get("/api/v1/org/settings")
    assert "sk-secret" not in read.text and read.json()["ai_has_key"] is True
    cleared = await stack.ok("PATCH", "/api/v1/org/settings", {"ai_api_key": ""})
    assert cleared["ai_has_key"] is False
    audit = await stack.ok("GET", "/api/v1/audit?action=org.")
    assert audit["items"] and "sk-secret" not in str(audit)


async def test_only_admins_change_settings(stack: Stack) -> None:
    for role in ("student", "staff"):
        client = await stack.user(role)
        assert (await client.get("/api/v1/org/settings")).status_code == 403
        resp = await client.patch("/api/v1/org/settings", json={"allow_signup": False})
        assert resp.status_code == 403
        await client.aclose()


async def test_settings_are_validated(stack: Stack) -> None:
    resp = await stack.client.patch("/api/v1/org/settings", json={"ai_enabled": True})
    assert resp.status_code == 400 and resp.json()["error"]["code"] == "ai_endpoint_required"
    resp = await stack.client.patch(
        "/api/v1/org/settings", json={"ai_base_url": "http://169.254.169.254/latest"}
    )
    assert resp.status_code == 422
    resp = await stack.client.patch("/api/v1/org/settings", json={"default_language": "cobol"})
    assert resp.status_code == 400 and resp.json()["error"]["code"] == "unknown_language"
    settings = await stack.ok("GET", "/api/v1/org/settings")
    assert settings["ai_enabled"] is False


async def test_a_student_signs_up_and_is_signed_in(stack: Stack) -> None:
    async with stack.anonymous() as anon:
        resp = await anon.post("/api/v1/auth/signup", json=SIGNUP)
        assert resp.status_code == 201, resp.text
        token = resp.json()["session_token"]
        me = await anon.get("/api/v1/auth/me", headers={"authorization": f"Bearer {token}"})
        assert me.json()["role"] == "student" and me.json()["email"] == SIGNUP["email"]
        again = await anon.post("/api/v1/auth/signup", json=SIGNUP)
        assert again.status_code == 409
        weak = await anon.post(
            "/api/v1/auth/signup", json={**SIGNUP, "email": "w@example.test", "password": "short"}
        )
        assert weak.status_code == 400 and weak.json()["error"]["code"] == "weak_password"


async def test_sign_up_can_be_closed(stack: Stack) -> None:
    await stack.ok("PATCH", "/api/v1/org/settings", {"allow_signup": False})
    async with stack.anonymous() as anon:
        assert (await anon.get("/api/v1/org/public")).json()["allow_signup"] is False
        resp = await anon.post("/api/v1/auth/signup", json=SIGNUP)
    assert resp.status_code == 403 and resp.json()["error"]["code"] == "signup_closed"
