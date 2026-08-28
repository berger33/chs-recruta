from __future__ import annotations

import calendar
import hashlib
import json
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Employee, TimeEntry
from ..permissions import Permission
from ..security import AuthContext, current_context, require_permissions
from ..services import audit, model_snapshot
from ..time_payroll_models import (
    EmployeeSchedule,
    PayrollBatch,
    PayrollBatchStatus,
    PayrollStatement,
    TimeAdjustment,
    TimeAdjustmentAction,
    TimeAdjustmentRequest,
    TimeAdjustmentStatus,
    Timesheet,
    TimesheetStatus,
    WorkSchedule,
)
from ..time_payroll_schemas import (
    EffectiveTimeEntry,
    EmployeeScheduleCreate,
    EmployeeScheduleRead,
    PayrollBatchCreate,
    PayrollBatchRead,
    PayrollBatchTransition,
    PayrollStatementRead,
    TimeAdjustmentDecision,
    TimeAdjustmentRequestCreate,
    TimeAdjustmentRequestRead,
    TimesheetCalculate,
    TimesheetRead,
    TimesheetTransition,
    WorkScheduleCreate,
    WorkScheduleRead,
)

router = APIRouter(prefix="/api", tags=["time-payroll-advanced"])

PAYROLL_TRANSITIONS = {
    PayrollBatchStatus.uploaded: {PayrollBatchStatus.validated, PayrollBatchStatus.cancelled},
    PayrollBatchStatus.validated: {PayrollBatchStatus.published, PayrollBatchStatus.cancelled},
    PayrollBatchStatus.published: set(),
    PayrollBatchStatus.cancelled: set(),
}


def now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def naive_utc(value: datetime) -> datetime:
    if value.tzinfo is not None:
        return value.astimezone(UTC).replace(tzinfo=None)
    return value


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


def time_scope(db: Session, context: AuthContext) -> set[int] | None:
    if Permission.time_manage in context.permissions:
        return None
    employee = own_employee(db, context)
    allowed = {employee.id}
    if Permission.time_team in context.permissions:
        allowed.update(
            db.scalars(
                select(Employee.id).where(
                    Employee.tenant_id == context.tenant_id,
                    Employee.manager_id == employee.id,
                )
            ).all()
        )
    elif Permission.time_own not in context.permissions:
        raise HTTPException(status_code=403, detail="Permissão insuficiente para jornada")
    return allowed


def require_scoped_employee(
    db: Session, context: AuthContext, employee_id: int
) -> Employee:
    employee = tenant_employee(db, context, employee_id)
    scope = time_scope(db, context)
    if scope is not None and employee.id not in scope:
        raise HTTPException(status_code=404, detail="Colaborador não encontrado")
    return employee


def competence_bounds(competence: str) -> tuple[datetime, datetime]:
    year, month = map(int, competence.split("-"))
    last_day = calendar.monthrange(year, month)[1]
    return datetime.combine(date(year, month, 1), time.min), datetime.combine(
        date(year, month, last_day), time.max
    )


def adjustment_hash(item: TimeAdjustmentRequest, tenant_id: int) -> str:
    raw = ":".join(
        [
            str(tenant_id),
            str(item.employee_id),
            item.action.value,
            str(item.original_entry_id or ""),
            item.requested_kind.value if item.requested_kind else "",
            item.requested_at.isoformat() if item.requested_at else "",
            str(item.id),
        ]
    )
    return hashlib.sha256(raw.encode()).hexdigest()


