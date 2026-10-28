"""SQLAlchemy models for the problems domain.

A problem's tests live in an immutable *version*: a zip in the Kattis package layout stored
by its SHA-256. Editing tests creates a new version; submissions record the version they
were judged against, so rejudging and contest results stay reproducible. Sample tests are
copied into the version row (they are public); hidden tests exist only inside the package.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from codejudge.core.db import Base, TimestampMixin, new_id


class Problem(TimestampMixin, Base):
    __tablename__ = "problems"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_id)
    slug: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    statement_md: Mapped[str] = mapped_column(Text, nullable=False, default="")
    difficulty: Mapped[str] = mapped_column(String(16), nullable=False, default="medium")
    tags: Mapped[list[str]] = mapped_column(ARRAY(String(40)), nullable=False, default=list)
    time_limit_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=2000)
    memory_limit_mb: Mapped[int] = mapped_column(Integer, nullable=False, default=256)
    output_limit_mb: Mapped[int] = mapped_column(Integer, nullable=False, default=64)
    checker: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    # draft: only staff see it; published: listed for everyone (or used in contests).
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="draft", index=True)
    # public: in the practice list; private: only through contests, classes, assessments.
    visibility: Mapped[str] = mapped_column(String(16), nullable=False, default="public")
    source: Mapped[str | None] = mapped_column(String(200))
    license: Mapped[str | None] = mapped_column(String(64))
    current_version_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("problem_versions.id", use_alter=True, ondelete="SET NULL")
    )
    author_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    # Denormalised counters for the problem list (updated when a submission is judged).
    submissions_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    accepted_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    solvers_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class ProblemVersion(Base):
    __tablename__ = "problem_versions"
    __table_args__ = (UniqueConstraint("problem_id", "number"),)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_id)
    problem_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("problems.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    number: Mapped[int] = mapped_column(Integer, nullable=False)
    package_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    package_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    # [{name, group, sample, input_bytes, answer_bytes}] in judging order.
    tests: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False, default=list)
    # [{name, points, stop_on_failure}]
    groups: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False, default=list)
    # Public sample content for the statement: [{name, input, output}] (bounded size).
    samples: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False, default=list)
    checker: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    max_score: Mapped[float] = mapped_column(Float, nullable=False, default=100.0)
    note: Mapped[str | None] = mapped_column(String(200))
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class ReferenceSolution(TimestampMixin, Base):
    """A setter's solution and the verdict it must get. A problem is publishable only when
    every reference solution gets its expected verdict on the current version."""

    __tablename__ = "reference_solutions"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_id)
    problem_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("problems.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    language: Mapped[str] = mapped_column(String(32), nullable=False)
    source: Mapped[str] = mapped_column(Text, nullable=False)
    expected: Mapped[str] = mapped_column(String(8), nullable=False, default="AC")
    last_submission_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
