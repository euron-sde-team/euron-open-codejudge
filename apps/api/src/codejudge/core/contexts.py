"""Where a submission happens decides who may make it: one policy per context.

``practice`` is the problem list; ``contest``, ``assignment`` and ``assessment`` belong to
their domains, which register a policy here at import time. The submissions domain asks
the policy before accepting a submission and tells every listener after one is judged
(contest scoreboards, gradebooks, analytics), so it never imports those domains and they
never reach into its tables.
"""

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

from sqlalchemy.ext.asyncio import AsyncSession

if TYPE_CHECKING:
    from codejudge.core.container import Container
    from codejudge.problems.models import Problem
    from codejudge.submissions.models import Submission


@dataclass(frozen=True)
class Submitter:
    """A signed-in user, or an interview candidate (no account) identified by the
    assessment attempt their one-time link opened."""

    user_id: uuid.UUID | None
    candidate_id: uuid.UUID | None
    role: str  # student, staff, admin, candidate

    @property
    def is_staff(self) -> bool:
        return self.role in ("staff", "admin")


@dataclass(frozen=True)
class Admission:
    late: bool = False
    # Contestants in a frozen ICPC contest see "pending" for others; their own verdicts
    # are always shown. Hidden test details can be withheld per context.
    show_test_details: bool = True


class ContextPolicy(Protocol):
    async def admit(
        self, session: AsyncSession, who: Submitter, problem: Problem, context_id: uuid.UUID | None
    ) -> Admission:
        """Allow the submission (returning how to treat it) or raise an AppError."""
        ...

    async def can_view(self, session: AsyncSession, who: Submitter, submission: Submission) -> bool:
        """Whether someone other than the author may see this submission."""
        ...


Listener = Callable[["Container", AsyncSession, "Submission"], Awaitable[None]]

_POLICIES: dict[str, ContextPolicy] = {}
_LISTENERS: list[Listener] = []


def register(context: str, policy: ContextPolicy) -> None:
    _POLICIES[context] = policy


def policy(context: str) -> ContextPolicy | None:
    return _POLICIES.get(context)


def on_judged(listener: Listener) -> Listener:
    """Register a coroutine called (in the ingest transaction) after a submission is
    judged. Listeners must be idempotent: a rejudge calls them again."""
    _LISTENERS.append(listener)
    return listener


def listeners() -> list[Listener]:
    return list(_LISTENERS)
