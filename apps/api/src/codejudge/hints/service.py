"""Optional AI hints through any OpenAI-compatible endpoint (a local model or a provider).

Off by default: with AI disabled no request is ever made. When it is on, a hint is refused
in contests and assessments (always), in assignments unless the admin allows it, and after
the per-problem cap. The prompt carries the statement, the public samples, the student's
own code and the verdict of their last submission with the *name* of the first failing
test. Hidden test inputs and answers never enter the prompt: they are not even read here,
only the public sample content stored on the problem version is.
"""

from __future__ import annotations

import uuid
from datetime import timedelta
from typing import Any

import httpx
from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from codejudge.core.container import Container
from codejudge.core.contexts import Submitter
from codejudge.core.errors import AppError, NotFoundError, PermissionDeniedError, RateLimitedError
from codejudge.core.net import resolves_safely
from codejudge.hints.models import HintRequest
from codejudge.hints.schemas import HintOut, HintRequestIn, HintStatus
from codejudge.org import service as org
from codejudge.org.models import OrgSettings
from codejudge.problems import service as problems
from codejudge.problems.models import Problem, ProblemVersion
from codejudge.submissions import service as submissions
from codejudge.submissions.models import Submission

TIMEOUT_S = 30.0
MAX_STATEMENT = 8000
MAX_SOURCE = 12000
MAX_COMPILE_OUTPUT = 2000
NEVER = ("contest", "assessment")

SYSTEM_PROMPT = (
    "You are a patient programming tutor helping a student with a judged coding problem. "
    "Give one or two short hints that point at the mistake or the next idea. Do not write "
    "the corrected program and do not give a complete solution. Answer in plain text."
)


class HintProviderError(AppError):
    status_code = 502
    code = "ai_unavailable"


def refusal(row: OrgSettings, who: Submitter, context: str) -> tuple[str, str] | None:
    """(code, message) when hints are not available here, else None. Decided from the
    settings alone, before anything else is read or any request is made."""
    if who.user_id is None:
        return "ai_not_allowed", "Hints are not available in an assessment"
    if not row.ai_enabled or not row.ai_base_url or not row.ai_model:
        return "ai_disabled", "AI hints are turned off for this site"
    if context in NEVER:
        return "ai_not_allowed", f"Hints are never available during a {context}"
    if context == "assignment" and not row.ai_allowed_in_assignments:
        return "ai_not_allowed", "Your teacher has turned hints off for assignments"
    if context == "practice" and not row.ai_allowed_in_practice:
        return "ai_not_allowed", "Hints are turned off for practice"
    if row.ai_max_hints_per_problem <= 0:
        return "ai_disabled", "AI hints are turned off for this site"
    return None


async def used(session: AsyncSession, user_id: uuid.UUID, problem_id: uuid.UUID) -> int:
    """Hints given, plus ones in flight (a pending row older than the timeout is a request
    whose process died: it no longer holds its slot)."""
    stale = func.now() - timedelta(seconds=TIMEOUT_S * 2)
    count = await session.scalar(
        select(func.count())
        .select_from(HintRequest)
        .where(
            HintRequest.user_id == user_id,
            HintRequest.problem_id == problem_id,
            or_(
                HintRequest.status == "ok",
                and_(HintRequest.status == "pending", HintRequest.created_at > stale),
            ),
        )
    )
    return int(count or 0)


async def status(
    session: AsyncSession, who: Submitter, problem_ref: str, context: str
) -> HintStatus:
    row = await org.get(session)
    if (why := refusal(row, who, context)) is not None:
        return HintStatus(available=False, reason=why[1])
    assert who.user_id is not None
    p = await problems.get(session, problem_ref)
    n = await used(session, who.user_id, p.id)
    limit = row.ai_max_hints_per_problem
    return HintStatus(
        available=n < limit,
        reason=None if n < limit else "You have used every hint for this problem",
        used=n,
        limit=limit,
        remaining=max(0, limit - n),
    )


def _first_failing(s: Submission) -> str | None:
    for t in s.tests or []:
        if t.get("verdict") not in ("AC", "SKIPPED"):
            return str(t.get("name"))
    return None


def build_messages(
    *,
    title: str,
    statement: str,
    samples: list[dict[str, Any]],
    language: str,
    source: str,
    verdict: str | None,
    failing_test: str | None,
    compile_output: str | None,
    question: str | None,
) -> list[dict[str, str]]:
    """The chat messages. ``samples`` are the public samples; nothing else from the tests
    is ever passed in, so hidden data cannot reach the model."""
    parts = [f"Problem: {title}", "", statement[:MAX_STATEMENT].strip()]
    for s in samples[:3]:
        parts += ["", f"Sample {s['name']} input:", s["input"][:1000]]
        parts += ["Expected output:", s["output"][:1000]]
    parts += ["", f"The student's {language} code:", source[:MAX_SOURCE]]
    if verdict:
        line = f"Their last submission got {verdict}"
        if failing_test:
            where = (
                "a sample, shown above"
                if failing_test.startswith("sample/")
                else "a hidden test; its data is not available"
            )
            line += f", first failing on test {failing_test} ({where})"
        parts += ["", line + "."]
        if compile_output:
            parts += ["Compiler output:", compile_output[:MAX_COMPILE_OUTPUT]]
    parts += ["", f"The student asks: {question.strip()}" if question else "Give a hint."]
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": "\n".join(parts)},
    ]