def effective_entries(
    db: Session,
    context: AuthContext,
    employee_id: int,
    start_at: datetime,
    end_at: datetime,
) -> list[EffectiveTimeEntry]:
    require_scoped_employee(db, context, employee_id)
    raw_entries = db.scalars(
        select(TimeEntry)
        .where(
            TimeEntry.tenant_id == context.tenant_id,
            TimeEntry.employee_id == employee_id,
            TimeEntry.recorded_at >= start_at,
            TimeEntry.recorded_at <= end_at,
        )
        .order_by(TimeEntry.recorded_at)
    ).all()
    raw_ids = [entry.id for entry in raw_entries]
    criteria = [
        TimeAdjustment.tenant_id == context.tenant_id,
        TimeAdjustment.employee_id == employee_id,
    ]
    if raw_ids:
        adjustment_filter = or_(
            TimeAdjustment.original_entry_id.in_(raw_ids),
            TimeAdjustment.effective_at.between(start_at, end_at),
        )
    else:
        adjustment_filter = TimeAdjustment.effective_at.between(start_at, end_at)
    adjustments = db.scalars(select(TimeAdjustment).where(*criteria, adjustment_filter)).all()
    altered = {
        item.original_entry_id
        for item in adjustments
        if item.original_entry_id is not None
        and item.action in {TimeAdjustmentAction.replace, TimeAdjustmentAction.void}
    }
    result = [
        EffectiveTimeEntry(
            source_type="raw",
            source_id=entry.id,
            original_entry_id=entry.id,
            kind=entry.kind,
            recorded_at=entry.recorded_at,
            integrity_hash=entry.integrity_hash,
        )
        for entry in raw_entries
        if entry.id not in altered
    ]
    result.extend(
        EffectiveTimeEntry(
            source_type="adjustment",
            source_id=item.id,
            original_entry_id=item.original_entry_id,
            kind=item.effective_kind,
            recorded_at=item.effective_at,
            integrity_hash=item.integrity_hash,
        )
        for item in adjustments
        if item.action in {TimeAdjustmentAction.add, TimeAdjustmentAction.replace}
        and item.effective_kind is not None
        and item.effective_at is not None
        and start_at <= item.effective_at <= end_at
    )
    return sorted(result, key=lambda entry: (entry.recorded_at, entry.source_type, entry.source_id))


@router.get("/time-management/schedules", response_model=list[WorkScheduleRead])
def list_schedules(
    context: Annotated[AuthContext, Depends(require_permissions(Permission.time_close))],
    db: Annotated[Session, Depends(get_db)],
):
    return db.scalars(
        select(WorkSchedule)
        .where(WorkSchedule.tenant_id == context.tenant_id)
        .order_by(WorkSchedule.active.desc(), WorkSchedule.name)
    ).all()


@router.post("/time-management/schedules", response_model=WorkScheduleRead, status_code=201)
def create_schedule(
    payload: WorkScheduleCreate,
    request: Request,
    context: Annotated[AuthContext, Depends(require_permissions(Permission.time_close))],
    db: Annotated[Session, Depends(get_db)],
):
    item = WorkSchedule(tenant_id=context.tenant_id, **payload.model_dump())
    db.add(item)
    try:
        db.flush()
    except IntegrityError as error:
        db.rollback()
        raise HTTPException(status_code=409, detail="Escala já cadastrada") from error
    audit(
        db,
        context=context,
        request=request,
        action="create",
        entity="work_schedule",
        entity_id=str(item.id),
        details=item.name,
        after=model_snapshot(item),
    )
    db.commit()
    db.refresh(item)
    return item


@router.get("/time-management/employee-schedules", response_model=list[EmployeeScheduleRead])
def list_employee_schedules(
    context: Annotated[AuthContext, Depends(current_context)],
    db: Annotated[Session, Depends(get_db)],
    employee_id: int | None = None,
):
    scope = time_scope(db, context)
    statement = select(EmployeeSchedule).where(EmployeeSchedule.tenant_id == context.tenant_id)
    if employee_id is not None:
        require_scoped_employee(db, context, employee_id)
        statement = statement.where(EmployeeSchedule.employee_id == employee_id)
    elif scope is not None:
        statement = statement.where(EmployeeSchedule.employee_id.in_(scope))
    return db.scalars(statement.order_by(EmployeeSchedule.effective_from.desc())).all()


