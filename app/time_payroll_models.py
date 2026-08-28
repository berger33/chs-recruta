from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from enum import Enum

from sqlalchemy import Date, DateTime, ForeignKey, Index, Integer, JSON, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base
from .models import TimeEntryKind, enum_type, utcnow


class TimeAdjustmentStatus(str, Enum):
    requested = "requested"
    approved = "approved"
    rejected = "rejected"
    cancelled = "cancelled"


class TimeAdjustmentAction(str, Enum):
    add = "add"
    replace = "replace"
    void = "void"


class TimesheetStatus(str, Enum):
    open = "open"
    submitted = "submitted"
    approved = "approved"
    locked = "locked"


class PayrollBatchStatus(str, Enum):
    uploaded = "uploaded"
    validated = "validated"
    published = "published"
    cancelled = "cancelled"


class WorkSchedule(Base):
    __tablename__ = "work_schedules"
    __table_args__ = (UniqueConstraint("tenant_id", "name", name="uq_work_schedule_name"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(160))
    timezone: Mapped[str] = mapped_column(String(64), default="America/Sao_Paulo")
    weekly_minutes: Mapped[int] = mapped_column(Integer, default=2640)
    break_minutes: Mapped[int] = mapped_column(Integer, default=60)
    tolerance_minutes: Mapped[int] = mapped_column(Integer, default=10)
    active: Mapped[bool] = mapped_column(default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


class EmployeeSchedule(Base):
    __tablename__ = "employee_schedules"
    __table_args__ = (Index("ix_employee_schedule_period", "tenant_id", "employee_id", "effective_from"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id", ondelete="CASCADE"), index=True)
    schedule_id: Mapped[int] = mapped_column(ForeignKey("work_schedules.id", ondelete="CASCADE"), index=True)
    effective_from: Mapped[date] = mapped_column(Date)
    effective_to: Mapped[date | None] = mapped_column(Date)
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class TimeAdjustmentRequest(Base):
    __tablename__ = "time_adjustment_requests"
    __table_args__ = (Index("ix_time_adjustment_request_status", "tenant_id", "status"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id", ondelete="CASCADE"), index=True)
    action: Mapped[TimeAdjustmentAction] = mapped_column(
        enum_type(TimeAdjustmentAction, "time_adjustment_action"), index=True
    )
    original_entry_id: Mapped[int | None] = mapped_column(
        ForeignKey("time_entries.id", ondelete="RESTRICT"), index=True
    )
    requested_kind: Mapped[TimeEntryKind | None] = mapped_column(
        enum_type(TimeEntryKind, "time_adjustment_kind")
    )
    requested_at: Mapped[datetime | None] = mapped_column(DateTime)
    reason: Mapped[str] = mapped_column(Text)
    status: Mapped[TimeAdjustmentStatus] = mapped_column(
        enum_type(TimeAdjustmentStatus, "time_adjustment_status"),
        default=TimeAdjustmentStatus.requested,
        index=True,
    )
    reviewed_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    review_notes: Mapped[str] = mapped_column(Text, default="")
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


class TimeAdjustment(Base):
    __tablename__ = "time_adjustments"
    __table_args__ = (UniqueConstraint("tenant_id", "request_id", name="uq_time_adjustment_request"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    request_id: Mapped[int] = mapped_column(
        ForeignKey("time_adjustment_requests.id", ondelete="RESTRICT"), index=True
    )
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id", ondelete="CASCADE"), index=True)
    action: Mapped[TimeAdjustmentAction] = mapped_column(
        enum_type(TimeAdjustmentAction, "approved_time_adjustment_action")
    )
    original_entry_id: Mapped[int | None] = mapped_column(
        ForeignKey("time_entries.id", ondelete="RESTRICT"), index=True
    )
    effective_kind: Mapped[TimeEntryKind | None] = mapped_column(
        enum_type(TimeEntryKind, "effective_time_adjustment_kind")
    )
    effective_at: Mapped[datetime | None] = mapped_column(DateTime)
    approved_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    integrity_hash: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Timesheet(Base):
    __tablename__ = "timesheets"
    __table_args__ = (
        UniqueConstraint("tenant_id", "employee_id", "competence", "version", name="uq_timesheet_version"),
        Index("ix_timesheet_tenant_status", "tenant_id", "status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id", ondelete="CASCADE"), index=True)
    competence: Mapped[str] = mapped_column(String(7), index=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    supersedes_id: Mapped[int | None] = mapped_column(ForeignKey("timesheets.id", ondelete="RESTRICT"))
    status: Mapped[TimesheetStatus] = mapped_column(
        enum_type(TimesheetStatus, "timesheet_status"), default=TimesheetStatus.open, index=True
    )
    summary: Mapped[dict] = mapped_column(JSON, default=dict)
    integrity_hash: Mapped[str] = mapped_column(String(64), default="")
    calculated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    submitted_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime)
    approved_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime)
    locked_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    locked_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


class PayrollBatch(Base):
    __tablename__ = "payroll_batches"
    __table_args__ = (
        UniqueConstraint("tenant_id", "idempotency_key", name="uq_payroll_batch_idempotency"),
        Index("ix_payroll_batch_tenant_competence", "tenant_id", "competence"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    competence: Mapped[str] = mapped_column(String(7), index=True)
    source: Mapped[str] = mapped_column(String(100))
    idempotency_key: Mapped[str] = mapped_column(String(160))
    status: Mapped[PayrollBatchStatus] = mapped_column(
        enum_type(PayrollBatchStatus, "payroll_batch_status"),
        default=PayrollBatchStatus.uploaded,
        index=True,
    )
    row_count: Mapped[int] = mapped_column(Integer, default=0)
    total_net: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=Decimal("0.00"))
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


class PayrollStatement(Base):
    __tablename__ = "payroll_statements"
    __table_args__ = (
        UniqueConstraint("tenant_id", "batch_id", "employee_id", name="uq_payroll_statement_batch_employee"),
        UniqueConstraint("tenant_id", "storage_key", name="uq_payroll_statement_storage_key"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    batch_id: Mapped[int] = mapped_column(ForeignKey("payroll_batches.id", ondelete="CASCADE"), index=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id", ondelete="CASCADE"), index=True)
    competence: Mapped[str] = mapped_column(String(7), index=True)
    gross_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    deduction_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    net_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    currency: Mapped[str] = mapped_column(String(3), default="BRL")
    filename: Mapped[str] = mapped_column(String(255))
    storage_key: Mapped[str] = mapped_column(String(500))
    checksum: Mapped[str] = mapped_column(String(64))
    published_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
