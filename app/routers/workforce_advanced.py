from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import BenefitPlan, Department, Employee, OnboardingTask, TaskStatus
from ..permissions import Permission
from ..security import AuthContext, current_context, require_permissions
from ..services import audit, model_snapshot
from ..workforce_models import (
    BenefitEligibilityRule,
    BenefitEnrollment,
    BenefitEnrollmentStatus,
    OnboardingApplication,
    OnboardingTemplate,
    OnboardingTemplateItem,
)
from ..workforce_schemas import (
    AppliedTemplateRead,
    ApplyTemplate,
    BenefitEligibilityRead,
    BenefitEnrollmentCreate,
    BenefitEnrollmentRead,
    BenefitEnrollmentTransition,
    EligibilityRuleRead,
    EligibilityRuleUpsert,
    OnboardingTemplateCreate,
    OnboardingTemplateRead,
)

router = APIRouter(prefix="/api/workforce", tags=["workforce-advanced"])

ENROLLMENT_TRANSITIONS = {
    BenefitEnrollmentStatus.requested: {
        BenefitEnrollmentStatus.active,
        BenefitEnrollmentStatus.rejected,
    },
    BenefitEnrollmentStatus.active: {BenefitEnrollmentStatus.cancelled},
    BenefitEnrollmentStatus.rejected: set(),
    BenefitEnrollmentStatus.cancelled: set(),
}


def now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def tenant_employee(db: Session, context: AuthContext, employee_id: int) -> Employee:
    employee = db.scalar(
        select(Employee).where(Employee.id == employee_id, Employee.tenant_id == context.tenant_id)
    )
    if not employee:
        raise HTTPException(status_code=404, detail="Colaborador não encontrado nesta empresa")
    return employee


def own_employee(db: Session, context: AuthContext) -> Employee:
    employee = db.scalar(
        select(Employee).where(
            Employee.tenant_id == context.tenant_id,
            Employee.user_id == context.user.id,
        )
    )
    if not employee:
        raise HTTPException(status_code=403, detail="Usuário não está vinculado a um colaborador")
    return employee


def tenant_plan(db: Session, context: AuthContext, plan_id: int) -> BenefitPlan:
    plan = db.scalar(
        select(BenefitPlan).where(
            BenefitPlan.id == plan_id,
            BenefitPlan.tenant_id == context.tenant_id,
            BenefitPlan.active.is_(True),
        )
    )
    if not plan:
        raise HTTPException(status_code=404, detail="Benefício não encontrado nesta empresa")
    return plan


def template_payload(db: Session, template: OnboardingTemplate) -> dict:
    items = db.scalars(
        select(OnboardingTemplateItem)
        .where(
            OnboardingTemplateItem.tenant_id == template.tenant_id,
            OnboardingTemplateItem.template_id == template.id,
        )
        .order_by(OnboardingTemplateItem.position)
    ).all()
    return {
        **model_snapshot(template),
        "items": [model_snapshot(item) for item in items],
    }


@router.get("/onboarding/templates", response_model=list[OnboardingTemplateRead])
def list_templates(
    context: Annotated[AuthContext, Depends(require_permissions(Permission.onboarding_manage))],
    db: Annotated[Session, Depends(get_db)],
):
    templates = db.scalars(
        select(OnboardingTemplate)
        .where(OnboardingTemplate.tenant_id == context.tenant_id)
        .order_by(OnboardingTemplate.active.desc(), OnboardingTemplate.name)
    ).all()
    return [template_payload(db, template) for template in templates]


@router.post("/onboarding/templates", response_model=OnboardingTemplateRead, status_code=201)
def create_template(
    payload: OnboardingTemplateCreate,
    request: Request,
    context: Annotated[AuthContext, Depends(require_permissions(Permission.onboarding_manage))],
    db: Annotated[Session, Depends(get_db)],
):
    template = OnboardingTemplate(
        tenant_id=context.tenant_id,
        name=payload.name,
        description=payload.description,
        active=payload.active,
        created_by_id=context.user.id,
    )
    db.add(template)
    try:
        db.flush()
        for item in payload.items:
            db.add(
                OnboardingTemplateItem(
                    tenant_id=context.tenant_id,
                    template_id=template.id,
                    **item.model_dump(),
                )
            )
        db.flush()
    except IntegrityError as error:
        db.rollback()
        raise HTTPException(status_code=409, detail="Template ou posição já cadastrado") from error
    audit(
        db,
        context=context,
        request=request,
        action="create",
        entity="onboarding_template",
        entity_id=str(template.id),
        details=f"{template.name}: {len(payload.items)} tarefas",
        after=model_snapshot(template),
    )
    db.commit()
    db.refresh(template)
    return template_payload(db, template)


