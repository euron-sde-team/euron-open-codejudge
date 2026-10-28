"""SQLAlchemy models for interview assessments.

An assessment is a timed set of problems. Each candidate gets an *invitation*: a one-time
link whose token is stored only as an HMAC (keyed with ``INVITE_TOKEN_PEPPER``), so a
database leak does not hand out working links. Opening the link starts the candidate's
timer. Candidates have no account: their submissions carry ``candidate_id = <invitation
id>`` and ``context = "assessment"``.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from codejudge.core.db import Base, TimestampMixin, new_id


class Assessment(TimestampMixin, Base):
    __tablename__ = "assessments"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_id)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    instructions_md: Mapped[str] = mapped_column(Text, nullable=False, default="")
    duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=60)
    # Optional window in which links work at all (a link opened late still gets the full
    # duration, capped at closes_at).
    opens_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    closes_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )


class AssessmentProblem(Base):
    __tablename__ = "assessment_problems"
    assessment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("assessments.id", ondelete="CASCADE"), primary_key=True
    )
    problem_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("problems.id", ondelete="CASCADE"), primary_key=True
    )
    points: Mapped[float] = mapped_column(Float, nullable=False, default=100.0)
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class Invitation(TimestampMixin, Base):
    __tablename__ = "invitations"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_id)
    assessment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("assessments.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    # HMAC-SHA256 of the link token; the token itself is only ever in the email.
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    # invited, started, submitted, expired, revoked
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="invited", index=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deadline_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    events_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    invited_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )


class CandidateEvent(Base):
    """What the candidate's browser reported: started, paste, tab_hidden, tab_visible,
    submitted. Signals for the interviewer to look at, never proof of anything."""

    __tablename__ = "candidate_events"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    invitation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("invitations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    detail: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
