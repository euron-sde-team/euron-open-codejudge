"""Database engine, session factory and the declarative base shared by every domain."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def new_id() -> uuid.UUID:
    return uuid.uuid4()


class Base(DeclarativeBase):
    type_annotation_map = {dict[str, Any]: JSONB, list[str]: JSONB}


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class Database:
    """Owns the engine and session factory for one application instance."""

    def __init__(self, url: str, *, pool_size: int = 10, max_overflow: int = 20) -> None:
        self.engine: AsyncEngine = create_async_engine(
            url,
            pool_size=pool_size,
            max_overflow=max_overflow,
            pool_pre_ping=True,
            pool_recycle=1800,
            # Never echo bound values (password hashes, key hashes, content) into an
            # exception message, and so never into a log line.
            hide_parameters=True,
        )
        self.sessionmaker = async_sessionmaker(self.engine, expire_on_commit=False)

    async def session(self) -> AsyncIterator[AsyncSession]:
        async with self.sessionmaker() as session:
            yield session

    async def dispose(self) -> None:
        await self.engine.dispose()


def import_all_models() -> None:
    """Import every domain's models so Base.metadata is complete (Alembic, tests)."""
    from codejudge.analytics import models as _analytics  # noqa: F401
    from codejudge.assessments import models as _assessments  # noqa: F401
    from codejudge.audit import models as _audit  # noqa: F401
    from codejudge.auth import models as _auth  # noqa: F401
    from codejudge.classrooms import models as _classrooms  # noqa: F401
    from codejudge.contests import models as _contests  # noqa: F401
    from codejudge.hints import models as _hints  # noqa: F401
    from codejudge.org import models as _org  # noqa: F401
    from codejudge.plagiarism import models as _plagiarism  # noqa: F401
    from codejudge.problems import models as _problems  # noqa: F401
    from codejudge.submissions import models as _submissions  # noqa: F401
    from codejudge.users import models as _users  # noqa: F401
