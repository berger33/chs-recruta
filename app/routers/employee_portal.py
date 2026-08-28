from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Employee, Membership
from ..permissions import Permission
from ..portal_models import (
    EmployeeFile,
    EmployeeFileVisibility,
    EmployeeRequest,
    EmployeeRequestStatus,
    LeaveRequest,
    LeaveRequestStatus,
)
from ..portal_schemas import (
    EmployeeFileCreate,
    EmployeeFileRead,
    EmployeeRequestCreate,
    EmployeeRequestRead,
    EmployeeRequestTransition,
    LeaveRequestCreate,
    LeaveRequestRead,
    LeaveRequestTransition,
    PortalSummary,
)
from ..security import AuthContext, current_context, require_permissions
from ..services import audit, model_snapshot

router = APIRouter(prefix="/api/portal", tags=["employee-portal"])

REQUEST_TRANSITIONS = {
    EmployeeRequestStatus.submitted: {
        EmployeeRequestStatus.in_review,
        EmployeeRequestStatus.approved,
        EmployeeRequestStatus.rejected,
        EmployeeRequestStatus.resolved,
    },
    EmployeeRequestStatus.in_review: {
        EmployeeRequestStatus.approved,
        EmployeeRequestStatus.rejected,
        EmployeeRequestStatus.resolved,
    },
    EmployeeRequestStatus.approved: {EmployeeRequestStatus.resolved},
    EmployeeRequestStatus.rejected: set(),
    EmployeeRequestStatus.resolved: set(),
    EmployeeRequestStatus.cancelled: set(),
}
LEAVE_TRANSITIONS = {
    LeaveRequestStatus.submitted: {LeaveRequestStatus.approved, LeaveRequestStatus.rejected},
    LeaveRequestStatus.approved: {LeaveRequestStatus.cancelled},
    LeaveRequestStatus.rejected: set(),
    LeaveRequestStatus.cancelled: set(),
}


def now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def own_employee(db: Session, context: AuthContext, required: bool = True) -> Employee | None:
    employee = db.scalar(
        select(Employee).where(
            Employee.tenant_id == context.tenant_id,
            Employee.user_id == context.user.id,
        )
    )
    if required and not employee:
        raise HTTPException(status_code=403, detail="Usuário não está vinculado a um colaborador")
    return employee


def tenant_employee(db: Session, context: AuthContext, employee_id: int) -> Employee:
    employee = db.scalar(
        select(Employee).where(Employee.id == employee_id, Employee.tenant_id == context.tenant_id)
    )
    if not employee:
        raise HTTPException(status_code=404, detail="Colaborador não encontrado nesta empresa")
    return employee


def access_scope(db: Session, context: AuthContext) -> set[int] | None:
    if Permission.portal_manage in context.permissions:
        return None
    employee = own_employee(db, context)
    allowed = {employee.id}
    if Permission.portal_team in context.permissions:
        allowed.update(
            db.scalars(
                select(Employee.id).where(
                    Employee.tenant_id == context.tenant_id,
                    Employee.manager_id == employee.id,
                )
            ).all()
        )
    if not ({Permission.portal_own, Permission.portal_team} & context.permissions):
        raise HTTPException(status_code=403, detail="Permissão insuficiente para o portal")
    return allowed


def resolve_target(
    db: Session, context: AuthContext, requested_employee_id: int | None
) -> Employee:
    scope = access_scope(db, context)
    if requested_employee_id is None:
        return own_employee(db, context)
    employee = tenant_employee(db, context, requested_employee_id)
    if scope is not None and employee.id not in scope:
        raise HTTPException(status_code=403, detail="Colaborador fora do escopo permitido")
    return employee


def scoped_item(db: Session, context: AuthContext, model, item_id: int):
    item = db.scalar(select(model).where(model.id == item_id, model.tenant_id == context.tenant_id))
    if not item:
        raise HTTPException(status_code=404, detail="Registro não encontrado")
    scope = access_scope(db, context)
    if scope is not None and item.employee_id not in scope:
        raise HTTPException(status_code=404, detail="Registro não encontrado")
    return item


@router.get("/summary", response_model=PortalSummary)
def summary(
    context: Annotated[AuthContext, Depends(current_context)],
    db: Annotated[Session, Depends(get_db)],
):
    scope = access_scope(db, context)
    employee = own_employee(db, context, required=False)
    request_statement = select(func.count(EmployeeRequest.id)).where(
        EmployeeRequest.tenant_id == context.tenant_id,
        EmployeeRequest.status.in_([EmployeeRequestStatus.submitted, EmployeeRequestStatus.in_review]),
    )
    leave_statement = select(func.count(LeaveRequest.id)).where(
        LeaveRequest.tenant_id == context.tenant_id,
        LeaveRequest.status == LeaveRequestStatus.submitted,
    )
    file_statement = select(func.count(EmployeeFile.id)).where(EmployeeFile.tenant_id == context.tenant_id)
    if scope is not None:
        request_statement = request_statement.where(EmployeeRequest.employee_id.in_(scope))
        leave_statement = leave_statement.where(LeaveRequest.employee_id.in_(scope))
        file_statement = file_statement.where(
            EmployeeFile.employee_id.in_(scope),
            EmployeeFile.visibility == EmployeeFileVisibility.employee,
        )
    return PortalSummary(
        employee_id=employee.id if employee else None,
        employee_name=employee.full_name if employee else None,
        open_requests=db.scalar(request_statement) or 0,
        pending_leave_requests=db.scalar(leave_statement) or 0,
        available_files=db.scalar(file_statement) or 0,
    )