@router.post(
    "/time-management/employee-schedules",
    response_model=EmployeeScheduleRead,
    status_code=201,
)
def assign_schedule(
    payload: EmployeeScheduleCreate,
    request: Request,
    context: Annotated[AuthContext, Depends(require_permissions(Permission.time_close))],
    db: Annotated[Session, Depends(get_db)],
):
    tenant_employee(db, context, payload.employee_id)
    if not db.scalar(
        select(WorkSchedule.id).where(
            WorkSchedule.id == payload.schedule_id,
            WorkSchedule.tenant_id == context.tenant_id,
            WorkSchedule.active.is_(True),
        )
    ):
        raise HTTPException(status_code=404, detail="Escala ativa não encontrada")
    overlap = db.scalar(
        select(EmployeeSchedule.id).where(
            EmployeeSchedule.tenant_id == context.tenant_id,
            EmployeeSchedule.employee_id == payload.employee_id,
            EmployeeSchedule.effective_from <= (payload.effective_to or date.max),
            or_(
                EmployeeSchedule.effective_to.is_(None),
                EmployeeSchedule.effective_to >= payload.effective_from,
            ),
        )
    )
    if overlap:
        raise HTTPException(status_code=409, detail="Já existe escala vigente neste período")
    item = EmployeeSchedule(
        tenant_id=context.tenant_id,
        created_by_id=context.user.id,
        **payload.model_dump(),
    )
    db.add(item)
    db.flush()
    audit(
        db,
        context=context,
        request=request,
        action="assign",
        entity="employee_schedule",
        entity_id=str(item.id),
        details=f"employee={item.employee_id}; schedule={item.schedule_id}",
        after=model_snapshot(item),
    )
    db.commit()
    db.refresh(item)
    return item


@router.get("/time-management/effective-entries", response_model=list[EffectiveTimeEntry])
def list_effective_entries(
    employee_id: int,
    start_at: datetime,
    end_at: datetime,
    context: Annotated[AuthContext, Depends(current_context)],
    db: Annotated[Session, Depends(get_db)],
):
    start_at = naive_utc(start_at)
    end_at = naive_utc(end_at)
    if end_at < start_at:
        raise HTTPException(status_code=422, detail="Período inválido")
    if (end_at - start_at).days > 366:
        raise HTTPException(status_code=422, detail="Consulta limitada a 367 dias")
    return effective_entries(db, context, employee_id, start_at, end_at)


@router.get(
    "/time-management/adjustment-requests", response_model=list[TimeAdjustmentRequestRead]
)
def list_adjustment_requests(
    context: Annotated[AuthContext, Depends(current_context)],
    db: Annotated[Session, Depends(get_db)],
    employee_id: int | None = None,
):
    scope = time_scope(db, context)
    statement = select(TimeAdjustmentRequest).where(
        TimeAdjustmentRequest.tenant_id == context.tenant_id
    )
    if employee_id is not None:
        require_scoped_employee(db, context, employee_id)
        statement = statement.where(TimeAdjustmentRequest.employee_id == employee_id)
    elif scope is not None:
        statement = statement.where(TimeAdjustmentRequest.employee_id.in_(scope))
    return db.scalars(statement.order_by(TimeAdjustmentRequest.updated_at.desc())).all()


@router.post(
    "/time-management/adjustment-requests",
    response_model=TimeAdjustmentRequestRead,
    status_code=201,
)
def create_adjustment_request(
    payload: TimeAdjustmentRequestCreate,
    request: Request,
    context: Annotated[AuthContext, Depends(current_context)],
    db: Annotated[Session, Depends(get_db)],
):
    employee = own_employee(db, context)
    if Permission.time_own not in context.permissions:
        raise HTTPException(status_code=403, detail="Permissão insuficiente")
    if payload.original_entry_id is not None and not db.scalar(
        select(TimeEntry.id).where(
            TimeEntry.id == payload.original_entry_id,
            TimeEntry.tenant_id == context.tenant_id,
            TimeEntry.employee_id == employee.id,
        )
    ):
        raise HTTPException(status_code=404, detail="Marcação original não encontrada")
    if payload.requested_at is not None and not (
        now() - timedelta(days=366 * 5) <= payload.requested_at <= now() + timedelta(minutes=5)
    ):
        raise HTTPException(status_code=422, detail="Horário solicitado fora do período permitido")
    item = TimeAdjustmentRequest(
        tenant_id=context.tenant_id,
        employee_id=employee.id,
        **payload.model_dump(),
    )
    db.add(item)
    db.flush()
    audit(
        db,
        context=context,
        request=request,
        action="request",
        entity="time_adjustment_request",
        entity_id=str(item.id),
        details=f"{item.action.value}: employee={employee.id}",
        after=model_snapshot(item),
    )
    db.commit()
    db.refresh(item)
    return item


