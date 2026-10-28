"""Dashboard authentication: session cookie (browser) or bearer session token (API).

Cookie-authenticated mutations must carry ``X-CodeJudge-CSRF: 1``. Browsers cannot add a
custom header to a cross-site request without a CORS preflight, which the allowlist
refuses, so this blocks CSRF without server-side token state.
"""

from __future__ import annotations

from collections.abc import Callable, Coroutine
from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import Depends, Request
from sqlalchemy import delete
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from codejudge.audit.service import Actor
from codejudge.auth.models import RevokedSession
from codejudge.core.contexts import Submitter
from codejudge.core.deps import ContainerDep, SessionDep, client_ip
from codejudge.core.errors import AuthenticationError, PermissionDeniedError
from codejudge.core.security import SessionClaims, decode_session
from codejudge.users.models import User

SESSION_COOKIE = "cj_session"
CSRF_HEADER = "x-codejudge-csrf"
ROLE_RANK = {"student": 0, "staff": 1, "admin": 2}
_SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


async def is_revoked(session: AsyncSession, claims: SessionClaims) -> bool:
    """A signed-out session stays refused until it would have expired anyway (a primary
    key lookup in Postgres: durable, and never evicted like a cache entry)."""
    if not claims.jti:
        return False
    return await session.get(RevokedSession, claims.jti) is not None


async def revoke(session: AsyncSession, claims: SessionClaims) -> None:
    """Record a signed-out session and prune rows whose tokens have expired anyway."""
    if not claims.jti or claims.expires_at is None:
        return
    now = datetime.now(UTC)
    await session.execute(delete(RevokedSession).where(RevokedSession.expires_at < now))
    if claims.expires_at > now:
        await session.execute(
            insert(RevokedSession)
            .values(jti=claims.jti, expires_at=claims.expires_at)
            .on_conflict_do_nothing()
        )


def session_token(request: Request) -> tuple[str | None, bool]:
    """The session token and whether it came from the cookie."""
    header = request.headers.get("authorization", "")
    token = header[7:].strip() if header.lower().startswith("bearer ") else None
    if token:
        return token, False
    cookie = request.cookies.get(SESSION_COOKIE)
    return cookie, cookie is not None


async def current_user(request: Request, container: ContainerDep, session: SessionDep) -> User:
    # An explicit Authorization header wins: browsers never attach it cross-site, so it
    # needs no CSRF check. The cookie is the fallback for the dashboard.
    token, via_cookie = session_token(request)
    if not token:
        raise AuthenticationError("Sign in to continue", code="not_signed_in")
    claims = decode_session(token, container.settings.session_secret)
    if claims is None or await is_revoked(session, claims):
        raise AuthenticationError("Your session expired. Sign in again", code="session_expired")
    user = await session.get(User, claims.user_id)
    if user is None or user.disabled or user.session_version != claims.session_version:
        raise AuthenticationError("Your session expired. Sign in again", code="session_expired")
    if (
        via_cookie
        and request.method not in _SAFE_METHODS
        and request.headers.get(CSRF_HEADER) != "1"
    ):
        raise PermissionDeniedError("Missing CSRF header", code="csrf_required")
    request.state.actor = Actor(user.id, user.email, user.role, client_ip(request))
    return user


CurrentUser = Annotated[User, Depends(current_user)]


def require_role(role: str) -> Callable[..., Coroutine[Any, Any, Actor]]:
    async def dependency(request: Request, user: CurrentUser) -> Actor:
        if ROLE_RANK.get(user.role, -1) < ROLE_RANK[role]:
            raise PermissionDeniedError(
                f"This action needs the {role} role", code="insufficient_role"
            )
        actor: Actor = request.state.actor
        return actor

    return dependency


Student = Annotated[Actor, Depends(require_role("student"))]
Staff = Annotated[Actor, Depends(require_role("staff"))]
Admin = Annotated[Actor, Depends(require_role("admin"))]


# Interview candidates have no account: their one-time link gives them a candidate token,
# which the assessments domain resolves (registered at import time, see contexts.py).
CANDIDATE_HEADER = "x-codejudge-candidate"
CandidateResolver = Callable[[Request, AsyncSession, str], Coroutine[Any, Any, Submitter]]
_candidate_resolver: list[CandidateResolver] = []


def register_candidate_resolver(resolver: CandidateResolver) -> None:
    _candidate_resolver[:] = [resolver]


async def current_submitter(
    request: Request, container: ContainerDep, session: SessionDep
) -> Submitter:
    token = request.headers.get(CANDIDATE_HEADER)
    if token and _candidate_resolver:
        return await _candidate_resolver[0](request, session, token)
    user = await current_user(request, container, session)
    return Submitter(user_id=user.id, candidate_id=None, role=user.role)


CurrentSubmitter = Annotated[Submitter, Depends(current_submitter)]


async def optional_submitter(
    request: Request, container: ContainerDep, session: SessionDep
) -> Submitter:
    """Signed in or not: anonymous visitors browse public problems as students."""
    if request.headers.get(CANDIDATE_HEADER) or session_token(request)[0]:
        try:
            return await current_submitter(request, container, session)
        except AuthenticationError:
            pass
    return Submitter(user_id=None, candidate_id=None, role="student")


OptionalSubmitter = Annotated[Submitter, Depends(optional_submitter)]
