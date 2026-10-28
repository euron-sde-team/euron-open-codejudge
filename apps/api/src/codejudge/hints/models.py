"""SQLAlchemy models for the hints domain: one row per hint asked for."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from codejudge.core.db import Base, new_id


class HintRequest(Base):
    """A hint request and how it went. ``pending`` reserves a slot under the cap while the
    provider is called (so parallel requests cannot exceed it); ``failed`` ones do not
    count."""

    __tablename__ = "hint_requests"
    __table_args__ = (Index("ix_hint_requests_user_problem", "user_id", "problem_id"),)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_id)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    problem_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("problems.id", ondelete="CASCADE"), nullable=False
    )
    submission_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    context: Mapped[str] = mapped_column(String(16), nullable=False, default="practice")
    model: Mapped[str | None] = mapped_column(String(120))
    # pending, ok, failed
    status: Mapped[str] = mapped_column(String(8), nullable=False, default="pending")
    prompt_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    completion_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
