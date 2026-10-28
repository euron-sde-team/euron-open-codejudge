"""SQLAlchemy models for the classrooms domain.

A class has members (teachers and students) and assignments. An assignment is a set of
problems with points, an opening time, a due time and a late policy. Submissions made for
an assignment carry ``context = "assignment"`` and ``context_id = <assignment id>``; the
gradebook reads them from the submissions table, so nothing here duplicates a verdict.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from codejudge.core.db import Base, TimestampMixin, new_id


class Classroom(TimestampMixin, Base):
    __tablename__ = "classes"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    # Students join with this code; teachers can rotate it.
    join_code: Mapped[str] = mapped_column(String(16), unique=True, nullable=False)
    archived: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )


class ClassMember(Base):
    __tablename__ = "class_members"
    class_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("classes.id", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True, index=True
    )
    # teacher | student
    role: Mapped[str] = mapped_column(String(16), nullable=False, default="student")
    joined_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class Assignment(TimestampMixin, Base):
    __tablename__ = "assignments"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_id)
    class_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("classes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description_md: Mapped[str] = mapped_column(Text, nullable=False, default="")
    opens_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    # accept: late work counts in full (marked late); penalty: late scores lose
    # penalty_percent; refuse: no submissions after the due time.
    late_policy: Mapped[str] = mapped_column(String(16), nullable=False, default="penalty")
    penalty_percent: Mapped[int] = mapped_column(Integer, nullable=False, default=20)


class AssignmentProblem(Base):
    __tablename__ = "assignment_problems"
    __table_args__ = (UniqueConstraint("assignment_id", "problem_id"),)
    assignment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("assignments.id", ondelete="CASCADE"), primary_key=True
    )
    problem_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("problems.id", ondelete="CASCADE"), primary_key=True
    )
    points: Mapped[float] = mapped_column(Float, nullable=False, default=100.0)
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class AssignmentExtension(Base):
    """A later due time for one student (illness, accommodations)."""

    __tablename__ = "assignment_extensions"
    assignment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("assignments.id", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
