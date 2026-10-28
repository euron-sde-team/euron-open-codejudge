"""HTTP endpoints for organisation settings and self sign-up."""

from __future__ import annotations

from fastapi import APIRouter, Request, Response
from redis.exceptions import RedisError

from codejudge.auth.dependencies import Admin
from codejudge.auth.router import _session
from codejudge.auth.schemas import SignInOut
from codejudge.core.deps import ContainerDep, SessionDep, client_ip
from codejudge.core.errors import RateLimitedError
from codejudge.limits.limiter import LimitDecision
from codejudge.org import service
from codejudge.org.schemas import AdminSettings, PublicSettings, SettingsUpdate, SignupRequest

router = APIRouter(prefix="/api/v1", tags=["org"])
SIGNUP_RPM_PER_IP = 10


@router.get("/org/public", response_model=PublicSettings, summary="Settings the sign-in page needs")
async def public_settings(session: SessionDep) -> PublicSettings:
    return service.public(await service.get(session))


@router.get("/org/settings", response_model=AdminSettings, summary="Organisation settings")
async def get_settings(_: Admin, session: SessionDep) -> AdminSettings:
    return service.admin(await service.get(session))


@router.patch("/org/settings", response_model=AdminSettings, summary="Change organisation settings")
async def update_settings(
    body: SettingsUpdate, actor: Admin, session: SessionDep, container: ContainerDep
) -> AdminSettings:
    return service.admin(await service.update(container, session, body, actor))


@router.post(
    "/auth/signup",
    response_model=SignInOut,
    status_code=201,
    summary="Create a student account (when sign-up is open) and sign in",
)
async def signup(
    body: SignupRequest,
    request: Request,
    response: Response,
    container: ContainerDep,
    session: SessionDep,
) -> SignInOut:
    ip = client_ip(request)
    try:
        decision = await container.kv.hit(f"signup:{ip}", SIGNUP_RPM_PER_IP)
    except (RedisError, OSError):
        decision = LimitDecision(allowed=True)
    if not decision.allowed:
        raise RateLimitedError(
            "Too many sign-ups from this address. Wait a minute and try again",
            headers={"retry-after": str(decision.retry_after_s)},
        )
    user = await service.signup(session, body, ip)
    response.headers["cache-control"] = "no-store"
    return _session(response, container, user)
