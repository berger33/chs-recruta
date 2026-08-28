from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..advanced_models import (
    ApplicationStageHistory,
    Interview,
    JobRequisition,
    Offer,
    OfferStatus,
    RequisitionStatus,
    Scorecard,
)
from ..advanced_schemas import (
    InterviewCreate,
    InterviewRead,
    InterviewUpdate,
    JobRequisitionCreate,
    JobRequisitionRead,
    OfferCreate,
    OfferRead,
    OfferStatusUpdate,
    RequisitionDecision,
    ScorecardCreate,
    ScorecardRead,
    StageHistoryRead,
    StageTransition,
)
from ..database import get_db
from ..models import Application, ApplicationStage, Department, Membership, User
from ..permissions import Permission
from ..security import AuthContext, require_permissions
from ..services import audit, model_snapshot

router = APIRouter(prefix="/api/ats", tags=["ats-advanced"])


def scoped(db: Session, model, tenant_id: int, object_id: int, detail: str):
    item = db.scalar(select(model).where(model.id == object_id, model.tenant_id == tenant_id))
    if not item:
        raise HTTPException(status_code=404, detail=detail)
    return item


def scoped_application(db: Session, context: AuthContext, application_id: int) -> Application:
    return scoped(db, Application, context.tenant_id, application_id, "Candidatura não encontrada")


def validate_tenant_users(db: Session, tenant_id: int, user_ids: list[int]) -> None:
    if not user_ids:
        return
    found = set(
        db.scalars(
            select(Membership.user_id).where(
                Membership.tenant_id == tenant_id,
                Membership.user_id.in_(set(user_ids)),
                Membership.active.is_(True),
            )
        ).all()
    )
    missing = set(user_ids) - found
    if missing:
        raise HTTPException(status_code=404, detail=f"Usuários não pertencem à empresa: {sorted(missing)}")


@router.get("/requisitions", response_model=list[JobRequisitionRead])
def list_requisitions(
    context: Annotated[AuthContext, Depends(require_permissions(Permission.vacancies_read))],
    db: Annotated[Session, Depends(get_db)],
    status_filter: RequisitionStatus | None = Query(default=None, alias="status"),
):
    statement = select(JobRequisition).where(JobRequisition.tenant_id == context.tenant_id)
    if status_filter:
        statement = statement.where(JobRequisition.status == status_filter)
    return db.scalars(statement.order_by(JobRequisition.updated_at.desc())).all()


@router.post("/requisitions", response_model=JobRequisitionRead, status_code=201)
def create_requisition(
    payload: JobRequisitionCreate,
    request: Request,
    context: Annotated[AuthContext, Depends(require_permissions(Permission.vacancies_write))],
    db: Annotated[Session, Depends(get_db)],
):
    if payload.department_id is not None and not db.scalar(
        select(Department.id).where(
            Department.id == payload.department_id,
            Department.tenant_id == context.tenant_id,
        )
    ):
        raise HTTPException(status_code=404, detail="Departamento não encontrado nesta empresa")
    item = JobRequisition(
        tenant_id=context.tenant_id,
        requested_by_id=context.user.id,
        status=RequisitionStatus.pending,
        **payload.model_dump(),
    )
    db.add(item)
    try:
        db.flush()
    except IntegrityError as error:
        db.rollback()
        raise HTTPException(status_code=409, detail="Código de requisição já existe") from error
    audit(
        db,
        context=context,
        request=request,
        action="submit",
        entity="job_requisition",
        entity_id=str(item.id),
        details=item.title,
        after=model_snapshot(item),
    )
    db.commit()
    db.refresh(item)
    return item


