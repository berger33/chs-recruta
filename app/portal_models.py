from __future__ import annotations

from datetime import date, datetime
from enum import Enum

from sqlalchemy import Date, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base
from .models import enum_type, utcnow


class EmployeeRequestStatus(str, Enum):
    submitted = "submitted"
    in_review = "in_review"
    approved = "approved"
    rejected = "rejected"
    resolved = "resolved"
    cancelled = "cancelled"


class LeaveRequestStatus(str, Enum):
    submitted = "submitted"
    approved = "approved"
    rejected = "rejected"
    cancelled = "cancelled"


class EmployeeFileVisibility(str, Enum):
    employee = "employee"
    hr_only = "hr_only"


class EmployeeRequest(Base):
    __tablename__ = "employee_requests"
    __table_args__ = (Index("ix_employee_request_tenant_status", "tenant_id", "status"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id", ondelete="CASCADE"), index=True)
    category: Mapped[str] = mapped_column(String(80), index=True)
    subject: Mapped[str] = mapped_column(String(180))
    description: Mapped[str] = mapped_column(Text, default="")
    priority: Mapped[str] = mapped_column(String(20), default="normal")
    status: Mapped[EmployeeRequestStatus] = mapped_column(
        enum_type(EmployeeRequestStatus, "employee_request_status"),
        default=EmployeeRequestStatus.submitted,
        index=True,
    )
    assigned_to_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    decided_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    resolution: Mapped[str] = mapped_column(Text, default="")
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


class LeaveRequest(Base):
    __tablename__ = "leave_requests"
    __table_args__ = (Index("ix_leave_request_tenant_period", "tenant_id", "start_date", "end_date"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id", ondelete="CASCADE"), index=True)
    leave_type: Mapped[str] = mapped_column(String(60), index=True)
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date] = mapped_column(Date)
    total_days: Mapped[int] = mapped_column(Integer)
    reason: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[LeaveRequestStatus] = mapped_column(
        enum_type(LeaveRequestStatus, "leave_request_status"),
        default=LeaveRequestStatus.submitted,
        index=True,
    )
    decided_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    decision_notes: Mapped[str] = mapped_column(Text, default="")
    decided_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


class EmployeeFile(Base):
    __tablename__ = "employee_files"
    __table_args__ = (
        UniqueConstraint("tenant_id", "storage_key", name="uq_employee_file_storage_key"),
        Index("ix_employee_file_tenant_employee", "tenant_id", "employee_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id", ondelete="CASCADE"), index=True)
    category: Mapped[str] = mapped_column(String(80), index=True)
    filename: Mapped[str] = mapped_column(String(255))
    storage_key: Mapped[str] = mapped_column(String(500))
    checksum: Mapped[str] = mapped_column(String(64))
    mime_type: Mapped[str] = mapped_column(String(120), default="application/octet-stream")
    visibility: Mapped[EmployeeFileVisibility] = mapped_column(
        enum_type(EmployeeFileVisibility, "employee_file_visibility"),
        default=EmployeeFileVisibility.employee,
    )
    expires_on: Mapped[date | None] = mapped_column(Date)
    uploaded_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

