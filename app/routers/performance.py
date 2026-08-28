from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..advanced_models import PerformanceCycle, PerformanceGoal, PerformanceReview, ReviewStatus
from ..advanced_schemas import (
    PerformanceCycleCreate,
    PerformanceCycleRead,
    PerformanceCycleUpdate,
    PerformanceGoalCreate,
    PerformanceGoalRead,
    PerformanceReviewCreate,
    PerformanceReviewRead,
)
from ..database import get_db
from ..models import Employee
from ..permissions import Permission
from ..security import AuthContext, require_permissions
from ..services import audit, model_snapshot

router = APIRouter(prefix="/api/performance", tags=["performance"])


def employee_scope(db: Session, context: AuthContext) -> set[int] | None:
    role = context.membership.role.value
    if role in {"tenant_owner", "admin", "hr", "auditor"}:
        return None
    own = db.scalar(
        select(Employee).where(Employee.tenant_id == context.tenant_id, Employee.user_id == context.user.id)
    )
    if not own:
        return set()
    if role == "manager":
        return {own.id, *db.scalars(select(Employee.id).where(
            Employee.tenant_id == context.tenant_id,
            Employee.manager_id == own.id,
        )).all()}
    return {own.id}


def validate_employee(db: Session, tenant_id: int, employee_id: int) -> Employee:
    employee = db.scalar(
        select(Employee).where(Employee.id == employee_id, Employee.tenant_id == tenant_id)
    )
    if not employee:
        raise HTTPException(status_code=404, detail="Colaborador não encontrado")
    return employee


def validate_cycle(db: Session, tenant_id: int, cycle_id: int) -> PerformanceCycle:
    cycle = db.scalar(
        select(PerformanceCycle).where(
            PerformanceCycle.id == cycle_id,
            PerformanceCycle.tenant_id == tenant_id,
        )
    )
    if not cycle:
        raise HTTPException(status_code=404, detail="Ciclo não encontrado")
    return cycle


@router.get("/cycles", response_model=list[PerformanceCycleRead])
def list_cycles(
    context: Annotated[AuthContext, Depends(require_permissions(Permission.performance_read))],
    db: Annotated[Session, Depends(get_db)],
):
    return db.scalars(
        select(PerformanceCycle)
        .where(PerformanceCycle.tenant_id == context.tenant_id)
        .order_by(PerformanceCycle.start_date.desc())
    ).all()


@router.post("/cycles", response_model=PerformanceCycleRead, status_code=201)
def create_cycle(
    payload: PerformanceCycleCreate,
    request: Request,
    context: Annotated[AuthContext, Depends(require_permissions(Permission.performance_manage))],
    db: Annotated[Session, Depends(get_db)],
):
    item = PerformanceCycle(tenant_id=context.tenant_id, **payload.model_dump())
    db.add(item)
    try:
        db.flush()
    except IntegrityError as error:
        db.rollback()
        raise HTTPException(status_code=409, detail="Já existe um ciclo com este nome") from error
    audit(
        db,
        context=context,
        request=request,
        action="create",
        entity="performance_cycle",
        entity_id=str(item.id),
        details=item.name,
        after=model_snapshot(item),
    )
    db.commit()
    db.refresh(item)
    return item


@router.patch("/cycles/{cycle_id}", response_model=PerformanceCycleRead)
def update_cycle(
    cycle_id: int,
    payload: PerformanceCycleUpdate,
    request: Request,
    context: Annotated[AuthContext, Depends(require_permissions(Permission.performance_manage))],
    db: Annotated[Session, Depends(get_db)],
):
    item = validate_cycle(db, context.tenant_id, cycle_id)
    before = model_snapshot(item)
    item.status = payload.status
    audit(
        db,
        context=context,
        request=request,
        action="update_status",
        entity="performance_cycle",
        entity_id=str(item.id),
        before=before,
        after=model_snapshot(item),
    )
    db.commit()
    db.refresh(item)
    return item


