from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .models import TimeEntryKind
from .time_payroll_models import (
    PayrollBatchStatus,
    TimeAdjustmentAction,
    TimeAdjustmentStatus,
    TimesheetStatus,
)


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class WorkScheduleCreate(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    timezone: str = Field(default="America/Sao_Paulo", min_length=3, max_length=64)
    weekly_minutes: int = Field(default=2640, ge=1, le=10_080)
    break_minutes: int = Field(default=60, ge=0, le=1_440)
    tolerance_minutes: int = Field(default=10, ge=0, le=240)
    active: bool = True


class WorkScheduleRead(WorkScheduleCreate, ORMModel):
    id: int
    created_at: datetime
    updated_at: datetime


class EmployeeScheduleCreate(BaseModel):
    employee_id: int
    schedule_id: int
    effective_from: date
    effective_to: date | None = None

    @model_validator(mode="after")
    def valid_period(self):
        if self.effective_to and self.effective_to < self.effective_from:
            raise ValueError("Fim da escala deve ser posterior ao início")
        return self


class EmployeeScheduleRead(EmployeeScheduleCreate, ORMModel):
    id: int
    created_by_id: int | None
    created_at: datetime


class TimeAdjustmentRequestCreate(BaseModel):
    action: TimeAdjustmentAction
    original_entry_id: int | None = None
    requested_kind: TimeEntryKind | None = None
    requested_at: datetime | None = None
    reason: str = Field(min_length=5, max_length=10_000)

    @field_validator("requested_at")
    @classmethod
    def normalize_requested_at(cls, value: datetime | None) -> datetime | None:
        if value is not None and value.tzinfo is not None:
            return value.astimezone(UTC).replace(tzinfo=None)
        return value

    @model_validator(mode="after")
    def valid_action(self):
        if self.action == TimeAdjustmentAction.add and (
            self.original_entry_id is not None or self.requested_kind is None or self.requested_at is None
        ):
            raise ValueError("Inclusão exige tipo e horário, sem marcação original")
        if self.action == TimeAdjustmentAction.replace and (
            self.original_entry_id is None or self.requested_kind is None or self.requested_at is None
        ):
            raise ValueError("Substituição exige marcação original, tipo e horário")
        if self.action == TimeAdjustmentAction.void and (
            self.original_entry_id is None or self.requested_kind is not None or self.requested_at is not None
        ):
            raise ValueError("Anulação exige somente a marcação original")
        return self


class TimeAdjustmentDecision(BaseModel):
    approved: bool
    review_notes: str = Field(default="", max_length=10_000)


class TimeAdjustmentRequestRead(TimeAdjustmentRequestCreate, ORMModel):
    id: int
    employee_id: int
    status: TimeAdjustmentStatus
    reviewed_by_id: int | None
    review_notes: str
    reviewed_at: datetime | None
    created_at: datetime
    updated_at: datetime


class EffectiveTimeEntry(BaseModel):
    source_type: str
    source_id: int
    original_entry_id: int | None
    kind: TimeEntryKind
    recorded_at: datetime
    integrity_hash: str


class TimesheetCalculate(BaseModel):
    employee_id: int
    competence: str = Field(pattern=r"^\d{4}-(0[1-9]|1[0-2])$")


class TimesheetTransition(BaseModel):
    status: TimesheetStatus


class TimesheetRead(ORMModel):
    id: int
    employee_id: int
    competence: str
    version: int
    supersedes_id: int | None
    status: TimesheetStatus
    summary: dict
    integrity_hash: str
    calculated_at: datetime
    submitted_at: datetime | None
    approved_at: datetime | None
    locked_at: datetime | None
    created_at: datetime
    updated_at: datetime


class PayrollRowCreate(BaseModel):
    employee_number: str = Field(min_length=1, max_length=40)
    gross_amount: Decimal = Field(ge=0)
    deduction_amount: Decimal = Field(ge=0)
    net_amount: Decimal = Field(ge=0)
    currency: str = Field(default="BRL", pattern=r"^[A-Z]{3}$")
    filename: str = Field(min_length=1, max_length=255)
    storage_key: str = Field(min_length=3, max_length=500)
    checksum: str = Field(min_length=64, max_length=64, pattern=r"^[a-fA-F0-9]+$")

    @model_validator(mode="after")
    def totals_reconcile(self):
        if (self.gross_amount - self.deduction_amount).quantize(Decimal("0.01")) != self.net_amount.quantize(Decimal("0.01")):
            raise ValueError("Líquido deve ser igual a bruto menos descontos")
        return self


class PayrollBatchCreate(BaseModel):
    competence: str = Field(pattern=r"^\d{4}-(0[1-9]|1[0-2])$")
    source: str = Field(min_length=2, max_length=100)
    idempotency_key: str = Field(min_length=8, max_length=160)
    rows: list[PayrollRowCreate] = Field(min_length=1, max_length=10_000)

    @model_validator(mode="after")
    def unique_employees(self):
        numbers = [row.employee_number for row in self.rows]
        if len(numbers) != len(set(numbers)):
            raise ValueError("O lote contém matrícula duplicada")
        return self


class PayrollBatchTransition(BaseModel):
    status: PayrollBatchStatus


class PayrollBatchRead(ORMModel):
    id: int
    competence: str
    source: str
    idempotency_key: str
    status: PayrollBatchStatus
    row_count: int
    total_net: Decimal
    created_at: datetime
    updated_at: datetime


class PayrollStatementRead(ORMModel):
    id: int
    batch_id: int
    employee_id: int
    competence: str
    gross_amount: Decimal
    deduction_amount: Decimal
    net_amount: Decimal
    currency: str
    filename: str
    storage_key: str
    checksum: str
    published_at: datetime | None
    created_at: datetime
