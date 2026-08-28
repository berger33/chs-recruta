from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..advanced_models import ESocialEvent, ESocialEventStatus, InvoiceStatus, SaaSInvoice, UsageRecord
from ..advanced_schemas import (
    BillingSummary,
    ESocialEventCreate,
    ESocialEventRead,
    ESocialEventTransition,
    InvoiceCreate,
    InvoiceRead,
    InvoiceUpdate,
    UsageRecordCreate,
    UsageRecordRead,
)
from ..database import get_db
from ..models import Employee, Subscription
from ..permissions import Permission
from ..security import AuthContext, require_permissions
from ..services import audit, model_snapshot

router = APIRouter(prefix="/api", tags=["integrations-billing"])

ESOCIAL_TRANSITIONS = {
    ESocialEventStatus.draft: {ESocialEventStatus.validated},
    ESocialEventStatus.validated: {ESocialEventStatus.queued},
    ESocialEventStatus.queued: {ESocialEventStatus.sent, ESocialEventStatus.rejected},
    ESocialEventStatus.sent: {ESocialEventStatus.accepted, ESocialEventStatus.rejected},
    ESocialEventStatus.rejected: {ESocialEventStatus.queued},
    ESocialEventStatus.accepted: set(),
}


def scoped_event(db: Session, tenant_id: int, event_id: int) -> ESocialEvent:
    item = db.scalar(
        select(ESocialEvent).where(ESocialEvent.id == event_id, ESocialEvent.tenant_id == tenant_id)
    )
    if not item:
        raise HTTPException(status_code=404, detail="Evento eSocial não encontrado")
    return item


@router.get("/esocial/events", response_model=list[ESocialEventRead])
def list_esocial_events(
    context: Annotated[AuthContext, Depends(require_permissions(Permission.esocial_manage))],
    db: Annotated[Session, Depends(get_db)],
    status_filter: ESocialEventStatus | None = None,
):
    statement = select(ESocialEvent).where(ESocialEvent.tenant_id == context.tenant_id)
    if status_filter:
        statement = statement.where(ESocialEvent.status == status_filter)
    return db.scalars(statement.order_by(ESocialEvent.updated_at.desc())).all()


@router.post("/esocial/events", response_model=ESocialEventRead, status_code=201)
def create_esocial_event(
    payload: ESocialEventCreate,
    request: Request,
    context: Annotated[AuthContext, Depends(require_permissions(Permission.esocial_manage))],
    db: Annotated[Session, Depends(get_db)],
):
    if payload.employee_id is not None and not db.scalar(
        select(Employee.id).where(
            Employee.id == payload.employee_id,
            Employee.tenant_id == context.tenant_id,
        )
    ):
        raise HTTPException(status_code=404, detail="Colaborador não encontrado nesta empresa")
    item = ESocialEvent(
        tenant_id=context.tenant_id,
        created_by_id=context.user.id,
        **payload.model_dump(),
    )
    db.add(item)
    try:
        db.flush()
    except IntegrityError as error:
        db.rollback()
        raise HTTPException(status_code=409, detail="Evento já existe para a chave de idempotência") from error
    audit(
        db,
        context=context,
        request=request,
        action="create",
        entity="esocial_event",
        entity_id=str(item.id),
        details=f"{item.event_type}:{item.reference}",
        after=model_snapshot(item),
    )
    db.commit()
    db.refresh(item)
    return item


@router.patch("/esocial/events/{event_id}", response_model=ESocialEventRead)
def transition_esocial_event(
    event_id: int,
    payload: ESocialEventTransition,
    request: Request,
    context: Annotated[AuthContext, Depends(require_permissions(Permission.esocial_manage))],
    db: Annotated[Session, Depends(get_db)],
):
    item = scoped_event(db, context.tenant_id, event_id)
    if payload.status not in ESOCIAL_TRANSITIONS[item.status]:
        raise HTTPException(
            status_code=409,
            detail=f"Transição inválida: {item.status.value} → {payload.status.value}",
        )
    if payload.status == ESocialEventStatus.accepted and not payload.receipt.strip():
        raise HTTPException(status_code=422, detail="Recibo oficial é obrigatório para registrar aceite")
    before = model_snapshot(item)
    if payload.status == ESocialEventStatus.queued:
        item.attempts += 1
        item.error_message = ""
    item.status = payload.status
    item.receipt = payload.receipt
    item.error_message = payload.error_message
    audit(
        db,
        context=context,
        request=request,
        action="transition",
        entity="esocial_event",
        entity_id=str(item.id),
        details=f"{before['status']} → {item.status.value}",
        before=before,
        after=model_snapshot(item),
    )
    db.commit()
    db.refresh(item)
    return item