@router.post(
    "/time-management/adjustment-requests/{adjustment_request_id}/cancel",
    response_model=TimeAdjustmentRequestRead,
)
def cancel_adjustment_request(
    adjustment_request_id: int,
    request: Request,
    context: Annotated[AuthContext, Depends(current_context)],
    db: Annotated[Session, Depends(get_db)],
):
    employee = own_employee(db, context)
    item = db.scalar(
        select(TimeAdjustmentRequest).where(
            TimeAdjustmentRequest.id == adjustment_request_id,
            TimeAdjustmentRequest.tenant_id == context.tenant_id,
            TimeAdjustmentRequest.employee_id == employee.id,
        )
    )
    if not item:
        raise HTTPException(status_code=404, detail="Solicitação não encontrada")
    if item.status != TimeAdjustmentStatus.requested:
        raise HTTPException(status_code=409, detail="Somente solicitação pendente pode ser cancelada")
    before = model_snapshot(item)
    item.status = TimeAdjustmentStatus.cancelled
    audit(
        db,
        context=context,
        request=request,
        action="cancel",
        entity="time_adjustment_request",
        entity_id=str(item.id),
        details="Cancelada pelo colaborador solicitante",
        before=before,
        after=model_snapshot(item),
    )
    db.commit()
    db.refresh(item)
    return item


@router.post(
    "/time-management/adjustment-requests/{adjustment_request_id}/decision",
    response_model=TimeAdjustmentRequestRead,
)
def decide_adjustment_request(
    adjustment_request_id: int,
    payload: TimeAdjustmentDecision,
    request: Request,
    context: Annotated[
        AuthContext, Depends(require_permissions(Permission.time_adjust_approve))
    ],
    db: Annotated[Session, Depends(get_db)],
):
    item = db.scalar(
        select(TimeAdjustmentRequest).where(
            TimeAdjustmentRequest.id == adjustment_request_id,
            TimeAdjustmentRequest.tenant_id == context.tenant_id,
        )
    )
    if not item:
        raise HTTPException(status_code=404, detail="Solicitação não encontrada")
    require_scoped_employee(db, context, item.employee_id)
    reviewer = own_employee(db, context, required=False)
    if Permission.time_manage not in context.permissions and reviewer and reviewer.id == item.employee_id:
        raise HTTPException(status_code=403, detail="Gestor não pode aprovar o próprio ajuste")
    if item.status != TimeAdjustmentStatus.requested:
        raise HTTPException(status_code=409, detail="Solicitação já decidida")
    if payload.approved and item.original_entry_id is not None and db.scalar(
        select(TimeAdjustment.id).where(
            TimeAdjustment.tenant_id == context.tenant_id,
            TimeAdjustment.original_entry_id == item.original_entry_id,
            TimeAdjustment.action.in_([TimeAdjustmentAction.replace, TimeAdjustmentAction.void]),
        )
    ):
        raise HTTPException(status_code=409, detail="Marcação original já possui ajuste aprovado")
    before = model_snapshot(item)
    item.status = (
        TimeAdjustmentStatus.approved if payload.approved else TimeAdjustmentStatus.rejected
    )
    item.review_notes = payload.review_notes
    item.reviewed_by_id = context.user.id
    item.reviewed_at = now()
    if payload.approved:
        approved = TimeAdjustment(
            tenant_id=context.tenant_id,
            request_id=item.id,
            employee_id=item.employee_id,
            action=item.action,
            original_entry_id=item.original_entry_id,
            effective_kind=item.requested_kind,
            effective_at=item.requested_at,
            approved_by_id=context.user.id,
            integrity_hash=adjustment_hash(item, context.tenant_id),
        )
        db.add(approved)
        db.flush()
    audit(
        db,
        context=context,
        request=request,
        action="approve" if payload.approved else "reject",
        entity="time_adjustment_request",
        entity_id=str(item.id),
        details=payload.review_notes,
        before=before,
        after=model_snapshot(item),
    )
    db.commit()
    db.refresh(item)
    return item


