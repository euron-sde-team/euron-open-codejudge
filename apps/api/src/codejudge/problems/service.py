"""Problem lifecycle: create, edit, versions of tests, import and export, publishing.

A problem is published only when it has tests and every reference solution gets the
verdict it is supposed to get on the current version: a setter cannot publish a problem
whose own accepted solution fails, which is how most broken judges go wrong.
"""

from __future__ import annotations

import io
import uuid
import zipfile
from typing import Any

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from codejudge.audit.service import Actor, audit
from codejudge.core.config import Settings
from codejudge.core.container import Container
from codejudge.core.contexts import Submitter
from codejudge.core.contract import CheckerSpec, GroupSpec
from codejudge.core.errors import AppError, ConflictError, NotFoundError, PermissionDeniedError
from codejudge.judge import languages as language_registry
from codejudge.problems import packages
from codejudge.problems.models import Problem, ProblemVersion, ReferenceSolution
from codejudge.problems.schemas import (
    ImportResult,
    LanguageOut,
    ProblemAdmin,
    ProblemCreate,
    ProblemOut,
    ProblemSummary,
    ProblemUpdate,
    ReferenceIn,
    ReferenceOut,
    Sample,
    TestMeta,
    VersionCreate,
    VersionOut,
)
from codejudge.submissions.models import Submission

COUNTED = ("practice", "contest", "assignment", "assessment")


def package_key(sha256: str) -> str:
    return f"packages/{sha256}.zip"


def languages_out(problem: Problem | None = None) -> list[LanguageOut]:
    out = []
    for lang in language_registry.registry().values():
        out.append(
            LanguageOut(
                id=lang.id,
                name=lang.name,
                monaco=lang.monaco,
                template=lang.template,
                time_limit_ms=lang.time_limit_ms(problem.time_limit_ms) if problem else None,
            )
        )
    return out


# ── reading ──────────────────────────────────────────────────────────────────────────
def _acceptance(p: Problem) -> float | None:
    return round(p.accepted_count / p.submissions_count, 4) if p.submissions_count else None


def summary(p: Problem, mine: str | None = None) -> ProblemSummary:
    return ProblemSummary(
        id=p.id,
        slug=p.slug,
        title=p.title,
        difficulty=p.difficulty,
        tags=list(p.tags or []),
        status=p.status,
        visibility=p.visibility,
        submissions_count=p.submissions_count,
        accepted_count=p.accepted_count,
        solvers_count=p.solvers_count,
        acceptance=_acceptance(p),
        mine=mine,
        updated_at=p.updated_at,
    )


async def get(session: AsyncSession, ref: str | uuid.UUID) -> Problem:
    """By id or by slug."""
    try:
        pid = ref if isinstance(ref, uuid.UUID) else uuid.UUID(str(ref))
        row = await session.get(Problem, pid)
    except ValueError:
        row = await session.scalar(select(Problem).where(Problem.slug == str(ref)))
    if row is None:
        raise NotFoundError("Problem not found")
    return row


def can_practice(p: Problem, who: Submitter) -> bool:
    return who.is_staff or (p.status == "published" and p.visibility == "public")


async def version(session: AsyncSession, p: Problem) -> ProblemVersion | None:
    if p.current_version_id is None:
        return None
    return await session.get(ProblemVersion, p.current_version_id)


async def mine_map(
    session: AsyncSession, user_id: uuid.UUID | None, ids: list[uuid.UUID]
) -> dict[uuid.UUID, str]:
    """solved / attempted per problem for one user, in one query."""
    if user_id is None or not ids:
        return {}
    solved = func.bool_or(Submission.verdict == "AC")
    rows = await session.execute(
        select(Submission.problem_id, solved)
        .where(
            Submission.user_id == user_id,
            Submission.problem_id.in_(ids),
            Submission.context.in_(COUNTED),
        )
        .group_by(Submission.problem_id)
    )
    return {pid: ("solved" if ok else "attempted") for pid, ok in rows.all()}


