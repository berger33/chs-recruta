from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from enum import Enum

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Index, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base
from .models import enum_type, utcnow


class BenefitEnrollmentStatus(str, Enum):
    requested = "requested"
    active = "active"
    rejected = "rejected"
    cancelled = "cancelled"


class OnboardingTemplate(Base):
    __tablename__ = "onboarding_templates"
    __table_args__ = (UniqueConstraint("tenant_id", "name", name="uq_onboarding_template_name"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(160))
    description: Mapped[str] = mapped_column(Text, default="")
    active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


class OnboardingTemplateItem(Base):
    __tablename__ = "onboarding_template_items"
    __table_args__ = (
        UniqueConstraint("tenant_id", "template_id", "position", name="uq_onboarding_item_position"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    template_id: Mapped[int] = mapped_column(
        ForeignKey("onboarding_templates.id", ondelete="CASCADE"), index=True
    )
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    due_offset_days: Mapped[int] = mapped_column(Integer, default=0)
    assigned_role: Mapped[str] = mapped_column(String(40), default="hr")
    position: Mapped[int] = mapped_column(Integer)
    required: Mapped[bool] = mapped_column(Boolean, default=True)


class OnboardingApplication(Base):
    __tablename__ = "onboarding_applications"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "template_id", "employee_id", name="uq_onboarding_application"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    template_id: Mapped[int] = mapped_column(
        ForeignKey("onboarding_templates.id", ondelete="CASCADE"), index=True
    )
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id", ondelete="CASCADE"), index=True)
    anchor_date: Mapped[date] = mapped_column(Date)
    applied_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    applied_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class BenefitEligibilityRule(Base):
    __tablename__ = "benefit_eligibility_rules"
    __table_args__ = (UniqueConstraint("tenant_id", "plan_id", name="uq_benefit_rule_plan"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    plan_id: Mapped[int] = mapped_column(ForeignKey("benefit_plans.id", ondelete="CASCADE"), index=True)
    department_id: Mapped[int | None] = mapped_column(
        ForeignKey("departments.id", ondelete="SET NULL"), index=True
    )
    employment_status: Mapped[str] = mapped_column(String(40), default="")
    minimum_tenure_days: Mapped[int] = mapped_column(Integer, default=0)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


class BenefitEnrollment(Base):
    __tablename__ = "benefit_enrollments"
    __table_args__ = (
        Index("ix_benefit_enrollment_tenant_status", "tenant_id", "status"),
        Index("ix_benefit_enrollment_employee_plan", "tenant_id", "employee_id", "plan_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id", ondelete="CASCADE"), index=True)
    plan_id: Mapped[int] = mapped_column(ForeignKey("benefit_plans.id", ondelete="CASCADE"), index=True)
    status: Mapped[BenefitEnrollmentStatus] = mapped_column(
        enum_type(BenefitEnrollmentStatus, "benefit_enrollment_status"),
        default=BenefitEnrollmentStatus.requested,
        index=True,
    )
    effective_on: Mapped[date | None] = mapped_column(Date)
    ends_on: Mapped[date | None] = mapped_column(Date)
    employee_contribution: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"))
    employer_contribution: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"))
    decision_notes: Mapped[str] = mapped_column(Text, default="")
    requested_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    decided_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    decided_at: Mapped[datetime | None] = mapped_column(DateTime)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