@router.get("/requests", response_model=list[EmployeeRequestRead])
def list_requests(
    context: Annotated[AuthContext, Depends(current_context)],
    db: Annotated[Session, Depends(get_db)],
    employee_id: int | None = None,
):
    scope = access_scope(db, context)
    statement = select(EmployeeRequest).where(EmployeeRequest.tenant_id == context.tenant_id)
    if employee_id is not None:
        resolve_target(db, context, employee_id)
        statement = statement.where(EmployeeRequest.employee_id == employee_id)
    elif scope is not None:
        statement = statement.where(EmployeeRequest.employee_id.in_(scope))
    return db.scalars(statement.order_by(EmployeeRequest.updated_at.desc())).all()


@router.post("/requests", response_model=EmployeeRequestRead, status_code=201)
def create_request(
    payload: EmployeeRequestCreate,
    request: Request,
    context: Annotated[AuthContext, Depends(current_context)],
    db: Annotated[Session, Depends(get_db)],
):
    employee = resolve_target(db, context, payload.employee_id)
    data = payload.model_dump(exclude={"employee_id"})
    item = EmployeeRequest(tenant_id=context.tenant_id, employee_id=employee.id, **data)
    db.add(item)
    db.flush()
    audit(
        db,
        context=context,
        request=request,
        action="submit",
        entity="employee_request",
        entity_id=str(item.id),
        details=f"{item.category}: {item.subject}",
        after=model_snapshot(item),
    )
    db.commit()
    db.refresh(item)
    return item


@router.patch("/requests/{request_id}", response_model=EmployeeRequestRead)
def transition_request(
    request_id: int,
    payload: EmployeeRequestTransition,
    request: Request,
    context: Annotated[AuthContext, Depends(current_context)],
    db: Annotated[Session, Depends(get_db)],
):
    item = scoped_item(db, context, EmployeeRequest, request_id)
    own = own_employee(db, context, required=False)
    can_manage = Permission.portal_manage in context.permissions or (
        Permission.portal_team in context.permissions and own and item.employee_id != own.id
    )
    if not can_manage:
        if item.employee_id != (own.id if own else None) or payload.status != EmployeeRequestStatus.cancelled:
            raise HTTPException(status_code=403, detail="Somente o responsável pode decidir a solicitação")
        if payload.assigned_to_id is not None:
            raise HTTPException(status_code=403, detail="Colaborador não pode atribuir responsável")
        if item.status not in {EmployeeRequestStatus.submitted, EmployeeRequestStatus.in_review}:
            raise HTTPException(status_code=409, detail="Esta solicitação não pode mais ser cancelada")
    elif payload.status not in REQUEST_TRANSITIONS[item.status]:
        raise HTTPException(
            status_code=409,
            detail=f"Transição inválida: {item.status.value} → {payload.status.value}",
        )
    if payload.assigned_to_id is not None and not db.scalar(
        select(Membership.id).where(
            Membership.tenant_id == context.tenant_id,
            Membership.user_id == payload.assigned_to_id,
            Membership.active.is_(True),
        )
    ):
        raise HTTPException(status_code=404, detail="Responsável não pertence à empresa")
    before = model_snapshot(item)
    item.status = payload.status
    item.resolution = payload.resolution
    item.assigned_to_id = payload.assigned_to_id
    if payload.status in {
        EmployeeRequestStatus.approved,
        EmployeeRequestStatus.rejected,
        EmployeeRequestStatus.resolved,
        EmployeeRequestStatus.cancelled,
    }:
        item.decided_by_id = context.user.id
        item.resolved_at = now()
    audit(
        db,
        context=context,
        request=request,
        action="transition",
        entity="employee_request",
        entity_id=str(item.id),
        details=f"{before['status']} → {item.status.value}",
        before=before,
        after=model_snapshot(item),
    )
    db.commit()
    db.refresh(item)
    return item


@router.get("/leave-requests", response_model=list[LeaveRequestRead])
def list_leave_requests(
    context: Annotated[AuthContext, Depends(current_context)],
    db: Annotated[Session, Depends(get_db)],
    employee_id: int | None = None,
):
    scope = access_scope(db, context)
    statement = select(LeaveRequest).where(LeaveRequest.tenant_id == context.tenant_id)
    if employee_id is not None:
        resolve_target(db, context, employee_id)
        statement = statement.where(LeaveRequest.employee_id == employee_id)
    elif scope is not None:
        statement = statement.where(LeaveRequest.employee_id.in_(scope))
    return db.scalars(statement.order_by(LeaveRequest.start_date.desc())).all()