async def _last_submission(
    session: AsyncSession, who: Submitter, p: Problem, submission_id: uuid.UUID | None
) -> Submission | None:
    if submission_id is not None:
        s = await session.get(Submission, submission_id)
        if s is None or s.user_id != who.user_id or s.problem_id != p.id:
            raise NotFoundError("Submission not found")
        if s.context in NEVER:
            raise PermissionDeniedError(
                f"Hints are never available during a {s.context}", code="ai_not_allowed"
            )
        return s
    return await session.scalar(
        select(Submission)
        .where(
            Submission.user_id == who.user_id,
            Submission.problem_id == p.id,
            Submission.status == "done",
            Submission.context.notin_(("reference", *NEVER)),
        )
        .order_by(Submission.created_at.desc())
        .limit(1)
    )


async def _call(
    container: Container, row: OrgSettings, messages: list[dict[str, str]]
) -> tuple[str, int, int]:
    base = (row.ai_base_url or "").rstrip("/")
    org.check_endpoint(container, base)
    if not await resolves_safely(base, allow_private=container.settings.ai_allow_private_endpoints):
        raise HintProviderError(
            "The AI endpoint resolves to a forbidden address. Check the URL in Settings",
            code="ai_endpoint_forbidden",
        )
    headers = {"content-type": "application/json"}
    if key := await org.ai_api_key(container, row):
        headers["authorization"] = f"Bearer {key}"
    body = {"model": row.ai_model, "messages": messages, "max_tokens": 400, "temperature": 0.2}
    try:
        resp = await container.http.post(
            f"{base}/chat/completions", json=body, headers=headers, timeout=TIMEOUT_S
        )
    except httpx.TimeoutException as exc:
        raise HintProviderError(
            "The AI provider took too long to answer. Try again in a moment"
        ) from exc
    except httpx.HTTPError as exc:
        raise HintProviderError(
            "The AI provider could not be reached. An administrator should check the "
            "endpoint URL in Settings"
        ) from exc
    if resp.status_code != 200:
        raise HintProviderError(
            f"The AI provider answered HTTP {resp.status_code}. An administrator should "
            "check the endpoint, model and key in Settings"
        )
    try:
        data = resp.json()
        text = str(data["choices"][0]["message"]["content"]).strip()
        usage = data.get("usage") or {}
    except (ValueError, KeyError, IndexError, TypeError) as exc:
        raise HintProviderError(
            "The AI provider's answer was not in the OpenAI chat format. Check the endpoint"
        ) from exc
    if not text:
        raise HintProviderError("The AI provider returned an empty hint. Try again")
    return text, int(usage.get("prompt_tokens") or 0), int(usage.get("completion_tokens") or 0)


async def request(
    container: Container, session: AsyncSession, who: Submitter, data: HintRequestIn
) -> HintOut:
    row = await org.get(session)
    if (why := refusal(row, who, data.context)) is not None:
        raise PermissionDeniedError(why[1], code=why[0])
    assert who.user_id is not None
    p = await problems.get(session, data.problem)
    # The same access rule as submitting here: no hints for a problem you cannot open.
    await submissions.admit(session, who, p, data.context, data.context_id)
    limit = row.ai_max_hints_per_problem
    last = await _last_submission(session, who, p, data.submission_id)
    version = (
        await session.get(ProblemVersion, p.current_version_id) if p.current_version_id else None
    )
    messages = build_messages(
        title=p.title,
        statement=p.statement_md,
        samples=list(version.samples) if version else [],
        language=data.language,
        source=data.source or (last.source if last else ""),
        verdict=last.verdict if last else None,
        failing_test=_first_failing(last) if last else None,
        compile_output=last.compile_output if last and last.verdict == "CE" else None,
        question=data.question,
    )
    # Reserve a slot under the cap: the check and the insert happen under one lock per
    # (user, problem), and the lock is released before the provider is called.
    await session.execute(
        select(func.pg_advisory_xact_lock(func.hashtext(f"hint:{who.user_id}:{p.id}")))
    )
    n = await used(session, who.user_id, p.id)
    if n >= limit:
        raise RateLimitedError(
            f"You have used all {limit} hints for this problem", code="hint_limit"
        )
    record = HintRequest(
        id=uuid.uuid4(),
        user_id=who.user_id,
        problem_id=p.id,
        submission_id=last.id if last else None,
        context=data.context,
        model=row.ai_model,
    )
    session.add(record)
    await session.commit()
    try:
        text, prompt_tokens, completion_tokens = await _call(container, row, messages)
    except AppError as exc:
        record.status, record.error = "failed", exc.message[:500]
        await session.commit()
        raise
    record.status = "ok"
    record.prompt_tokens, record.completion_tokens = prompt_tokens, completion_tokens
    await session.commit()
    return HintOut(
        hint=text,
        model=row.ai_model or "",
        used=n + 1,
        limit=limit,
        remaining=max(0, limit - n - 1),
    )
