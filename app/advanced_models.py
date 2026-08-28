from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from enum import Enum

from sqlalchemy import JSON, Date, DateTime, ForeignKey, Index, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base
from .models import enum_type, utcnow


class RequisitionStatus(str, Enum):
    draft = "draft"
    pending = "pending"
    approved = "approved"
    rejected = "rejected"
    converted = "converted"
    canceled = "canceled"


class InterviewStatus(str, Enum):
    scheduled = "scheduled"
    completed = "completed"
    canceled = "canceled"
    no_show = "no_show"


class OfferStatus(str, Enum):
    draft = "draft"
    sent = "sent"
    accepted = "accepted"
    declined = "declined"
    expired = "expired"
    canceled = "canceled"


class ContractStatus(str, Enum):
    planned = "planned"
    active = "active"
    suspended = "suspended"
    ended = "ended"


class PerformanceStatus(str, Enum):
    draft = "draft"
    active = "active"
    calibration = "calibration"
    closed = "closed"


class ReviewStatus(str, Enum):
    pending = "pending"
    in_progress = "in_progress"
    submitted = "submitted"
    acknowledged = "acknowledged"


class ESocialEventStatus(str, Enum):
    draft = "draft"
    validated = "validated"
    queued = "queued"
    sent = "sent"
    accepted = "accepted"
    rejected = "rejected"


class InvoiceStatus(str, Enum):
    draft = "draft"
    open = "open"
    paid = "paid"
    past_due = "past_due"
    void = "void"