@router.post(
    "/onboarding/templates/{template_id}/apply",
    response_model=AppliedTemplateRead,
    status_code=201,
)
def apply_template(
    template_id: int,
    payload: ApplyTemplate,
    request: Request,
    context: Annotated[AuthContext, Depends(require_permissions(Permission.onboarding_manage))],
    db: Annotated[Session, Depends(get_db)],
):
    template = db.scalar(
        select(OnboardingTemplate).where(
            OnboardingTemplate.id == template_id,
            OnboardingTemplate.tenant_id == context.tenant_id,
            OnboardingTemplate.active.is_(True),
        )
    )
    if not template:
        raise HTTPException(status_code=404, detail="Template ativo não encontrado")
    employee = tenant_employee(db, context, payload.employee_id)
    if db.scalar(
        select(OnboardingApplication.id).where(
            OnboardingApplication.tenant_id == context.tenant_id,
            OnboardingApplication.template_id == template.id,
            OnboardingApplication.employee_id == employee.id,
        )
    ):
        raise HTTPException(status_code=409, detail="Template já aplicado a este colaborador")
    anchor = payload.anchor_date or employee.hire_date or date.today()
    application = OnboardingApplication(
        tenant_id=context.tenant_id,
        template_id=template.id,
        employee_id=employee.id,
        anchor_date=anchor,
        applied_by_id=context.user.id,
    )
    db.add(application)
    db.flush()
    manager_user_id = None
    if employee.manager_id:
        manager = db.scalar(
            select(Employee).where(
                Employee.id == employee.manager_id,
                Employee.tenant_id == context.tenant_id,
            )
        )
        manager_user_id = manager.user_id if manager else None
    items = db.scalars(
        select(OnboardingTemplateItem)
        .where(
            OnboardingTemplateItem.tenant_id == context.tenant_id,
            OnboardingTemplateItem.template_id == template.id,
        )
        .order_by(OnboardingTemplateItem.position)
    ).all()
    task_ids = []
    for item in items:
        assigned_to = {
            "employee": employee.user_id,
            "manager": manager_user_id,
        }.get(item.assigned_role)
        description = item.description
        if not item.required:
            description = "Tarefa opcional. " + description
        task = OnboardingTask(
            tenant_id=context.tenant_id,
            employee_id=employee.id,
            title=item.title,
            description=description.strip(),
            status=TaskStatus.pendente,
            due_date=anchor + timedelta(days=item.due_offset_days),
            assigned_to_id=assigned_to,
        )
        db.add(task)
        db.flush()
        task_ids.append(task.id)
    audit(
        db,
        context=context,
        request=request,
        action="apply",
        entity="onboarding_template",
        entity_id=str(template.id),
        details=f"employee={employee.id}; tasks={len(task_ids)}",
        after={"application_id": application.id, "task_ids": task_ids},
    )
    db.commit()
    return AppliedTemplateRead(
        application_id=application.id,
        employee_id=employee.id,
        template_id=template.id,
        task_ids=task_ids,
    )


def evaluate_eligibility(
    db: Session, context: AuthContext, employee: Employee, plan: BenefitPlan
) -> BenefitEligibilityRead:
    rule = db.scalar(
        select(BenefitEligibilityRule).where(
            BenefitEligibilityRule.tenant_id == context.tenant_id,
            BenefitEligibilityRule.plan_id == plan.id,
            BenefitEligibilityRule.active.is_(True),
        )
    )
    if not rule:
        return BenefitEligibilityRead(
            plan_id=plan.id, plan_name=plan.name, eligible=True, reason="Sem restrição ativa"
        )
    if rule.department_id is not None and employee.department_id != rule.department_id:
        return BenefitEligibilityRead(
            plan_id=plan.id, plan_name=plan.name, eligible=False, reason="Departamento não elegível"
        )
    if rule.employment_status and employee.status.value != rule.employment_status:
        return BenefitEligibilityRead(
            plan_id=plan.id, plan_name=plan.name, eligible=False, reason="Vínculo não elegível"
        )
    if rule.minimum_tenure_days:
        if not employee.hire_date:
            return BenefitEligibilityRead(
                plan_id=plan.id,
                plan_name=plan.name,
                eligible=False,
                reason="Data de admissão ausente",
            )
        tenure = (date.today() - employee.hire_date).days
        if tenure < rule.minimum_tenure_days:
            return BenefitEligibilityRead(
                plan_id=plan.id,
                plan_name=plan.name,
                eligible=False,
                reason=f"Carência de {rule.minimum_tenure_days} dias",
            )
    return BenefitEligibilityRead(
        plan_id=plan.id, plan_name=plan.name, eligible=True, reason="Critérios atendidos"
    )


