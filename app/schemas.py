from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel, ConfigDict, EmailStr, Field

from .models import CandidateStatus, VacancyStatus


class CandidateCreate(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    profession: str = Field(min_length=2, max_length=120)
    city: str = ""
    professional_registry: str = ""
    phone: str = ""
    email: EmailStr | str = ""
    source: str = ""
    source_url: str = ""
    recruiter: str = ""
    status: CandidateStatus = CandidateStatus.novo
    notes: str = ""
    vacancy_id: int | None = None


class CandidateRead(CandidateCreate):
    model_config = ConfigDict(from_attributes=True)
    id: int
    created_at: datetime
    updated_at: datetime


class VacancyCreate(BaseModel):
    code: str = Field(min_length=2, max_length=40)
    title: str = Field(min_length=2, max_length=160)
    profession: str = Field(min_length=2, max_length=120)
    city: str = ""
    positions: int = Field(default=1, ge=1, le=1000)
    status: VacancyStatus = VacancyStatus.aberta
    owner: str = ""


class VacancyRead(VacancyCreate):
    model_config = ConfigDict(from_attributes=True)
    id: int
    created_at: datetime


class DashboardRead(BaseModel):
    candidates: int
    new_candidates: int
    open_vacancies: int
    open_positions: int
    hires: int
    conversion_rate: float
    funnel: dict[str, int]


class FinancialCreate(BaseModel):
    service: str = Field(min_length=2, max_length=160)
    current_value: float = Field(ge=0)
    max_value: float = Field(ge=0)


class FinancialRead(FinancialCreate):
    model_config = ConfigDict(from_attributes=True)
    id: int
