"""SQLAlchemy models for submissions and their judging.

A submission is judged by a *job*: ``job_id`` names the job currently responsible for it.
Rejudging starts a new job; a result is accepted only for the submission's current job and
only once, which makes ingestion idempotent however many times a worker retries or a job
is redelivered.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from codejudge.core.db import Base, new_id


class Submission(Base):
    __tablename__ = "submissions"
    __table_args__ = (
        Index("ix_submissions_user_created", "user_id", "created_at"),
        Index("ix_submissions_problem_created", "problem_id", "created_at"),
        Index("ix_submissions_context", "context", "context_id", "created_at"),
        # Time windows across everyone (active people in analytics, run cleanup).
        Index("ix_submissions_created", "created_at"),
        Index("ix_submissions_status", "status", postgresql_where="status <> 'done'"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_id)
    # Null for interview candidates, who have no account (``candidate_id`` names them).
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    candidate_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), index=True)
    problem_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("problems.id", ondelete="CASCADE"), nullable=False
    )
    version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("problem_versions.id", ondelete="CASCADE"), nullable=False
    )
    language: Mapped[str] = mapped_column(String(32), nullable=False)
    source: Mapped[str] = mapped_column(Text, nullable=False)
    # practice, contest, assignment, assessment, reference, run (custom input / samples)
    context: Mapped[str] = mapped_column(String(16), nullable=False, default="practice")
    context_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    # queued -> judging -> done
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="queued")
    verdict: Mapped[str] = mapped_column(String(8), nullable=False, default="PENDING")
    score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    max_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    time_ms: Mapped[int | None] = mapped_column(Integer)
    memory_kb: Mapped[int | None] = mapped_column(Integer)
    compile_output: Mapped[str | None] = mapped_column(Text)
    tests: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False, default=list)
    groups: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False, default=list)
    # Only for runs on samples or custom input.
    run_input: Mapped[str | None] = mapped_column(Text)
    run_output: Mapped[str | None] = mapped_column(Text)
    only_tests: Mapped[list[str] | None] = mapped_column(JSONB)
    # Submitted after the assignment's deadline (kept and shown, scored per the policy).
    late: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # Set by the context (an ICPC contest while it runs, an interview): non-staff then see
    # the overall verdict and the public samples, not how many hidden tests passed.
    hide_test_details: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    job_id: Mapped[str] = mapped_column(String(32), nullable=False, unique=True)
    attempt: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    worker: Mapped[str | None] = mapped_column(String(100))
    progress: Mapped[str | None] = mapped_column(String(40))
    error: Mapped[str | None] = mapped_column(Text)
    judged_ms: Mapped[int | None] = mapped_column(Integer)
    rejudged: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    judged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