@router.put("/benefits/{plan_id}/eligibility", response_model=EligibilityRuleRead)
def upsert_eligibility_rule(
    plan_id: int,
    payload: EligibilityRuleUpsert,
    request: Request,
    context: Annotated[AuthContext, Depends(require_permissions(Permission.benefits_manage))],
    db: Annotated[Session, Depends(get_db)],
):
    tenant_plan(db, context, plan_id)
    if payload.department_id is not None and not db.scalar(
        select(Department.id).where(
            Department.id == payload.department_id,
            Department.tenant_id == context.tenant_id,
        )
    ):
        raise HTTPException(status_code=404, detail="Departamento não encontrado nesta empresa")
    rule = db.scalar(
        select(BenefitEligibilityRule).where(
            BenefitEligibilityRule.tenant_id == context.tenant_id,
            BenefitEligibilityRule.plan_id == plan_id,
        )
    )
    before = model_snapshot(rule) if rule else None
    if rule:
        for key, value in payload.model_dump().items():
            setattr(rule, key, value)
    else:
        rule = BenefitEligibilityRule(
            tenant_id=context.tenant_id, plan_id=plan_id, **payload.model_dump()
        )
        db.add(rule)
        db.flush()
    audit(
        db,
        context=context,
        request=request,
        action="upsert",
        entity="benefit_eligibility_rule",
        entity_id=str(rule.id),
        before=before,
        after=model_snapshot(rule),
    )
    db.commit()
    db.refresh(rule)
    return rule


@router.get("/benefits/eligibility", response_model=list[BenefitEligibilityRead])
def list_eligibility(
    context: Annotated[AuthContext, Depends(current_context)],
    db: Annotated[Session, Depends(get_db)],
    employee_id: int | None = None,
):
    if employee_id is not None:
        if Permission.benefits_manage not in context.permissions:
            employee = own_employee(db, context)
            if employee.id != employee_id:
                raise HTTPException(status_code=403, detail="Acesso limitado à própria elegibilidade")
        else:
            employee = tenant_employee(db, context, employee_id)
    else:
        employee = own_employee(db, context)
    plans = db.scalars(
        select(BenefitPlan)
        .where(BenefitPlan.tenant_id == context.tenant_id, BenefitPlan.active.is_(True))
        .order_by(BenefitPlan.name)
    ).all()
    return [evaluate_eligibility(db, context, employee, plan) for plan in plans]


def enrollment_target(
    db: Session, context: AuthContext, employee_id: int | None
) -> Employee:
    if employee_id is None:
        return own_employee(db, context)
    employee = tenant_employee(db, context, employee_id)
    if Permission.benefits_manage not in context.permissions:
        own = own_employee(db, context)
        if employee.id != own.id:
            raise HTTPException(status_code=403, detail="Acesso limitado à própria adesão")
    return employee


@router.get("/benefits/enrollments", response_model=list[BenefitEnrollmentRead])
def list_enrollments(
    context: Annotated[AuthContext, Depends(current_context)],
    db: Annotated[Session, Depends(get_db)],
    employee_id: int | None = None,
):
    statement = select(BenefitEnrollment).where(
        BenefitEnrollment.tenant_id == context.tenant_id
    )
    if Permission.benefits_manage in context.permissions:
        if employee_id is not None:
            tenant_employee(db, context, employee_id)
            statement = statement.where(BenefitEnrollment.employee_id == employee_id)
    else:
        employee = own_employee(db, context)
        if employee_id is not None and employee_id != employee.id:
            raise HTTPException(status_code=403, detail="Acesso limitado às próprias adesões")
        statement = statement.where(BenefitEnrollment.employee_id == employee.id)
    return db.scalars(statement.order_by(BenefitEnrollment.updated_at.desc())).all()


