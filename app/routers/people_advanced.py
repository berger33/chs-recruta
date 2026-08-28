from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..advanced_models import EmployeeMovement, EmploymentContract
from ..advanced_schemas import (
    ContractCreate,
    ContractRead,
    EmployeeMovementCreate,
    EmployeeMovementRead,
)
from ..database import get_db
from ..models import Employee
from ..permissions import Permission
from ..security import AuthContext, require_permissions
from ..services import audit, model_snapshot

router = APIRouter(prefix="/api/core-hr", tags=["core-hr-advanced"])


def scoped_employee(db: Session, tenant_id: int, employee_id: int) -> Employee:
    employee = db.scalar(
        select(Employee).where(Employee.id == employee_id, Employee.tenant_id == tenant_id)
    )
    if not employee:
        raise HTTPException(status_code=404, detail="Colaborador não encontrado")
    return employee


@router.get("/contracts", response_model=list[ContractRead])
def list_contracts(
    context: Annotated[AuthContext, Depends(require_permissions(Permission.contracts_read))],
    db: Annotated[Session, Depends(get_db)],
    employee_id: int | None = None,
):
    statement = select(EmploymentContract).where(EmploymentContract.tenant_id == context.tenant_id)
    if employee_id is not None:
        scoped_employee(db, context.tenant_id, employee_id)
        statement = statement.where(EmploymentContract.employee_id == employee_id)
    return db.scalars(statement.order_by(EmploymentContract.start_date.desc())).all()


@router.post("/contracts", response_model=ContractRead, status_code=201)
def create_contract(
    payload: ContractCreate,
    request: Request,
    context: Annotated[AuthContext, Depends(require_permissions(Permission.contracts_manage))],
    db: Annotated[Session, Depends(get_db)],
):
    employee = scoped_employee(db, context.tenant_id, payload.employee_id)
    item = EmploymentContract(tenant_id=context.tenant_id, **payload.model_dump())
    db.add(item)
    try:
        db.flush()
    except IntegrityError as error:
        db.rollback()
        raise HTTPException(status_code=409, detail="Número de contrato já existe para o colaborador") from error
    audit(
        db,
        context=context,
        request=request,
        action="create",
        entity="employment_contract",
        entity_id=str(item.id),
        details=f"{employee.employee_number}:{item.contract_number}",
        after=model_snapshot(item),
    )
    db.commit()
    db.refresh(item)
    return item


@router.get("/movements", response_model=list[EmployeeMovementRead])
def list_movements(
    context: Annotated[AuthContext, Depends(require_permissions(Permission.contracts_read))],
    db: Annotated[Session, Depends(get_db)],
    employee_id: int | None = None,
):
    statement = select(EmployeeMovement).where(EmployeeMovement.tenant_id == context.tenant_id)
    if employee_id is not None:
        scoped_employee(db, context.tenant_id, employee_id)
        statement = statement.where(EmployeeMovement.employee_id == employee_id)
    return db.scalars(statement.order_by(EmployeeMovement.effective_date.desc())).all()


@router.post("/movements", response_model=EmployeeMovementRead, status_code=201)
def create_movement(
    payload: EmployeeMovementCreate,
    request: Request,
    context: Annotated[AuthContext, Depends(require_permissions(Permission.contracts_manage))],
    db: Annotated[Session, Depends(get_db)],
):
    employee = scoped_employee(db, context.tenant_id, payload.employee_id)
    item = EmployeeMovement(
        tenant_id=context.tenant_id,
        approved_by_id=context.user.id,
        **payload.model_dump(),
    )
    db.add(item)
    db.flush()
    audit(
        db,
        context=context,
        request=request,
        action="create",
        entity="employee_movement",
        entity_id=str(item.id),
        details=f"{employee.employee_number}:{item.movement_type}",
        before=item.before_data,
        after=item.after_data,
    )
    db.commit()
    db.refresh(item)
    return item
