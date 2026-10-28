"""SQLAlchemy models for the contests domain.

A contest is a time window, a list of problems with labels, and the people registered for
it. Results are not stored here: the scoreboard is computed from the contest's
submissions (context ``contest``), so a rejudge changes the board without any extra
bookkeeping.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from codejudge.core.db import Base, TimestampMixin, new_id


class Contest(TimestampMixin, Base):
    __tablename__ = "contests"
    __table_args__ = (Index("ix_contests_window", "starts_at", "ends_at"),)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_id)
    slug: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description_md: Mapped[str] = mapped_column(Text, nullable=False, default="")
    # icpc: problems solved, then penalty minutes. ioi: sum of the best score per problem.
    format: Mapped[str] = mapped_column(String(8), nullable=False, default="icpc")
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    # From this moment contestants see later attempts as pending, until staff unfreeze.
    freeze_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    unfrozen: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # public: listed for everyone; private: only participants and staff see it.
    visibility: Mapped[str] = mapped_column(
        String(16), nullable=False, default="public", index=True
    )
    # open: anyone who sees it may register; invite: only with the join code.
    registration: Mapped[str] = mapped_column(String(16), nullable=False, default="open")
    join_code: Mapped[str | None] = mapped_column(String(16), unique=True)
    penalty_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=20)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )


class ContestProblem(Base):
    __tablename__ = "contest_problems"
    __table_args__ = (
        UniqueConstraint("contest_id", "label"),
        UniqueConstraint("contest_id", "problem_id"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_id)
    contest_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("contests.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    problem_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("problems.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    label: Mapped[str] = mapped_column(String(4), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # IOI: what a full score on this problem is worth in the contest.
    points: Mapped[float] = mapped_column(Float, nullable=False, default=100.0)


class ContestParticipant(Base):
    __tablename__ = "contest_participants"
    __table_args__ = (UniqueConstraint("contest_id", "user_id"),)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_id)
    contest_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("contests.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    registered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class Clarification(TimestampMixin, Base):
    __tablename__ = "clarifications"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_id)
    contest_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("contests.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    problem_label: Mapped[str | None] = mapped_column(String(4))
    question: Mapped[str] = mapped_column(Text, nullable=False)
    answer: Mapped[str | None] = mapped_column(Text)
    # Public: every participant sees it (announcements and answers useful to all).
    public: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    asked_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    answered_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    answered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