async def list_problems(
    session: AsyncSession,
    who: Submitter,
    *,
    q: str | None = None,
    tag: str | None = None,
    difficulty: str | None = None,
    status: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[ProblemSummary], int]:
    query = select(Problem)
    if not who.is_staff:
        query = query.where(Problem.status == "published", Problem.visibility == "public")
    elif status:
        query = query.where(Problem.status == status)
    if q:
        like = f"%{q.strip()[:80]}%"
        query = query.where(or_(Problem.title.ilike(like), Problem.slug.ilike(like)))
    if tag:
        query = query.where(Problem.tags.any(tag.lower()))  # type: ignore[arg-type]
    if difficulty:
        query = query.where(Problem.difficulty == difficulty)
    total = int(await session.scalar(select(func.count()).select_from(query.subquery())) or 0)
    rows = list(
        (
            await session.scalars(
                query.order_by(Problem.created_at.desc(), Problem.id).limit(limit).offset(offset)
            )
        ).all()
    )
    mine = await mine_map(session, who.user_id, [p.id for p in rows])
    return [summary(p, mine.get(p.id)) for p in rows], total


async def detail(
    session: AsyncSession, p: Problem, who: Submitter, *, check_access: bool = True
) -> ProblemOut:
    if check_access and not can_practice(p, who):
        raise NotFoundError("Problem not found")
    v = await version(session, p)
    mine = (await mine_map(session, who.user_id, [p.id])).get(p.id)
    checker = CheckerSpec.model_validate(p.checker or {})
    return ProblemOut(
        **summary(p, mine).model_dump(),
        statement_md=p.statement_md,
        time_limit_ms=p.time_limit_ms,
        memory_limit_mb=p.memory_limit_mb,
        output_limit_mb=p.output_limit_mb,
        checker=checker.kind,
        max_score=v.max_score if v else 0.0,
        groups=[GroupSpec.model_validate(g) for g in (v.groups if v else [])],
        samples=[Sample.model_validate(s) for s in (v.samples if v else [])],
        languages=languages_out(p),
        source=p.source,
        license=p.license,
        version=v.number if v else None,
    )


def _version_out(v: ProblemVersion, current: uuid.UUID | None) -> VersionOut:
    return VersionOut(
        id=v.id,
        number=v.number,
        package_sha256=v.package_sha256,
        package_bytes=v.package_bytes,
        tests=[TestMeta.model_validate(t) for t in v.tests],
        groups=[GroupSpec.model_validate(g) for g in v.groups],
        checker=CheckerSpec.model_validate(v.checker or {}),
        max_score=v.max_score,
        note=v.note,
        current=v.id == current,
        created_at=v.created_at,
    )


async def admin_detail(session: AsyncSession, p: Problem, who: Submitter) -> ProblemAdmin:
    base = await detail(session, p, who, check_access=False)
    versions = list(
        (
            await session.scalars(
                select(ProblemVersion)
                .where(ProblemVersion.problem_id == p.id)
                .order_by(ProblemVersion.number.desc())
            )
        ).all()
    )
    refs = await references(session, p)
    blockers = await publish_blockers(session, p, refs)
    return ProblemAdmin(
        **base.model_dump(),
        checker_spec=CheckerSpec.model_validate(p.checker or {}),
        versions=[_version_out(v, p.current_version_id) for v in versions],
        references=refs,
        publishable=not blockers,
        publish_blockers=blockers,
    )


# ── writing ──────────────────────────────────────────────────────────────────────────
async def create(session: AsyncSession, data: ProblemCreate, actor: Actor) -> Problem:
    if await session.scalar(select(Problem.id).where(Problem.slug == data.slug)):
        raise ConflictError(f"A problem with the slug {data.slug!r} exists", code="slug_taken")
    values = data.model_dump(exclude={"checker"})
    p = Problem(id=uuid.uuid4(), author_id=actor.id, checker=data.checker.model_dump(), **values)
    session.add(p)
    await session.flush()
    audit(session, actor, "problem.created", "problem", p.id, slug=p.slug)
    await session.commit()
    await session.refresh(p)
    return p