class JobRequisition(Base):
    __tablename__ = "job_requisitions"
    __table_args__ = (UniqueConstraint("tenant_id", "code", name="uq_requisition_tenant_code"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    code: Mapped[str] = mapped_column(String(40), index=True)
    title: Mapped[str] = mapped_column(String(160))
    reason: Mapped[str] = mapped_column(String(80), default="replacement")
    positions: Mapped[int] = mapped_column(Integer, default=1)
    department_id: Mapped[int | None] = mapped_column(ForeignKey("departments.id", ondelete="SET NULL"))
    requested_by_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    approved_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    status: Mapped[RequisitionStatus] = mapped_column(
        enum_type(RequisitionStatus, "requisition_status"), default=RequisitionStatus.draft, index=True
    )
    description: Mapped[str] = mapped_column(Text, default="")
    approved_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


class ApplicationStageHistory(Base):
    __tablename__ = "application_stage_history"
    __table_args__ = (Index("ix_stage_history_tenant_application", "tenant_id", "application_id", "changed_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    application_id: Mapped[int] = mapped_column(ForeignKey("applications.id", ondelete="CASCADE"), index=True)
    from_stage: Mapped[str] = mapped_column(String(40), default="")
    to_stage: Mapped[str] = mapped_column(String(40))
    reason: Mapped[str] = mapped_column(String(240), default="")
    changed_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    changed_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Interview(Base):
    __tablename__ = "interviews"
    __table_args__ = (Index("ix_interview_tenant_schedule", "tenant_id", "scheduled_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    application_id: Mapped[int] = mapped_column(ForeignKey("applications.id", ondelete="CASCADE"), index=True)
    scheduled_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    duration_minutes: Mapped[int] = mapped_column(Integer, default=60)
    location: Mapped[str] = mapped_column(String(240), default="")
    interviewer_ids: Mapped[list[int]] = mapped_column(JSON, default=list)
    status: Mapped[InterviewStatus] = mapped_column(
        enum_type(InterviewStatus, "interview_status"), default=InterviewStatus.scheduled, index=True
    )
    notes: Mapped[str] = mapped_column(Text, default="")
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


class Scorecard(Base):
    __tablename__ = "scorecards"
    __table_args__ = (UniqueConstraint("tenant_id", "interview_id", "evaluator_id", name="uq_scorecard_evaluator"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    interview_id: Mapped[int] = mapped_column(ForeignKey("interviews.id", ondelete="CASCADE"), index=True)
    evaluator_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    overall_score: Mapped[int] = mapped_column(Integer)
    recommendation: Mapped[str] = mapped_column(String(40), default="neutral")
    criteria: Mapped[dict] = mapped_column(JSON, default=dict)
    feedback: Mapped[str] = mapped_column(Text, default="")
    submitted_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Offer(Base):
    __tablename__ = "offers"
    __table_args__ = (Index("ix_offer_tenant_status", "tenant_id", "status"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    application_id: Mapped[int] = mapped_column(ForeignKey("applications.id", ondelete="CASCADE"), index=True)
    salary: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    currency: Mapped[str] = mapped_column(String(3), default="BRL")
    start_date: Mapped[date | None] = mapped_column(Date)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime)
    status: Mapped[OfferStatus] = mapped_column(
        enum_type(OfferStatus, "offer_status"), default=OfferStatus.draft, index=True
    )
    notes: Mapped[str] = mapped_column(Text, default="")
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


class EmploymentContract(Base):
    __tablename__ = "employment_contracts"
    __table_args__ = (
        UniqueConstraint("tenant_id", "employee_id", "contract_number", name="uq_contract_tenant_number"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id", ondelete="CASCADE"), index=True)
    contract_number: Mapped[str] = mapped_column(String(60))
    contract_type: Mapped[str] = mapped_column(String(40), default="clt")
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date | None] = mapped_column(Date)
    weekly_hours: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=Decimal("44.00"))
    salary: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    currency: Mapped[str] = mapped_column(String(3), default="BRL")
    status: Mapped[ContractStatus] = mapped_column(
        enum_type(ContractStatus, "contract_status"), default=ContractStatus.planned, index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


class EmployeeMovement(Base):
    __tablename__ = "employee_movements"
    __table_args__ = (Index("ix_movement_tenant_employee_effective", "tenant_id", "employee_id", "effective_date"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id", ondelete="CASCADE"), index=True)
    movement_type: Mapped[str] = mapped_column(String(60))
    effective_date: Mapped[date] = mapped_column(Date)
    reason: Mapped[str] = mapped_column(String(240), default="")
    before_data: Mapped[dict] = mapped_column(JSON, default=dict)
    after_data: Mapped[dict] = mapped_column(JSON, default=dict)
    approved_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class PerformanceCycle(Base):
    __tablename__ = "performance_cycles"
    __table_args__ = (UniqueConstraint("tenant_id", "name", name="uq_performance_cycle_name"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(160))
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date] = mapped_column(Date)
    status: Mapped[PerformanceStatus] = mapped_column(
        enum_type(PerformanceStatus, "performance_status"), default=PerformanceStatus.draft, index=True
    )
    description: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


class PerformanceGoal(Base):
    __tablename__ = "performance_goals"
    __table_args__ = (Index("ix_goal_tenant_employee_cycle", "tenant_id", "employee_id", "cycle_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    cycle_id: Mapped[int] = mapped_column(ForeignKey("performance_cycles.id", ondelete="CASCADE"), index=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    target_value: Mapped[str] = mapped_column(String(120), default="")
    progress: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(40), default="not_started")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


class PerformanceReview(Base):
    __tablename__ = "performance_reviews"
    __table_args__ = (
        UniqueConstraint("tenant_id", "cycle_id", "reviewee_id", "reviewer_id", name="uq_performance_review"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    cycle_id: Mapped[int] = mapped_column(ForeignKey("performance_cycles.id", ondelete="CASCADE"), index=True)
    reviewee_id: Mapped[int] = mapped_column(ForeignKey("employees.id", ondelete="CASCADE"), index=True)
    reviewer_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), index=True)
    score: Mapped[Decimal | None] = mapped_column(Numeric(4, 2))
    strengths: Mapped[str] = mapped_column(Text, default="")
    development: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[ReviewStatus] = mapped_column(
        enum_type(ReviewStatus, "review_status"), default=ReviewStatus.pending, index=True
    )
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


class ESocialEvent(Base):
    __tablename__ = "esocial_events"
    __table_args__ = (
        UniqueConstraint("tenant_id", "idempotency_key", name="uq_esocial_idempotency"),
        Index("ix_esocial_tenant_status", "tenant_id", "status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    employee_id: Mapped[int | None] = mapped_column(ForeignKey("employees.id", ondelete="SET NULL"), index=True)
    event_type: Mapped[str] = mapped_column(String(20), index=True)
    reference: Mapped[str] = mapped_column(String(80), default="")
    layout_version: Mapped[str] = mapped_column(String(20), default="S-1.3")
    idempotency_key: Mapped[str] = mapped_column(String(120))
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[ESocialEventStatus] = mapped_column(
        enum_type(ESocialEventStatus, "esocial_event_status"), default=ESocialEventStatus.draft, index=True
    )
    receipt: Mapped[str] = mapped_column(String(160), default="")
    error_message: Mapped[str] = mapped_column(Text, default="")
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


class UsageRecord(Base):
    __tablename__ = "usage_records"
    __table_args__ = (
        UniqueConstraint("tenant_id", "metric", "period", name="uq_usage_tenant_metric_period"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    metric: Mapped[str] = mapped_column(String(80))
    period: Mapped[str] = mapped_column(String(7))
    quantity: Mapped[int] = mapped_column(Integer, default=0)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


class SaaSInvoice(Base):
    __tablename__ = "saas_invoices"
    __table_args__ = (UniqueConstraint("tenant_id", "number", name="uq_invoice_tenant_number"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    number: Mapped[str] = mapped_column(String(60))
    period: Mapped[str] = mapped_column(String(7))
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    currency: Mapped[str] = mapped_column(String(3), default="BRL")
    status: Mapped[InvoiceStatus] = mapped_column(
        enum_type(InvoiceStatus, "invoice_status"), default=InvoiceStatus.draft, index=True
    )
    due_date: Mapped[date] = mapped_column(Date)
    provider_reference: Mapped[str] = mapped_column(String(160), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)