@router.post("/requisitions/{requisition_id}/decision", response_model=JobRequisitionRead)
def decide_requisition(
    requisition_id: int,
    payload: RequisitionDecision,
    request: Request,
    context: Annotated[AuthContext, Depends(require_permissions(Permission.vacancies_write))],
    db: Annotated[Session, Depends(get_db)],
):
    item = scoped(db, JobRequisition, context.tenant_id, requisition_id, "Requisição não encontrada")
    if item.status not in {RequisitionStatus.pending, RequisitionStatus.draft}:
        raise HTTPException(status_code=409, detail="Requisição já possui decisão")
    before = model_snapshot(item)
    item.status = RequisitionStatus.approved if payload.approved else RequisitionStatus.rejected
    item.approved_by_id = context.user.id
    item.approved_at = datetime.now(UTC).replace(tzinfo=None)
    if payload.reason:
        item.description = f"{item.description}\n\nDecisão: {payload.reason}".strip()
    audit(
        db,
        context=context,
        request=request,
        action="approve" if payload.approved else "reject",
        entity="job_requisition",
        entity_id=str(item.id),
        details=payload.reason,
        before=before,
        after=model_snapshot(item),
    )
    db.commit()
    db.refresh(item)
    return item


@router.post("/applications/{application_id}/stage", response_model=StageHistoryRead)
def transition_application(
    application_id: int,
    payload: StageTransition,
    request: Request,
    context: Annotated[AuthContext, Depends(require_permissions(Permission.applications_manage))],
    db: Annotated[Session, Depends(get_db)],
):
    application = scoped_application(db, context, application_id)
    try:
        target = ApplicationStage(payload.stage)
    except ValueError as error:
        allowed = [item.value for item in ApplicationStage]
        raise HTTPException(status_code=422, detail=f"Etapa inválida. Use uma de: {allowed}") from error
    if application.stage == target:
        raise HTTPException(status_code=409, detail="A candidatura já está nesta etapa")
    before = model_snapshot(application)
    history = ApplicationStageHistory(
        tenant_id=context.tenant_id,
        application_id=application.id,
        from_stage=application.stage.value,
        to_stage=target.value,
        reason=payload.reason,
        changed_by_id=context.user.id,
    )
    application.stage = target
    db.add(history)
    db.flush()
    audit(
        db,
        context=context,
        request=request,
        action="update_stage",
        entity="application",
        entity_id=str(application.id),
        details=payload.reason,
        before=before,
        after=model_snapshot(application),
    )
    db.commit()
    db.refresh(history)
    return history


@router.get("/applications/{application_id}/history", response_model=list[StageHistoryRead])
def application_history(
    application_id: int,
    context: Annotated[AuthContext, Depends(require_permissions(Permission.candidates_read))],
    db: Annotated[Session, Depends(get_db)],
):
    scoped_application(db, context, application_id)
    return db.scalars(
        select(ApplicationStageHistory)
        .where(
            ApplicationStageHistory.tenant_id == context.tenant_id,
            ApplicationStageHistory.application_id == application_id,
        )
        .order_by(ApplicationStageHistory.changed_at)
    ).all()


@router.get("/interviews", response_model=list[InterviewRead])
def list_interviews(
    context: Annotated[AuthContext, Depends(require_permissions(Permission.candidates_read))],
    db: Annotated[Session, Depends(get_db)],
    application_id: int | None = None,
):
    statement = select(Interview).where(Interview.tenant_id == context.tenant_id)
    if application_id is not None:
        scoped_application(db, context, application_id)
        statement = statement.where(Interview.application_id == application_id)
    return db.scalars(statement.order_by(Interview.scheduled_at.desc())).all()


@router.post("/interviews", response_model=InterviewRead, status_code=201)
def create_interview(
    payload: InterviewCreate,
    request: Request,
    context: Annotated[AuthContext, Depends(require_permissions(Permission.applications_manage))],
    db: Annotated[Session, Depends(get_db)],
):
    scoped_application(db, context, payload.application_id)
    validate_tenant_users(db, context.tenant_id, payload.interviewer_ids)
    item = Interview(tenant_id=context.tenant_id, created_by_id=context.user.id, **payload.model_dump())
    db.add(item)
    db.flush()
    audit(
        db,
        context=context,
        request=request,
        action="schedule",
        entity="interview",
        entity_id=str(item.id),
        details=item.location,
        after=model_snapshot(item),
    )
    db.commit()
    db.refresh(item)
    return item