async def update(session: AsyncSession, p: Problem, data: ProblemUpdate, actor: Actor) -> Problem:
    changes = data.model_dump(exclude_unset=True)
    for required in (
        "title",
        "slug",
        "difficulty",
        "time_limit_ms",
        "memory_limit_mb",
        "output_limit_mb",
        "visibility",
    ):
        if required in changes and changes[required] is None:
            changes.pop(required)
    if (
        "slug" in changes
        and changes["slug"] != p.slug
        and await session.scalar(select(Problem.id).where(Problem.slug == changes["slug"]))
    ):
        raise ConflictError(
            f"A problem with the slug {changes['slug']!r} exists", code="slug_taken"
        )
    for field, value in changes.items():
        setattr(p, field, value)
    audit(session, actor, "problem.updated", "problem", p.id, fields=sorted(changes))
    await session.commit()
    await session.refresh(p)
    return p


async def delete(session: AsyncSession, p: Problem, actor: Actor) -> None:
    audit(session, actor, "problem.deleted", "problem", p.id, slug=p.slug)
    await session.delete(p)
    await session.commit()


async def set_status(session: AsyncSession, p: Problem, status: str, actor: Actor) -> Problem:
    if status == "published":
        blockers = await publish_blockers(session, p, await references(session, p))
        if blockers:
            raise AppError(
                "This problem cannot be published yet: " + "; ".join(blockers),
                code="not_publishable",
                details={"blockers": blockers},
            )
    p.status = status
    audit(
        session,
        actor,
        f"problem.{'published' if status == 'published' else 'unpublished'}",
        "problem",
        p.id,
    )
    await session.commit()
    await session.refresh(p)
    return p


async def _store_version(
    container: Container,
    session: AsyncSession,
    p: Problem,
    pkg: packages.Package,
    actor: Actor,
    note: str | None,
) -> ProblemVersion:
    """Build the package, store it by hash, and make it the current version."""
    _check_groups(pkg)
    data = packages.build(pkg)
    if len(data) > container.settings.max_package_bytes:
        raise AppError("The tests are larger than the package limit", code="package_too_large")
    sha = packages.sha256(data)
    await container.storage.put(package_key(sha), data, "application/zip")
    number = (
        int(
            await session.scalar(
                select(func.coalesce(func.max(ProblemVersion.number), 0)).where(
                    ProblemVersion.problem_id == p.id
                )
            )
            or 0
        )
        + 1
    )
    tests = [
        {
            "name": t.name,
            "group": t.group,
            "sample": t.sample,
            "input_bytes": len(t.input),
            "answer_bytes": len(t.answer),
        }
        for t in pkg.tests
    ]
    v = ProblemVersion(
        id=uuid.uuid4(),
        problem_id=p.id,
        number=number,
        package_sha256=sha,
        package_bytes=len(data),
        tests=tests,
        groups=[g.model_dump() for g in pkg.groups],
        samples=packages.samples(pkg),
        checker=pkg.checker.model_dump(),
        max_score=sum(g.points for g in pkg.groups),
        note=note,
        created_by=actor.id,
    )
    session.add(v)
    await session.flush()
    p.current_version_id = v.id
    p.checker = pkg.checker.model_dump()
    audit(
        session,
        actor,
        "problem.tests_changed",
        "problem",
        p.id,
        version=number,
        tests=len(tests),
        sha256=sha,
    )
    return v