@router.post("/benefits/enrollments", response_model=BenefitEnrollmentRead, status_code=201)
def create_enrollment(
    payload: BenefitEnrollmentCreate,
    request: Request,
    context: Annotated[AuthContext, Depends(current_context)],
    db: Annotated[Session, Depends(get_db)],
):
    employee = enrollment_target(db, context, payload.employee_id)
    plan = tenant_plan(db, context, payload.plan_id)
    eligibility = evaluate_eligibility(db, context, employee, plan)
    if not eligibility.eligible:
        raise HTTPException(status_code=409, detail=f"Não elegível: {eligibility.reason}")
    if db.scalar(
        select(BenefitEnrollment.id).where(
            BenefitEnrollment.tenant_id == context.tenant_id,
            BenefitEnrollment.employee_id == employee.id,
            BenefitEnrollment.plan_id == plan.id,
            BenefitEnrollment.status.in_(
                [BenefitEnrollmentStatus.requested, BenefitEnrollmentStatus.active]
            ),
        )
    ):
        raise HTTPException(status_code=409, detail="Já existe adesão ativa ou pendente")
    item = BenefitEnrollment(
        tenant_id=context.tenant_id,
        employee_id=employee.id,
        plan_id=plan.id,
        effective_on=payload.effective_on,
        employee_contribution=plan.employee_cost,
        employer_contribution=Decimal("0.00"),
    )
    db.add(item)
    db.flush()
    audit(
        db,
        context=context,
        request=request,
        action="request",
        entity="benefit_enrollment",
        entity_id=str(item.id),
        details=f"employee={employee.id}; plan={plan.id}",
        after=model_snapshot(item),
    )
    db.commit()
    db.refresh(item)
    return item


@router.patch("/benefits/enrollments/{enrollment_id}", response_model=BenefitEnrollmentRead)
def transition_enrollment(
    enrollment_id: int,
    payload: BenefitEnrollmentTransition,
    request: Request,
    context: Annotated[AuthContext, Depends(current_context)],
    db: Annotated[Session, Depends(get_db)],
):
    item = db.scalar(
        select(BenefitEnrollment).where(
            BenefitEnrollment.id == enrollment_id,
            BenefitEnrollment.tenant_id == context.tenant_id,
        )
    )
    if not item:
        raise HTTPException(status_code=404, detail="Adesão não encontrada")
    can_manage = Permission.benefits_manage in context.permissions
    if not can_manage:
        employee = own_employee(db, context)
        if (
            item.employee_id != employee.id
            or item.status != BenefitEnrollmentStatus.requested
            or payload.status != BenefitEnrollmentStatus.cancelled
        ):
            raise HTTPException(status_code=403, detail="Somente o RH pode decidir a adesão")
        if any(
            value is not None
            for value in (
                payload.effective_on,
                payload.ends_on,
                payload.employee_contribution,
                payload.employer_contribution,
            )
        ):
            raise HTTPException(status_code=403, detail="Colaborador não pode alterar a vigência ou valores")
    elif payload.status not in ENROLLMENT_TRANSITIONS[item.status]:
        raise HTTPException(
            status_code=409,
            detail=f"Transição inválida: {item.status.value} → {payload.status.value}",
        )
    effective_on = payload.effective_on or item.effective_on
    if payload.status == BenefitEnrollmentStatus.active and effective_on is None:
        effective_on = date.today()
    if payload.ends_on and effective_on and payload.ends_on < effective_on:
        raise HTTPException(status_code=422, detail="Fim deve ser posterior ao início da vigência")
    before = model_snapshot(item)
    item.status = payload.status
    item.effective_on = effective_on
    item.ends_on = payload.ends_on
    item.decision_notes = payload.decision_notes
    if payload.employee_contribution is not None:
        item.employee_contribution = payload.employee_contribution
    if payload.employer_contribution is not None:
        item.employer_contribution = payload.employer_contribution
    item.decided_by_id = context.user.id
    item.decided_at = now()
    audit(
        db,
        context=context,
        request=request,
        action="transition",
        entity="benefit_enrollment",
        entity_id=str(item.id),
        details=f"{before['status']} → {item.status.value}",
        before=before,
        after=model_snapshot(item),
    )
    db.commit()
    db.refresh(item)
    return item
