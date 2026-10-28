"""SQLAlchemy models for the plagiarism domain: check runs and the pairs they flag."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from codejudge.core.db import Base, new_id


class PlagiarismRun(Base):
    """One similarity check over a scope: a problem, a contest or an assignment.

    queued -> running -> done | failed. The background worker claims queued runs with
    ``FOR UPDATE SKIP LOCKED``; a run left ``running`` by a worker that died is claimed
    again after a while.
    """

    __tablename__ = "plagiarism_runs"
    __table_args__ = (Index("ix_plagiarism_runs_scope", "scope", "scope_id", "created_at"),)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_id)
    # problem, contest, assignment
    scope: Mapped[str] = mapped_column(String(16), nullable=False)
    scope_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    threshold: Mapped[float] = mapped_column(Float, nullable=False, default=0.5)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="queued", index=True)
    documents: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    comparisons: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    flagged: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class PlagiarismPair(Base):
    """Two submissions to the same problem whose similarity reached the run's threshold."""

    __tablename__ = "plagiarism_pairs"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_id)
    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("plagiarism_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    problem_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("problems.id", ondelete="CASCADE"), nullable=False
    )
    language: Mapped[str] = mapped_column(String(32), nullable=False)
    submission_a: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("submissions.id", ondelete="CASCADE"), nullable=False
    )
    submission_b: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("submissions.id", ondelete="CASCADE"), nullable=False
    )
    similarity: Mapped[float] = mapped_column(Float, nullable=False)
    coverage_a: Mapped[float] = mapped_column(Float, nullable=False)
    coverage_b: Mapped[float] = mapped_column(Float, nullable=False)
    # [[first_line, last_line], ...] on each side, for the side-by-side view.
    ranges_a: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    ranges_b: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