@router.get("/billing/summary", response_model=BillingSummary)
def billing_summary(
    context: Annotated[AuthContext, Depends(require_permissions(Permission.billing_manage))],
    db: Annotated[Session, Depends(get_db)],
):
    subscription = db.scalar(select(Subscription).where(Subscription.tenant_id == context.tenant_id))
    if not subscription:
        raise HTTPException(status_code=404, detail="Assinatura ainda não configurada")
    usage = db.scalars(
        select(UsageRecord).where(UsageRecord.tenant_id == context.tenant_id).order_by(UsageRecord.period.desc())
    ).all()
    invoices = db.scalars(
        select(SaaSInvoice)
        .where(
            SaaSInvoice.tenant_id == context.tenant_id,
            SaaSInvoice.status.in_([InvoiceStatus.open, InvoiceStatus.past_due]),
        )
        .order_by(SaaSInvoice.due_date)
    ).all()
    return BillingSummary(
        plan_code=subscription.plan_code,
        subscription_status=subscription.status.value,
        employee_limit=subscription.employee_limit,
        enabled_modules=subscription.enabled_modules,
        usage=usage,
        open_invoices=invoices,
    )


@router.get("/billing/usage", response_model=list[UsageRecordRead])
def list_usage(
    context: Annotated[AuthContext, Depends(require_permissions(Permission.billing_manage))],
    db: Annotated[Session, Depends(get_db)],
):
    return db.scalars(
        select(UsageRecord).where(UsageRecord.tenant_id == context.tenant_id).order_by(UsageRecord.period.desc())
    ).all()


@router.put("/billing/usage", response_model=UsageRecordRead)
def upsert_usage(
    payload: UsageRecordCreate,
    request: Request,
    context: Annotated[AuthContext, Depends(require_permissions(Permission.billing_manage))],
    db: Annotated[Session, Depends(get_db)],
):
    item = db.scalar(
        select(UsageRecord).where(
            UsageRecord.tenant_id == context.tenant_id,
            UsageRecord.metric == payload.metric,
            UsageRecord.period == payload.period,
        )
    )
    before = model_snapshot(item) if item else None
    if item:
        item.quantity = payload.quantity
    else:
        item = UsageRecord(tenant_id=context.tenant_id, **payload.model_dump())
        db.add(item)
        db.flush()
    audit(
        db,
        context=context,
        request=request,
        action="upsert",
        entity="usage_record",
        entity_id=str(item.id),
        details=f"{item.metric}:{item.period}",
        before=before,
        after=model_snapshot(item),
    )
    db.commit()
    db.refresh(item)
    return item


@router.get("/billing/invoices", response_model=list[InvoiceRead])
def list_invoices(
    context: Annotated[AuthContext, Depends(require_permissions(Permission.billing_manage))],
    db: Annotated[Session, Depends(get_db)],
):
    return db.scalars(
        select(SaaSInvoice).where(SaaSInvoice.tenant_id == context.tenant_id).order_by(SaaSInvoice.due_date.desc())
    ).all()


@router.post("/billing/invoices", response_model=InvoiceRead, status_code=201)
def create_invoice(
    payload: InvoiceCreate,
    request: Request,
    context: Annotated[AuthContext, Depends(require_permissions(Permission.billing_manage))],
    db: Annotated[Session, Depends(get_db)],
):
    item = SaaSInvoice(tenant_id=context.tenant_id, **payload.model_dump())
    db.add(item)
    try:
        db.flush()
    except IntegrityError as error:
        db.rollback()
        raise HTTPException(status_code=409, detail="Número de fatura já existe") from error
    audit(
        db,
        context=context,
        request=request,
        action="create",
        entity="saas_invoice",
        entity_id=str(item.id),
        details=item.number,
        after=model_snapshot(item),
    )
    db.commit()
    db.refresh(item)
    return item


@router.patch("/billing/invoices/{invoice_id}", response_model=InvoiceRead)
def update_invoice(
    invoice_id: int,
    payload: InvoiceUpdate,
    request: Request,
    context: Annotated[AuthContext, Depends(require_permissions(Permission.billing_manage))],
    db: Annotated[Session, Depends(get_db)],
):
    item = db.scalar(
        select(SaaSInvoice).where(
            SaaSInvoice.id == invoice_id,
            SaaSInvoice.tenant_id == context.tenant_id,
        )
    )
    if not item:
        raise HTTPException(status_code=404, detail="Fatura não encontrada")
    before = model_snapshot(item)
    item.status = payload.status
    if payload.provider_reference is not None:
        item.provider_reference = payload.provider_reference
    audit(
        db,
        context=context,
        request=request,
        action="update_status",
        entity="saas_invoice",
        entity_id=str(item.id),
        before=before,
        after=model_snapshot(item),
    )
    db.commit()
    db.refresh(item)
    return item