def timesheet_summary(entries: list[EffectiveTimeEntry]) -> dict:
    total_minutes = 0
    anomalies: list[str] = []
    active_start: datetime | None = None
    days: dict[str, int] = {}
    for entry in entries:
        if entry.kind.value in {"entrada", "fim_intervalo"}:
            if active_start is not None:
                anomalies.append(f"dupla_abertura:{entry.recorded_at.isoformat()}")
            else:
                active_start = entry.recorded_at
        else:
            if active_start is None:
                anomalies.append(f"fechamento_sem_abertura:{entry.recorded_at.isoformat()}")
            else:
                minutes = max(0, int((entry.recorded_at - active_start).total_seconds() // 60))
                total_minutes += minutes
                day = active_start.date().isoformat()
                days[day] = days.get(day, 0) + minutes
                active_start = None
    if active_start is not None:
        anomalies.append(f"jornada_aberta:{active_start.isoformat()}")
    return {
        "worked_minutes": total_minutes,
        "entry_count": len(entries),
        "anomaly_count": len(anomalies),
        "anomalies": anomalies,
        "days": days,
    }


@router.post("/time-management/timesheets/calculate", response_model=TimesheetRead)
def calculate_timesheet(
    payload: TimesheetCalculate,
    request: Request,
    context: Annotated[AuthContext, Depends(require_permissions(Permission.time_close))],
    db: Annotated[Session, Depends(get_db)],
):
    tenant_employee(db, context, payload.employee_id)
    start_at, end_at = competence_bounds(payload.competence)
    entries = effective_entries(db, context, payload.employee_id, start_at, end_at)
    summary = timesheet_summary(entries)
    latest = db.scalar(
        select(Timesheet)
        .where(
            Timesheet.tenant_id == context.tenant_id,
            Timesheet.employee_id == payload.employee_id,
            Timesheet.competence == payload.competence,
        )
        .order_by(Timesheet.version.desc())
    )
    if latest and latest.status in {TimesheetStatus.submitted, TimesheetStatus.approved}:
        raise HTTPException(status_code=409, detail="Espelho em aprovação não pode ser recalculado")
    if latest and latest.status == TimesheetStatus.open:
        item = latest
        before = model_snapshot(item)
        item.summary = summary
        item.calculated_at = now()
        action = "recalculate"
    else:
        item = Timesheet(
            tenant_id=context.tenant_id,
            employee_id=payload.employee_id,
            competence=payload.competence,
            version=(latest.version + 1) if latest else 1,
            supersedes_id=latest.id if latest else None,
            summary=summary,
            calculated_at=now(),
        )
        db.add(item)
        db.flush()
        before = None
        action = "calculate"
    audit(
        db,
        context=context,
        request=request,
        action=action,
        entity="timesheet",
        entity_id=str(item.id),
        details=f"{item.competence}: v{item.version}",
        before=before,
        after=model_snapshot(item),
    )
    db.commit()
    db.refresh(item)
    return item


@router.get("/time-management/timesheets", response_model=list[TimesheetRead])
def list_timesheets(
    context: Annotated[AuthContext, Depends(current_context)],
    db: Annotated[Session, Depends(get_db)],
    employee_id: int | None = None,
):
    scope = time_scope(db, context)
    statement = select(Timesheet).where(Timesheet.tenant_id == context.tenant_id)
    if employee_id is not None:
        require_scoped_employee(db, context, employee_id)
        statement = statement.where(Timesheet.employee_id == employee_id)
    elif scope is not None:
        statement = statement.where(Timesheet.employee_id.in_(scope))
    return db.scalars(
        statement.order_by(Timesheet.competence.desc(), Timesheet.version.desc())
    ).all()


@router.patch("/time-management/timesheets/{timesheet_id}", response_model=TimesheetRead)
def transition_timesheet(
    timesheet_id: int,
    payload: TimesheetTransition,
    request: Request,
    context: Annotated[AuthContext, Depends(current_context)],
    db: Annotated[Session, Depends(get_db)],
):
    item = db.scalar(
        select(Timesheet).where(
            Timesheet.id == timesheet_id,
            Timesheet.tenant_id == context.tenant_id,
        )
    )
    if not item:
        raise HTTPException(status_code=404, detail="Espelho não encontrado")
    require_scoped_employee(db, context, item.employee_id)
    employee = own_employee(db, context, required=False)
    before = model_snapshot(item)
    if item.status == TimesheetStatus.open and payload.status == TimesheetStatus.submitted:
        if Permission.time_manage not in context.permissions and (
            not employee or employee.id != item.employee_id
        ):
            raise HTTPException(status_code=403, detail="Somente colaborador ou RH pode enviar")
        item.submitted_by_id = context.user.id
        item.submitted_at = now()
    elif item.status == TimesheetStatus.submitted and payload.status == TimesheetStatus.approved:
        if Permission.time_adjust_approve not in context.permissions:
            raise HTTPException(status_code=403, detail="Permissão de aprovação necessária")
        if Permission.time_manage not in context.permissions and employee and employee.id == item.employee_id:
            raise HTTPException(status_code=403, detail="Gestor não pode aprovar o próprio espelho")
        item.approved_by_id = context.user.id
        item.approved_at = now()
    elif item.status == TimesheetStatus.approved and payload.status == TimesheetStatus.locked:
        if Permission.time_close not in context.permissions:
            raise HTTPException(status_code=403, detail="Somente RH autorizado pode fechar")
        item.locked_by_id = context.user.id
        item.locked_at = now()
        canonical = json.dumps(item.summary, sort_keys=True, separators=(",", ":"))
        item.integrity_hash = hashlib.sha256(
            f"{context.tenant_id}:{item.employee_id}:{item.competence}:{item.version}:{canonical}".encode()
        ).hexdigest()
    else:
        raise HTTPException(
            status_code=409,
            detail=f"Transição inválida: {item.status.value} → {payload.status.value}",
        )
    before_status = item.status.value
    item.status = payload.status
    audit(
        db,
        context=context,
        request=request,
        action="transition",
        entity="timesheet",
        entity_id=str(item.id),
        details=f"{before_status} → {item.status.value}",
        before=before,
        after=model_snapshot(item),
    )
    db.commit()
    db.refresh(item)
    return item


@router.get("/payroll/batches", response_model=list[PayrollBatchRead])
def list_payroll_batches(
    context: Annotated[AuthContext, Depends(require_permissions(Permission.payroll_manage))],
    db: Annotated[Session, Depends(get_db)],
):
    return db.scalars(
        select(PayrollBatch)
        .where(PayrollBatch.tenant_id == context.tenant_id)
        .order_by(PayrollBatch.created_at.desc())
    ).all()


@router.post("/payroll/batches", response_model=PayrollBatchRead, status_code=201)
def create_payroll_batch(
    payload: PayrollBatchCreate,
    request: Request,
    context: Annotated[AuthContext, Depends(require_permissions(Permission.payroll_manage))],
    db: Annotated[Session, Depends(get_db)],
):
    employees = db.scalars(
        select(Employee).where(
            Employee.tenant_id == context.tenant_id,
            Employee.employee_number.in_([row.employee_number for row in payload.rows]),
        )
    ).all()
    by_number = {employee.employee_number: employee for employee in employees}
    missing = sorted(
        row.employee_number for row in payload.rows if row.employee_number not in by_number
    )
    if missing:
        raise HTTPException(status_code=422, detail={"unknown_employee_numbers": missing})
    batch = PayrollBatch(
        tenant_id=context.tenant_id,
        competence=payload.competence,
        source=payload.source,
        idempotency_key=payload.idempotency_key,
        row_count=len(payload.rows),
        total_net=sum((row.net_amount for row in payload.rows), Decimal("0.00")),
        created_by_id=context.user.id,
    )
    db.add(batch)
    try:
        db.flush()
        for row in payload.rows:
            employee = by_number[row.employee_number]
            db.add(
                PayrollStatement(
                    tenant_id=context.tenant_id,
                    batch_id=batch.id,
                    employee_id=employee.id,
                    competence=payload.competence,
                    **row.model_dump(exclude={"employee_number"}),
                )
            )
        db.flush()
    except IntegrityError as error:
        db.rollback()
        raise HTTPException(status_code=409, detail="Lote já importado") from error
    audit(
        db,
        context=context,
        request=request,
        action="import",
        entity="payroll_batch",
        entity_id=str(batch.id),
        details=f"{batch.competence}: {batch.row_count} registros",
        after=model_snapshot(batch),
    )
    db.commit()
    db.refresh(batch)
    return batch


@router.patch("/payroll/batches/{batch_id}", response_model=PayrollBatchRead)
def transition_payroll_batch(
    batch_id: int,
    payload: PayrollBatchTransition,
    request: Request,
    context: Annotated[AuthContext, Depends(require_permissions(Permission.payroll_manage))],
    db: Annotated[Session, Depends(get_db)],
):
    batch = db.scalar(
        select(PayrollBatch).where(
            PayrollBatch.id == batch_id,
            PayrollBatch.tenant_id == context.tenant_id,
        )
    )
    if not batch:
        raise HTTPException(status_code=404, detail="Lote não encontrado")
    if payload.status not in PAYROLL_TRANSITIONS[batch.status]:
        raise HTTPException(
            status_code=409,
            detail=f"Transição inválida: {batch.status.value} → {payload.status.value}",
        )
    before = model_snapshot(batch)
    batch.status = payload.status
    if payload.status == PayrollBatchStatus.published:
        db.query(PayrollStatement).filter(
            PayrollStatement.tenant_id == context.tenant_id,
            PayrollStatement.batch_id == batch.id,
        ).update({PayrollStatement.published_at: now()}, synchronize_session=False)
    audit(
        db,
        context=context,
        request=request,
        action="transition",
        entity="payroll_batch",
        entity_id=str(batch.id),
        details=f"{before['status']} → {batch.status.value}",
        before=before,
        after=model_snapshot(batch),
    )
    db.commit()
    db.refresh(batch)
    return batch


@router.get("/payroll/statements", response_model=list[PayrollStatementRead])
def list_payroll_statements(
    context: Annotated[AuthContext, Depends(current_context)],
    db: Annotated[Session, Depends(get_db)],
    employee_id: int | None = None,
):
    statement = (
        select(PayrollStatement)
        .join(PayrollBatch, PayrollBatch.id == PayrollStatement.batch_id)
        .where(
            PayrollStatement.tenant_id == context.tenant_id,
            PayrollBatch.tenant_id == context.tenant_id,
        )
    )
    if Permission.payroll_manage in context.permissions:
        if employee_id is not None:
            tenant_employee(db, context, employee_id)
            statement = statement.where(PayrollStatement.employee_id == employee_id)
    elif Permission.payroll_own in context.permissions:
        employee = own_employee(db, context)
        if employee_id is not None and employee_id != employee.id:
            raise HTTPException(status_code=403, detail="Acesso limitado aos próprios demonstrativos")
        statement = statement.where(PayrollStatement.employee_id == employee.id)
        statement = statement.where(PayrollBatch.status == PayrollBatchStatus.published)
    else:
        raise HTTPException(status_code=403, detail="Permissão insuficiente")
    return db.scalars(
        statement.order_by(PayrollStatement.competence.desc(), PayrollStatement.created_at.desc())
    ).all()