def _check_groups(pkg: packages.Package) -> None:
    names = {t.group for t in pkg.tests}
    declared = {g.name for g in pkg.groups}
    if names - declared:
        raise AppError(
            f"Tests use groups that have no settings: {', '.join(sorted(names - declared))}",
            code="unknown_group",
        )
    if not any(not t.sample for t in pkg.tests):
        raise AppError(
            "Add at least one hidden test (secret/...): samples alone cannot judge",
            code="no_hidden_tests",
        )
    if pkg.checker.kind == "custom" and not pkg.checker_source:
        raise AppError("A custom checker needs its source", code="checker_source_required")


def groups_for(tests: list[packages.Test], given: list[GroupSpec]) -> list[GroupSpec]:
    """Declared groups, plus any group the tests use: samples score 0, the remaining hidden
    groups share the points not yet assigned (100 in total by default)."""
    by_name = {g.name: g for g in given}
    hidden = sorted({t.group for t in tests if not t.sample}, key=packages._natural)
    out: list[GroupSpec] = []
    if any(t.sample for t in tests):
        out.append(
            by_name.get("sample") or GroupSpec(name="sample", points=0, stop_on_failure=False)
        )
    assigned = sum(by_name[g].points for g in hidden if g in by_name)
    unassigned = [g for g in hidden if g not in by_name]
    share = round(max(0.0, 100 - assigned) / len(unassigned), 4) if unassigned else 0.0
    out += [by_name.get(g) or GroupSpec(name=g, points=share) for g in hidden]
    return out


async def create_version(
    container: Container, session: AsyncSession, p: Problem, data: VersionCreate, actor: Actor
) -> ProblemVersion:
    tests: list[packages.Test] = []
    seen: set[str] = set()
    for t in data.tests:
        if t.name in seen:
            raise AppError(f"Two tests are named {t.name!r}", code="duplicate_test")
        seen.add(t.name)
        parts = t.name.split("/")
        group = "sample" if parts[0] == "sample" else (parts[1] if len(parts) > 2 else "secret")
        tests.append(
            packages.Test(
                name=t.name,
                group=group,
                sample=parts[0] == "sample",
                input=t.input.encode(),
                answer=t.answer.encode(),
            )
        )
    tests.sort(key=lambda t: (not t.sample, packages._natural(t.name)))
    checker = data.checker or CheckerSpec.model_validate(p.checker or {})
    if checker.kind == "custom" and checker.path is None:
        suffix = next(
            (s for s, lang in packages.LANGUAGE_BY_SUFFIX.items() if lang == checker.language),
            ".txt",
        )
        checker = checker.model_copy(update={"path": f"output_validators/checker/checker{suffix}"})
    pkg = _package_for(
        p,
        tests,
        groups_for(tests, data.groups),
        checker,
        data.checker_source.encode()
        if data.checker_source
        else await _existing_checker(container, session, p, checker),
    )
    v = await _store_version(container, session, p, pkg, actor, data.note)
    await session.commit()
    return v


def _package_for(
    p: Problem,
    tests: list[packages.Test],
    groups: list[GroupSpec],
    checker: CheckerSpec,
    checker_source: bytes | None,
) -> packages.Package:
    return packages.Package(
        title=p.title,
        statement_md=p.statement_md,
        time_limit_ms=p.time_limit_ms,
        memory_limit_mb=p.memory_limit_mb,
        source=p.source,
        license=p.license,
        tests=tests,
        groups=groups,
        checker=checker,
        checker_source=checker_source,
    )


async def _existing_checker(
    container: Container, session: AsyncSession, p: Problem, checker: CheckerSpec
) -> bytes | None:
    if checker.kind != "custom" or not checker.path:
        return None
    v = await version(session, p)
    if v is None:
        return None
    with zipfile.ZipFile(
        io.BytesIO(await container.storage.get(package_key(v.package_sha256)))
    ) as z:
        try:
            return z.read(checker.path)
        except KeyError:
            return None


