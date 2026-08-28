from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .advanced_models import (
    ContractStatus,
    ESocialEventStatus,
    InterviewStatus,
    InvoiceStatus,
    OfferStatus,
    PerformanceStatus,
    RequisitionStatus,
    ReviewStatus,
)


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class JobRequisitionCreate(BaseModel):
    code: str = Field(min_length=2, max_length=40)
    title: str = Field(min_length=2, max_length=160)
    reason: str = Field(default="replacement", max_length=80)
    positions: int = Field(default=1, ge=1, le=10_000)
    department_id: int | None = None
    description: str = Field(default="", max_length=20_000)


class JobRequisitionRead(JobRequisitionCreate, ORMModel):
    id: int
    requested_by_id: int
    approved_by_id: int | None
    status: RequisitionStatus
    approved_at: datetime | None
    created_at: datetime
    updated_at: datetime


class RequisitionDecision(BaseModel):
    approved: bool
    reason: str = Field(default="", max_length=1_000)


class StageTransition(BaseModel):
    stage: str = Field(min_length=2, max_length=40)
    reason: str = Field(default="", max_length=240)


class StageHistoryRead(ORMModel):
    id: int
    application_id: int
    from_stage: str
    to_stage: str
    reason: str
    changed_by_id: int | None
    changed_at: datetime


class InterviewCreate(BaseModel):
    application_id: int
    scheduled_at: datetime
    duration_minutes: int = Field(default=60, ge=15, le=480)
    location: str = Field(default="", max_length=240)
    interviewer_ids: list[int] = Field(default_factory=list, max_length=30)
    notes: str = Field(default="", max_length=10_000)


class InterviewUpdate(BaseModel):
    scheduled_at: datetime | None = None
    duration_minutes: int | None = Field(default=None, ge=15, le=480)
    location: str | None = Field(default=None, max_length=240)
    interviewer_ids: list[int] | None = Field(default=None, max_length=30)
    status: InterviewStatus | None = None
    notes: str | None = Field(default=None, max_length=10_000)


class InterviewRead(InterviewCreate, ORMModel):
    id: int
    status: InterviewStatus
    created_by_id: int | None
    created_at: datetime
    updated_at: datetime


class ScorecardCreate(BaseModel):
    overall_score: int = Field(ge=1, le=5)
    recommendation: str = Field(default="neutral", pattern=r"^(strong_no|no|neutral|yes|strong_yes)$")
    criteria: dict[str, int] = Field(default_factory=dict)
    feedback: str = Field(default="", max_length=10_000)

    @model_validator(mode="after")
    def validate_criteria(self):
        if any(score < 1 or score > 5 for score in self.criteria.values()):
            raise ValueError("Cada critério deve receber nota entre 1 e 5")
        return self


class ScorecardRead(ScorecardCreate, ORMModel):
    id: int
    interview_id: int
    evaluator_id: int
    submitted_at: datetime


class OfferCreate(BaseModel):
    application_id: int
    salary: Decimal = Field(gt=0)
    currency: str = Field(default="BRL", min_length=3, max_length=3)
    start_date: date | None = None
    expires_at: datetime | None = None
    notes: str = Field(default="", max_length=10_000)


class OfferStatusUpdate(BaseModel):
    status: OfferStatus
    reason: str = Field(default="", max_length=1_000)


class OfferRead(OfferCreate, ORMModel):
    id: int
    status: OfferStatus
    created_by_id: int | None
    created_at: datetime
    updated_at: datetime


class ContractCreate(BaseModel):
    employee_id: int
    contract_number: str = Field(min_length=1, max_length=60)
    contract_type: str = Field(default="clt", max_length=40)
    start_date: date
    end_date: date | None = None
    weekly_hours: Decimal = Field(default=Decimal("44.00"), gt=0, le=168)
    salary: Decimal = Field(gt=0)
    currency: str = Field(default="BRL", min_length=3, max_length=3)
    status: ContractStatus = ContractStatus.planned

    @model_validator(mode="after")
    def validate_dates(self):
        if self.end_date and self.end_date < self.start_date:
            raise ValueError("O término não pode anteceder o início")
        return self


