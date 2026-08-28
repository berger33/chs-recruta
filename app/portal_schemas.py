from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .portal_models import EmployeeFileVisibility, EmployeeRequestStatus, LeaveRequestStatus


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class EmployeeRequestCreate(BaseModel):
    employee_id: int | None = None
    category: str = Field(min_length=2, max_length=80)
    subject: str = Field(min_length=3, max_length=180)
    description: str = Field(default="", max_length=10_000)
    priority: str = Field(default="normal", pattern=r"^(low|normal|high|urgent)$")


class EmployeeRequestTransition(BaseModel):
    status: EmployeeRequestStatus
    resolution: str = Field(default="", max_length=10_000)
    assigned_to_id: int | None = None


class EmployeeRequestRead(EmployeeRequestCreate, ORMModel):
    id: int
    employee_id: int
    status: EmployeeRequestStatus
    assigned_to_id: int | None
    decided_by_id: int | None
    resolution: str
    resolved_at: datetime | None
    created_at: datetime
    updated_at: datetime


class LeaveRequestCreate(BaseModel):
    employee_id: int | None = None
    leave_type: str = Field(min_length=2, max_length=60)
    start_date: date
    end_date: date
    reason: str = Field(default="", max_length=10_000)

    @model_validator(mode="after")
    def valid_period(self):
        if self.end_date < self.start_date:
            raise ValueError("A data final deve ser igual ou posterior à data inicial")
        if (self.end_date - self.start_date).days > 365:
            raise ValueError("O período não pode ultrapassar 366 dias")
        return self


class LeaveRequestTransition(BaseModel):
    status: LeaveRequestStatus
    decision_notes: str = Field(default="", max_length=10_000)


class LeaveRequestRead(LeaveRequestCreate, ORMModel):
    id: int
    employee_id: int
    total_days: int
    status: LeaveRequestStatus
    decided_by_id: int | None
    decision_notes: str
    decided_at: datetime | None
    created_at: datetime
    updated_at: datetime


class EmployeeFileCreate(BaseModel):
    employee_id: int
    category: str = Field(min_length=2, max_length=80)
    filename: str = Field(min_length=1, max_length=255)
    storage_key: str = Field(min_length=3, max_length=500)
    checksum: str = Field(min_length=64, max_length=64, pattern=r"^[a-fA-F0-9]+$")
    mime_type: str = Field(default="application/octet-stream", max_length=120)
    visibility: EmployeeFileVisibility = EmployeeFileVisibility.employee
    expires_on: date | None = None


class EmployeeFileRead(EmployeeFileCreate, ORMModel):
    id: int
    uploaded_by_id: int | None
    created_at: datetime


class PortalSummary(BaseModel):
    employee_id: int | None
    employee_name: str | None
    open_requests: int
    pending_leave_requests: int
    available_files: int