async def import_package(
    container: Container, session: AsyncSession, data: bytes, actor: Actor, slug: str | None = None
) -> ImportResult:
    if len(data) > container.settings.max_package_bytes:
        raise AppError("The package is larger than the limit", code="package_too_large")
    try:
        pkg = packages.parse(data)
    except packages.PackageFormatError as exc:
        raise AppError(f"This package cannot be imported: {exc}", code="bad_package") from exc
    warnings: list[str] = []
    base = slug or packages._safe(pkg.title).lower().replace("_", "-").strip("-")[:60] or "problem"
    candidate, n = base, 1
    while await session.scalar(select(Problem.id).where(Problem.slug == candidate)):
        n += 1
        candidate = f"{base[:56]}-{n}"
    if candidate != base:
        warnings.append(f"The slug {base!r} was taken; imported as {candidate!r}")
    max_ms, max_mb = container.settings.max_time_limit_ms, container.settings.max_memory_limit_mb
    time_ms = min(pkg.time_limit_ms or 2000, max_ms)
    memory_mb = min(pkg.memory_limit_mb or 256, max_mb)
    if pkg.time_limit_ms and pkg.time_limit_ms > max_ms:
        warnings.append(f"Time limit lowered to the server maximum ({max_ms} ms)")
    p = Problem(
        id=uuid.uuid4(),
        slug=candidate,
        title=pkg.title[:200],
        statement_md=pkg.statement_md,
        time_limit_ms=max(100, time_ms),
        memory_limit_mb=max(16, memory_mb),
        checker=pkg.checker.model_dump(),
        source=pkg.source,
        license=pkg.license,
        author_id=actor.id,
        status="draft",
    )
    session.add(p)
    await session.flush()
    # The judged package holds tests and checker only: reference solutions live in their
    # own rows (and go back into the package on export).
    references, pkg.references = pkg.references, []
    await _store_version(container, session, p, pkg, actor, "imported")
    pkg.references = references
    known = set(language_registry.registry())
    for name, language, source in pkg.references:
        if language in known:
            session.add(
                ReferenceSolution(
                    id=uuid.uuid4(),
                    problem_id=p.id,
                    name=name[:100],
                    language=language,
                    source=source,
                    expected="AC",
                )
            )
    audit(session, actor, "problem.imported", "problem", p.id, slug=p.slug, tests=len(pkg.tests))
    await session.commit()
    await session.refresh(p)
    return ImportResult(
        problem=summary(p),
        tests=len(pkg.tests),
        groups=len(pkg.groups),
        references=len(pkg.references),
        warnings=warnings,
    )


async def replace_package(
    container: Container, session: AsyncSession, p: Problem, data: bytes, actor: Actor
) -> ProblemVersion:
    """New tests (and checker) from an uploaded package; the statement and limits stay."""
    try:
        pkg = packages.parse(data)
    except packages.PackageFormatError as exc:
        raise AppError(f"This package cannot be used: {exc}", code="bad_package") from exc
    merged = _package_for(p, pkg.tests, pkg.groups, pkg.checker, pkg.checker_source)
    v = await _store_version(container, session, p, merged, actor, "package upload")
    await session.commit()
    return v


async def export(container: Container, session: AsyncSession, p: Problem) -> bytes:
    """The current tests with today's statement, limits and reference solutions."""
    v = await version(session, p)
    if v is None:
        raise AppError("This problem has no tests to export yet", code="no_tests")
    stored = packages.parse(await container.storage.get(package_key(v.package_sha256)))
    refs = [
        (r.name, r.language, r.source)
        for r in await _reference_rows(session, p)
        if r.expected == "AC"
    ]
    pkg = _package_for(
        p,
        stored.tests,
        [GroupSpec.model_validate(g) for g in v.groups],
        CheckerSpec.model_validate(v.checker),
        stored.checker_source,
    )
    pkg.references = refs
    return packages.build(pkg)


async def test_content(
    container: Container, session: AsyncSession, p: Problem, name: str, part: str
) -> bytes:
    v = await version(session, p)
    if v is None or not any(t["name"] == name for t in v.tests):
        raise NotFoundError("Test not found")
    with zipfile.ZipFile(
        io.BytesIO(await container.storage.get(package_key(v.package_sha256)))
    ) as z:
        return z.read(f"data/{name}.{'in' if part == 'input' else 'ans'}")