class ContractRead(ContractCreate, ORMModel):
    id: int
    created_at: datetime
    updated_at: datetime


class EmployeeMovementCreate(BaseModel):
    employee_id: int
    movement_type: str = Field(min_length=2, max_length=60)
    effective_date: date
    reason: str = Field(default="", max_length=240)
    before_data: dict = Field(default_factory=dict)
    after_data: dict = Field(default_factory=dict)


class EmployeeMovementRead(EmployeeMovementCreate, ORMModel):
    id: int
    approved_by_id: int | None
    created_at: datetime


class PerformanceCycleCreate(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    start_date: date
    end_date: date
    description: str = Field(default="", max_length=10_000)

    @model_validator(mode="after")
    def validate_dates(self):
        if self.end_date < self.start_date:
            raise ValueError("O fim do ciclo não pode anteceder o início")
        return self


class PerformanceCycleUpdate(BaseModel):
    status: PerformanceStatus


class PerformanceCycleRead(PerformanceCycleCreate, ORMModel):
    id: int
    status: PerformanceStatus
    created_at: datetime
    updated_at: datetime


class PerformanceGoalCreate(BaseModel):
    cycle_id: int
    employee_id: int
    title: str = Field(min_length=2, max_length=200)
    description: str = Field(default="", max_length=10_000)
    target_value: str = Field(default="", max_length=120)
    progress: int = Field(default=0, ge=0, le=100)
    status: str = Field(default="not_started", max_length=40)


class PerformanceGoalRead(PerformanceGoalCreate, ORMModel):
    id: int
    created_at: datetime
    updated_at: datetime


class PerformanceReviewCreate(BaseModel):
    cycle_id: int
    reviewee_id: int
    score: Decimal | None = Field(default=None, ge=1, le=5)
    strengths: str = Field(default="", max_length=10_000)
    development: str = Field(default="", max_length=10_000)
    status: ReviewStatus = ReviewStatus.in_progress


class PerformanceReviewRead(PerformanceReviewCreate, ORMModel):
    id: int
    reviewer_id: int
    submitted_at: datetime | None
    created_at: datetime
    updated_at: datetime


class ESocialEventCreate(BaseModel):
    employee_id: int | None = None
    event_type: str = Field(min_length=4, max_length=20, pattern=r"^S-\d{4}$")
    reference: str = Field(default="", max_length=80)
    layout_version: str = Field(default="S-1.3", max_length=20)
    idempotency_key: str = Field(min_length=8, max_length=120)
    payload: dict


class ESocialEventTransition(BaseModel):
    status: ESocialEventStatus
    receipt: str = Field(default="", max_length=160)
    error_message: str = Field(default="", max_length=10_000)


class ESocialEventRead(ESocialEventCreate, ORMModel):
    id: int
    status: ESocialEventStatus
    receipt: str
    error_message: str
    attempts: int
    created_by_id: int | None
    created_at: datetime
    updated_at: datetime


class UsageRecordCreate(BaseModel):
    metric: str = Field(min_length=2, max_length=80)
    period: str = Field(pattern=r"^\d{4}-(0[1-9]|1[0-2])$")
    quantity: int = Field(ge=0)


class UsageRecordRead(UsageRecordCreate, ORMModel):
    id: int
    updated_at: datetime


class InvoiceCreate(BaseModel):
    number: str = Field(min_length=2, max_length=60)
    period: str = Field(pattern=r"^\d{4}-(0[1-9]|1[0-2])$")
    amount: Decimal = Field(ge=0)
    currency: str = Field(default="BRL", min_length=3, max_length=3)
    due_date: date
    provider_reference: str = Field(default="", max_length=160)


class InvoiceUpdate(BaseModel):
    status: InvoiceStatus
    provider_reference: str | None = Field(default=None, max_length=160)


class InvoiceRead(InvoiceCreate, ORMModel):
    id: int
    status: InvoiceStatus
    created_at: datetime
    updated_at: datetime


class BillingSummary(BaseModel):
    plan_code: str
    subscription_status: str
    employee_limit: int
    enabled_modules: list[str]
    usage: list[UsageRecordRead]
    open_invoices: list[InvoiceRead]
