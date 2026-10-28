"""HTTP endpoints for interview assessments: staff manage them, candidates take them.

Candidate endpoints live under ``/api/v1/candidate``. Apart from the session exchange,
they authenticate with the ``X-CodeJudge-Candidate`` header (see ``service``), and the
candidate submits through the ordinary ``/api/v1/submissions`` and ``/api/v1/runs`` with
``context = "assessment"`` and ``context_id = <invitation id>``.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Response

from codejudge.assessments import service
from codejudge.assessments.models import Invitation
from codejudge.assessments.schemas import (
    AssessmentCreate,
    AssessmentOut,
    AssessmentUpdate,
    CandidatePreview,
    CandidateSessionIn,
    CandidateView,
    EventIn,
    InvitationOut,
    InviteRequest,
    InviteResult,
    Report,
)
from codejudge.auth.dependencies import CurrentSubmitter, Staff
from codejudge.core.deps import ContainerDep, SessionDep
from codejudge.core.errors import NotFoundError

router = APIRouter(prefix="/api/v1", tags=["assessments"])


@router.get("/assessments", response_model=list[AssessmentOut])
async def list_assessments(_: Staff, session: SessionDep) -> list[AssessmentOut]:
    return await service.list_all(session)


@router.post("/assessments", response_model=AssessmentOut, status_code=201)
async def create_assessment(
    body: AssessmentCreate, actor: Staff, session: SessionDep
) -> AssessmentOut:
    return await service.out(session, await service.create(session, body, actor))


@router.get("/assessments/{assessment_id}", response_model=AssessmentOut)
async def get_assessment(assessment_id: uuid.UUID, _: Staff, session: SessionDep) -> AssessmentOut:
    return await service.out(session, await service.get(session, assessment_id))


@router.patch("/assessments/{assessment_id}", response_model=AssessmentOut)
async def update_assessment(
    assessment_id: uuid.UUID, body: AssessmentUpdate, actor: Staff, session: SessionDep
) -> AssessmentOut:
    a = await service.update_assessment(
        session, await service.get(session, assessment_id), body, actor
    )
    return await service.out(session, a)


@router.delete("/assessments/{assessment_id}", status_code=204)
async def delete_assessment(
    assessment_id: uuid.UUID, actor: Staff, session: SessionDep
) -> Response:
    await service.delete(session, await service.get(session, assessment_id), actor)
    return Response(status_code=204)


@router.get("/assessments/{assessment_id}/invitations", response_model=list[InvitationOut])
async def list_invitations(
    assessment_id: uuid.UUID, _: Staff, session: SessionDep
) -> list[InvitationOut]:
    return await service.invitations(session, await service.get(session, assessment_id))


@router.post(
    "/assessments/{assessment_id}/invitations", response_model=InviteResult, status_code=201
)
async def invite(
    assessment_id: uuid.UUID,
    body: InviteRequest,
    actor: Staff,
    session: SessionDep,
    container: ContainerDep,
) -> InviteResult:
    a = await service.get(session, assessment_id)
    return await service.invite(container, session, a, body.candidates, actor)


@router.post(
    "/assessments/{assessment_id}/invitations/{invitation_id}/resend", response_model=InvitationOut
)
async def resend(
    assessment_id: uuid.UUID,
    invitation_id: uuid.UUID,
    actor: Staff,
    session: SessionDep,
    container: ContainerDep,
) -> InvitationOut:
    a = await service.get(session, assessment_id)
    return await service.resend(
        container, session, a, await service.get_invitation(session, a, invitation_id), actor
    )


@router.post(
    "/assessments/{assessment_id}/invitations/{invitation_id}/revoke", response_model=InvitationOut
)
async def revoke(
    assessment_id: uuid.UUID, invitation_id: uuid.UUID, actor: Staff, session: SessionDep
) -> InvitationOut:
    a = await service.get(session, assessment_id)
    return await service.revoke(
        session, await service.get_invitation(session, a, invitation_id), actor
    )


@router.get(
    "/assessments/{assessment_id}/invitations/{invitation_id}/report", response_model=Report
)
async def report(
    assessment_id: uuid.UUID, invitation_id: uuid.UUID, _: Staff, session: SessionDep
) -> Report:
    a = await service.get(session, assessment_id)
    return await service.report(session, a, await service.get_invitation(session, a, invitation_id))


# ── candidate ────────────────────────────────────────────────────────────────────────
@router.post("/candidate/preview", response_model=CandidatePreview)
async def candidate_preview(
    body: CandidateSessionIn, session: SessionDep, container: ContainerDep
) -> CandidatePreview:
    """What the link is for, before starting: title, duration, instructions, window. A POST
    so the token never lands in a URL or an access log."""
    return await service.preview(container, session, body.token)


@router.post("/candidate/session", response_model=CandidateView)
async def candidate_session(
    body: CandidateSessionIn, session: SessionDep, container: ContainerDep
) -> CandidateView:
    """Open the invitation link: starts the timer the first time. The page then sends the
    same token as ``X-CodeJudge-Candidate`` on every request."""
    from codejudge.core.contexts import Submitter

    inv = await service.open_session(container, session, body.token)
    who = Submitter(user_id=None, candidate_id=inv.id, role="candidate")
    return await service.candidate_view(session, inv, who)


async def _mine(session: SessionDep, who: CurrentSubmitter) -> Invitation:
    inv = await session.get(Invitation, service.require_candidate(who))
    if inv is None:
        raise NotFoundError("Invitation not found")
    return inv


@router.get("/candidate/assessment", response_model=CandidateView)
async def candidate_assessment(who: CurrentSubmitter, session: SessionDep) -> CandidateView:
    return await service.candidate_view(session, await _mine(session, who), who)


@router.post("/candidate/events", status_code=204)
async def candidate_event(
    body: EventIn, who: CurrentSubmitter, session: SessionDep, container: ContainerDep
) -> Response:
    await service.record_event(
        container, session, await _mine(session, who), body.kind, body.detail
    )
    return Response(status_code=204)


@router.post("/candidate/finish", response_model=CandidateView)
async def candidate_finish(who: CurrentSubmitter, session: SessionDep) -> CandidateView:
    inv = await service.finish(session, await _mine(session, who))
    return await service.candidate_view(session, inv, who)