# ── reference solutions and publishing ───────────────────────────────────────────────
async def _reference_rows(session: AsyncSession, p: Problem) -> list[ReferenceSolution]:
    return list(
        (
            await session.scalars(
                select(ReferenceSolution)
                .where(ReferenceSolution.problem_id == p.id)
                .order_by(ReferenceSolution.created_at)
            )
        ).all()
    )


async def references(session: AsyncSession, p: Problem) -> list[ReferenceOut]:
    rows = await _reference_rows(session, p)
    ids = [r.last_submission_id for r in rows if r.last_submission_id]
    subs: dict[uuid.UUID, Submission] = {}
    if ids:
        subs = {
            s.id: s
            for s in (await session.scalars(select(Submission).where(Submission.id.in_(ids)))).all()
        }
    out = []
    for r in rows:
        s = subs.get(r.last_submission_id) if r.last_submission_id else None
        current = s is not None and s.version_id == p.current_version_id
        out.append(
            ReferenceOut(
                id=r.id,
                name=r.name,
                language=r.language,
                expected=r.expected,
                source=r.source,
                last_submission_id=r.last_submission_id,
                last_verdict=s.verdict if s else None,
                last_status=s.status if s else None,
                matches=(s.verdict == r.expected)
                if (s and s.status == "done" and current)
                else None,
            )
        )
    return out


async def publish_blockers(
    session: AsyncSession, p: Problem, refs: list[ReferenceOut]
) -> list[str]:
    blockers = []
    if p.current_version_id is None:
        blockers.append("add tests")
    if not any(r.expected == "AC" for r in refs):
        blockers.append("add a reference solution that should be accepted")
    for r in refs:
        if r.matches is None:
            blockers.append(f"judge the reference solution {r.name!r} on the current tests")
        elif not r.matches:
            blockers.append(
                f"the reference solution {r.name!r} got {r.last_verdict}, expected {r.expected}"
            )
    return blockers


async def add_reference(
    session: AsyncSession, p: Problem, data: ReferenceIn, actor: Actor
) -> ReferenceSolution:
    if data.language not in language_registry.registry():
        raise AppError(f"Unknown language {data.language!r}", code="unknown_language")
    r = ReferenceSolution(id=uuid.uuid4(), problem_id=p.id, **data.model_dump())
    session.add(r)
    audit(
        session, actor, "problem.reference_added", "problem", p.id, name=r.name, expected=r.expected
    )
    await session.commit()
    await session.refresh(r)
    return r


async def remove_reference(
    session: AsyncSession, p: Problem, ref_id: uuid.UUID, actor: Actor
) -> None:
    r = await session.get(ReferenceSolution, ref_id)
    if r is None or r.problem_id != p.id:
        raise NotFoundError("Reference solution not found")
    await session.delete(r)
    audit(session, actor, "problem.reference_removed", "problem", p.id, name=r.name)
    await session.commit()


def check_limits(settings: Settings, time_ms: int | None, memory_mb: int | None) -> None:
    """The server's upper bounds apply to every problem, however it was made."""
    if time_ms is not None and time_ms > settings.max_time_limit_ms:
        raise AppError(
            f"The time limit can be at most {settings.max_time_limit_ms} ms on this server",
            code="limit_too_high",
        )
    if memory_mb is not None and memory_mb > settings.max_memory_limit_mb:
        raise AppError(
            f"The memory limit can be at most {settings.max_memory_limit_mb} MB on this server",
            code="limit_too_high",
        )


def require_staff(who: Submitter) -> None:
    if not who.is_staff:
        raise PermissionDeniedError("Only staff can manage problems", code="insufficient_role")


def counted_filter() -> Any:
    return and_(Submission.context.in_(COUNTED))