@router.post("/leave-requests", response_model=LeaveRequestRead, status_code=201)
def create_leave_request(
    payload: LeaveRequestCreate,
    request: Request,
    context: Annotated[AuthContext, Depends(current_context)],
    db: Annotated[Session, Depends(get_db)],
):
    employee = resolve_target(db, context, payload.employee_id)
    overlap = db.scalar(
        select(LeaveRequest.id).where(
            LeaveRequest.tenant_id == context.tenant_id,
            LeaveRequest.employee_id == employee.id,
            LeaveRequest.status.in_([LeaveRequestStatus.submitted, LeaveRequestStatus.approved]),
            LeaveRequest.start_date <= payload.end_date,
            LeaveRequest.end_date >= payload.start_date,
        )
    )
    if overlap:
        raise HTTPException(status_code=409, detail="Já existe solicitação ativa neste período")
    data = payload.model_dump(exclude={"employee_id"})
    item = LeaveRequest(
        tenant_id=context.tenant_id,
        employee_id=employee.id,
        total_days=(payload.end_date - payload.start_date).days + 1,
        **data,
    )
    db.add(item)
    db.flush()
    audit(
        db,
        context=context,
        request=request,
        action="submit",
        entity="leave_request",
        entity_id=str(item.id),
        details=f"{item.leave_type}: {item.start_date} a {item.end_date}",
        after=model_snapshot(item),
    )
    db.commit()
    db.refresh(item)
    return item


@router.patch("/leave-requests/{leave_id}", response_model=LeaveRequestRead)
def transition_leave_request(
    leave_id: int,
    payload: LeaveRequestTransition,
    request: Request,
    context: Annotated[AuthContext, Depends(current_context)],
    db: Annotated[Session, Depends(get_db)],
):
    item = scoped_item(db, context, LeaveRequest, leave_id)
    own = own_employee(db, context, required=False)
    can_manage = Permission.portal_manage in context.permissions or (
        Permission.portal_team in context.permissions and own and item.employee_id != own.id
    )
    if not can_manage:
        if (
            item.employee_id != (own.id if own else None)
            or item.status != LeaveRequestStatus.submitted
            or payload.status != LeaveRequestStatus.cancelled
        ):
            raise HTTPException(status_code=403, detail="Somente o responsável pode decidir a ausência")
    elif payload.status not in LEAVE_TRANSITIONS[item.status]:
        raise HTTPException(
            status_code=409,
            detail=f"Transição inválida: {item.status.value} → {payload.status.value}",
        )
    before = model_snapshot(item)
    item.status = payload.status
    item.decision_notes = payload.decision_notes
    item.decided_by_id = context.user.id
    item.decided_at = now()
    audit(
        db,
        context=context,
        request=request,
        action="transition",
        entity="leave_request",
        entity_id=str(item.id),
        details=f"{before['status']} → {item.status.value}",
        before=before,
        after=model_snapshot(item),
    )
    db.commit()
    db.refresh(item)
    return item


@router.get("/files", response_model=list[EmployeeFileRead])
def list_files(
    context: Annotated[AuthContext, Depends(current_context)],
    db: Annotated[Session, Depends(get_db)],
    employee_id: int | None = None,
):
    if Permission.employee_files_manage in context.permissions:
        statement = select(EmployeeFile).where(EmployeeFile.tenant_id == context.tenant_id)
        if employee_id is not None:
            tenant_employee(db, context, employee_id)
            statement = statement.where(EmployeeFile.employee_id == employee_id)
    else:
        employee = own_employee(db, context)
        if Permission.portal_own not in context.permissions:
            raise HTTPException(status_code=403, detail="Permissão insuficiente para documentos")
        if employee_id is not None and employee_id != employee.id:
            raise HTTPException(status_code=403, detail="Acesso limitado aos próprios documentos")
        statement = select(EmployeeFile).where(
            EmployeeFile.tenant_id == context.tenant_id,
            EmployeeFile.employee_id == employee.id,
            EmployeeFile.visibility == EmployeeFileVisibility.employee,
        )
    return db.scalars(statement.order_by(EmployeeFile.created_at.desc())).all()


@router.post("/files", response_model=EmployeeFileRead, status_code=201)
def create_file(
    payload: EmployeeFileCreate,
    request: Request,
    context: Annotated[
        AuthContext, Depends(require_permissions(Permission.employee_files_manage))
    ],
    db: Annotated[Session, Depends(get_db)],
):
    tenant_employee(db, context, payload.employee_id)
    item = EmployeeFile(
        tenant_id=context.tenant_id,
        uploaded_by_id=context.user.id,
        **payload.model_dump(),
    )
    db.add(item)
    try:
        db.flush()
    except IntegrityError as error:
        db.rollback()
        raise HTTPException(status_code=409, detail="Chave de armazenamento já registrada") from error
    audit(
        db,
        context=context,
        request=request,
        action="publish_metadata",
        entity="employee_file",
        entity_id=str(item.id),
        details=f"{item.category}: {item.filename}",
        after=model_snapshot(item),
    )
    db.commit()
    db.refresh(item)
    return item
