"""API application factory."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware

from codejudge import __version__
from codejudge.analytics.router import router as analytics_router
from codejudge.assessments.router import router as assessments_router
from codejudge.audit.router import router as audit_router
from codejudge.auth.router import router as auth_router
from codejudge.classrooms.router import router as classrooms_router
from codejudge.contests.router import router as contests_router
from codejudge.core.config import Settings, get_settings
from codejudge.core.container import Container
from codejudge.core.db import import_all_models
from codejudge.core.errors import install_error_handlers
from codejudge.core.logs import configure_logging
from codejudge.core.middleware import BodySizeLimitMiddleware, RequestContextMiddleware
from codejudge.core.tracing import configure_tracing
from codejudge.hints.router import router as hints_router
from codejudge.org.router import router as org_router
from codejudge.plagiarism.router import router as plagiarism_router
from codejudge.problems.router import router as problems_router
from codejudge.submissions.router import internal as judge_internal_router
from codejudge.submissions.router import router as submissions_router
from codejudge.system.router import router as system_router
from codejudge.users.router import router as users_router

DESCRIPTION = """
API of a self-hosted coding assessment platform: problems with hidden tests, submissions
judged in an unprivileged sandbox, contests with ICPC and IOI scoreboards, classes with
assignments, interview assessments, plagiarism checks and optional AI hints.

* Sign in with `POST /api/v1/auth/login`; send the session token as
  `Authorization: Bearer <token>` (the dashboard uses an HttpOnly cookie instead).
* `POST /api/v1/submissions` queues a submission; `GET /api/v1/submissions/{id}/events`
  streams its progress and verdict (server-sent events).
* Interview candidates use the token from their invitation link in the
  `X-CodeJudge-Candidate` header instead of a session.

Judge workers are a separate service that reaches only `/internal/judge/*`.
"""


def create_app(settings: Settings | None = None, container: Container | None = None) -> FastAPI:
    settings = settings or get_settings()
    import_all_models()
    configure_logging(settings.log_level)
    configure_tracing(settings)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.container = container or Container.build(settings)
        try:
            yield
        finally:
            if container is None:
                await app.state.container.close()

    app = FastAPI(
        title="Euron Open CodeJudge",
        version=__version__,
        description=DESCRIPTION,
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url=None,
        openapi_url="/openapi.json",
        separate_input_output_schemas=False,
    )
    install_error_handlers(app)
    for router in (
        auth_router,
        users_router,
        problems_router,
        submissions_router,
        contests_router,
        classrooms_router,
        assessments_router,
        plagiarism_router,
        analytics_router,
        hints_router,
        org_router,
        audit_router,
        system_router,
        judge_internal_router,
    ):
        app.include_router(router)

    app.add_middleware(GZipMiddleware, minimum_size=2048)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=[
            "authorization",
            "content-type",
            "x-codejudge-csrf",
            "x-codejudge-candidate",
            "x-request-id",
        ],
        expose_headers=["x-request-id", "retry-after", "content-disposition"],
        max_age=600,
    )
    app.add_middleware(BodySizeLimitMiddleware, settings=settings)
    app.add_middleware(RequestContextMiddleware)
    return app
