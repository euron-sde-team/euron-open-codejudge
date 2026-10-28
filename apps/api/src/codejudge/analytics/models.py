"""SQLAlchemy models for the analytics domain: a daily rollup of judged submissions."""

from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import Date, ForeignKey, Index, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from codejudge.core.db import Base


class StatsDaily(Base):
    """Judged submissions per day, problem and language, by verdict.

    Kept up to date by recomputing the one bucket a submission belongs to whenever it is
    judged (or rejudged), so it is always exactly what a scan would give, and the overview
    reads a few hundred rollup rows instead of every submission. ``users`` counts distinct
    authors within the bucket; summed across buckets it is an upper bound.
    """

    __tablename__ = "stats_daily"
    __table_args__ = (Index("ix_stats_daily_problem_day", "problem_id", "day"),)
    day: Mapped[date] = mapped_column(Date, primary_key=True)
    problem_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("problems.id", ondelete="CASCADE"), primary_key=True
    )
    language: Mapped[str] = mapped_column(String(32), primary_key=True)
    submissions: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    accepted: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    wrong_answer: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    time_limit: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    memory_limit: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    runtime_error: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    compile_error: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    output_limit: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    internal_error: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    users: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