@router.patch("/interviews/{interview_id}", response_model=InterviewRead)
def update_interview(
    interview_id: int,
    payload: InterviewUpdate,
    request: Request,
    context: Annotated[AuthContext, Depends(require_permissions(Permission.applications_manage))],
    db: Annotated[Session, Depends(get_db)],
):
    item = scoped(db, Interview, context.tenant_id, interview_id, "Entrevista não encontrada")
    if payload.interviewer_ids is not None:
        validate_tenant_users(db, context.tenant_id, payload.interviewer_ids)
    before = model_snapshot(item)
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(item, key, value)
    audit(
        db,
        context=context,
        request=request,
        action="update",
        entity="interview",
        entity_id=str(item.id),
        before=before,
        after=model_snapshot(item),
    )
    db.commit()
    db.refresh(item)
    return item


@router.post("/interviews/{interview_id}/scorecards", response_model=ScorecardRead, status_code=201)
def submit_scorecard(
    interview_id: int,
    payload: ScorecardCreate,
    request: Request,
    context: Annotated[AuthContext, Depends(require_permissions(Permission.applications_manage))],
    db: Annotated[Session, Depends(get_db)],
):
    interview = scoped(db, Interview, context.tenant_id, interview_id, "Entrevista não encontrada")
    if context.user.id not in interview.interviewer_ids and context.membership.role.value not in {
        "tenant_owner",
        "admin",
        "hr",
    }:
        raise HTTPException(status_code=403, detail="Somente entrevistadores autorizados podem avaliar")
    item = Scorecard(
        tenant_id=context.tenant_id,
        interview_id=interview.id,
        evaluator_id=context.user.id,
        **payload.model_dump(),
    )
    db.add(item)
    try:
        db.flush()
    except IntegrityError as error:
        db.rollback()
        raise HTTPException(status_code=409, detail="Avaliador já enviou scorecard") from error
    audit(
        db,
        context=context,
        request=request,
        action="submit",
        entity="scorecard",
        entity_id=str(item.id),
        details=item.recommendation,
        after=model_snapshot(item),
    )
    db.commit()
    db.refresh(item)
    return item


@router.get("/offers", response_model=list[OfferRead])
def list_offers(
    context: Annotated[AuthContext, Depends(require_permissions(Permission.candidates_read))],
    db: Annotated[Session, Depends(get_db)],
):
    return db.scalars(
        select(Offer).where(Offer.tenant_id == context.tenant_id).order_by(Offer.updated_at.desc())
    ).all()


@router.post("/offers", response_model=OfferRead, status_code=201)
def create_offer(
    payload: OfferCreate,
    request: Request,
    context: Annotated[AuthContext, Depends(require_permissions(Permission.applications_manage))],
    db: Annotated[Session, Depends(get_db)],
):
    scoped_application(db, context, payload.application_id)
    item = Offer(tenant_id=context.tenant_id, created_by_id=context.user.id, **payload.model_dump())
    db.add(item)
    db.flush()
    audit(
        db,
        context=context,
        request=request,
        action="create",
        entity="offer",
        entity_id=str(item.id),
        after=model_snapshot(item),
    )
    db.commit()
    db.refresh(item)
    return item


@router.patch("/offers/{offer_id}/status", response_model=OfferRead)
def update_offer_status(
    offer_id: int,
    payload: OfferStatusUpdate,
    request: Request,
    context: Annotated[AuthContext, Depends(require_permissions(Permission.applications_manage))],
    db: Annotated[Session, Depends(get_db)],
):
    item = scoped(db, Offer, context.tenant_id, offer_id, "Oferta não encontrada")
    before = model_snapshot(item)
    item.status = payload.status
    audit(
        db,
        context=context,
        request=request,
        action="update_status",
        entity="offer",
        entity_id=str(item.id),
        details=payload.reason,
        before=before,
        after=model_snapshot(item),
    )
    if payload.status == OfferStatus.accepted:
        application = scoped_application(db, context, item.application_id)
        if application.stage != ApplicationStage.contratado:
            db.add(
                ApplicationStageHistory(
                    tenant_id=context.tenant_id,
                    application_id=application.id,
                    from_stage=application.stage.value,
                    to_stage=ApplicationStage.contratado.value,
                    reason="Oferta aceita",
                    changed_by_id=context.user.id,
                )
            )
            application.stage = ApplicationStage.contratado
    db.commit()
    db.refresh(item)
    return item
