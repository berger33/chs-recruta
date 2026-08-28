from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .workforce_models import BenefitEnrollmentStatus


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class TemplateItemCreate(BaseModel):
    title: str = Field(min_length=2, max_length=200)
    description: str = Field(default="", max_length=10_000)
    due_offset_days: int = Field(default=0, ge=-30, le=365)
    assigned_role: str = Field(
        default="hr", pattern=r"^(employee|manager|hr|it|facilities)$"
    )
    position: int = Field(ge=1, le=1_000)
    required: bool = True


class TemplateItemRead(TemplateItemCreate, ORMModel):
    id: int


class OnboardingTemplateCreate(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    description: str = Field(default="", max_length=10_000)
    active: bool = True
    items: list[TemplateItemCreate] = Field(min_length=1, max_length=200)

    @model_validator(mode="after")
    def unique_positions(self):
        positions = [item.position for item in self.items]
        if len(positions) != len(set(positions)):
            raise ValueError("As posições das tarefas devem ser únicas")
        return self


class OnboardingTemplateRead(ORMModel):
    id: int
    name: str
    description: str
    active: bool
    created_at: datetime
    updated_at: datetime
    items: list[TemplateItemRead]


class ApplyTemplate(BaseModel):
    employee_id: int
    anchor_date: date | None = None


class AppliedTemplateRead(BaseModel):
    application_id: int
    employee_id: int
    template_id: int
    task_ids: list[int]


class EligibilityRuleUpsert(BaseModel):
    department_id: int | None = None
    employment_status: str = Field(
        default="", pattern=r"^(|pre_admissao|ativo|afastado|desligado)$"
    )
    minimum_tenure_days: int = Field(default=0, ge=0, le=36_500)
    active: bool = True


class EligibilityRuleRead(EligibilityRuleUpsert, ORMModel):
    id: int
    plan_id: int
    created_at: datetime
    updated_at: datetime


class BenefitEligibilityRead(BaseModel):
    plan_id: int
    plan_name: str
    eligible: bool
    reason: str


class BenefitEnrollmentCreate(BaseModel):
    employee_id: int | None = None
    plan_id: int
    effective_on: date | None = None


class BenefitEnrollmentTransition(BaseModel):
    status: BenefitEnrollmentStatus
    effective_on: date | None = None
    ends_on: date | None = None
    employee_contribution: Decimal | None = Field(default=None, ge=0)
    employer_contribution: Decimal | None = Field(default=None, ge=0)
    decision_notes: str = Field(default="", max_length=10_000)


class BenefitEnrollmentRead(ORMModel):
    id: int
    employee_id: int
    plan_id: int
    status: BenefitEnrollmentStatus
    effective_on: date | None
    ends_on: date | None
    employee_contribution: Decimal
    employer_contribution: Decimal
    decision_notes: str
    requested_at: datetime
    decided_by_id: int | None
    decided_at: datetime | None
    updated_at: datetime