@router.get("/goals", response_model=list[PerformanceGoalRead])
def list_goals(
    context: Annotated[AuthContext, Depends(require_permissions(Permission.performance_read))],
    db: Annotated[Session, Depends(get_db)],
    cycle_id: int | None = None,
    employee_id: int | None = None,
):
    allowed = employee_scope(db, context)
    if employee_id is not None:
        validate_employee(db, context.tenant_id, employee_id)
        if allowed is not None and employee_id not in allowed:
            raise HTTPException(status_code=403, detail="Colaborador fora do seu escopo")
    statement = select(PerformanceGoal).where(PerformanceGoal.tenant_id == context.tenant_id)
    if allowed is not None:
        statement = statement.where(PerformanceGoal.employee_id.in_(allowed))
    if cycle_id is not None:
        validate_cycle(db, context.tenant_id, cycle_id)
        statement = statement.where(PerformanceGoal.cycle_id == cycle_id)
    if employee_id is not None:
        statement = statement.where(PerformanceGoal.employee_id == employee_id)
    return db.scalars(statement.order_by(PerformanceGoal.updated_at.desc())).all()


@router.post("/goals", response_model=PerformanceGoalRead, status_code=201)
def create_goal(
    payload: PerformanceGoalCreate,
    request: Request,
    context: Annotated[AuthContext, Depends(require_permissions(Permission.performance_manage))],
    db: Annotated[Session, Depends(get_db)],
):
    validate_cycle(db, context.tenant_id, payload.cycle_id)
    employee = validate_employee(db, context.tenant_id, payload.employee_id)
    item = PerformanceGoal(tenant_id=context.tenant_id, **payload.model_dump())
    db.add(item)
    db.flush()
    audit(
        db,
        context=context,
        request=request,
        action="create",
        entity="performance_goal",
        entity_id=str(item.id),
        details=f"{employee.employee_number}:{item.title}",
        after=model_snapshot(item),
    )
    db.commit()
    db.refresh(item)
    return item


@router.get("/reviews", response_model=list[PerformanceReviewRead])
def list_reviews(
    context: Annotated[AuthContext, Depends(require_permissions(Permission.performance_read))],
    db: Annotated[Session, Depends(get_db)],
    cycle_id: int | None = None,
):
    allowed = employee_scope(db, context)
    statement = select(PerformanceReview).where(PerformanceReview.tenant_id == context.tenant_id)
    if allowed is not None:
        statement = statement.where(
            or_(
                PerformanceReview.reviewee_id.in_(allowed),
                PerformanceReview.reviewer_id == context.user.id,
            )
        )
    if cycle_id is not None:
        validate_cycle(db, context.tenant_id, cycle_id)
        statement = statement.where(PerformanceReview.cycle_id == cycle_id)
    return db.scalars(statement.order_by(PerformanceReview.updated_at.desc())).all()


@router.post("/reviews", response_model=PerformanceReviewRead, status_code=201)
def create_review(
    payload: PerformanceReviewCreate,
    request: Request,
    context: Annotated[AuthContext, Depends(require_permissions(Permission.performance_manage))],
    db: Annotated[Session, Depends(get_db)],
):
    validate_cycle(db, context.tenant_id, payload.cycle_id)
    employee = validate_employee(db, context.tenant_id, payload.reviewee_id)
    item = PerformanceReview(
        tenant_id=context.tenant_id,
        reviewer_id=context.user.id,
        submitted_at=datetime.now(UTC).replace(tzinfo=None) if payload.status == ReviewStatus.submitted else None,
        **payload.model_dump(),
    )
    db.add(item)
    try:
        db.flush()
    except IntegrityError as error:
        db.rollback()
        raise HTTPException(status_code=409, detail="Avaliação já existe para este avaliador") from error
    audit(
        db,
        context=context,
        request=request,
        action="submit" if item.status == ReviewStatus.submitted else "create",
        entity="performance_review",
        entity_id=str(item.id),
        details=employee.employee_number,
        after=model_snapshot(item),
    )
    db.commit()
    db.refresh(item)
    return item
