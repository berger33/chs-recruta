from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum

from sqlalchemy import Boolean, DateTime, Enum as SAEnum, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class Role(str, Enum):
    admin = "admin"
    recruiter = "recruiter"


class CandidateStatus(str, Enum):
    novo = "Novo"
    em_contato = "Em Contato"
    contatado = "Contatado"
    sem_resposta = "Sem resposta"
    respondeu = "Respondeu"
    entrevista_marcada = "Entrevista marcada"
    entrevistado = "Entrevistado"
    contratado = "Contratado"
    banco_talentos = "Banco de Talentos"
    nao_interessado = "Não interessado"


class VacancyStatus(str, Enum):
    aberta = "aberta"
    pausada = "pausada"
    fechada = "fechada"
    cancelada = "cancelada"


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(160), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[Role] = mapped_column(SAEnum(Role), default=Role.recruiter)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Candidate(Base):
    __tablename__ = "candidates"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(160), index=True)
    profession: Mapped[str] = mapped_column(String(120), index=True)
    city: Mapped[str] = mapped_column(String(120), default="")
    professional_registry: Mapped[str] = mapped_column(String(80), default="")
    phone: Mapped[str] = mapped_column(String(40), default="", index=True)
    email: Mapped[str] = mapped_column(String(160), default="")
    source: Mapped[str] = mapped_column(String(120), default="")
    source_url: Mapped[str] = mapped_column(String(500), default="")
    recruiter: Mapped[str] = mapped_column(String(120), default="")
    status: Mapped[CandidateStatus] = mapped_column(SAEnum(CandidateStatus), default=CandidateStatus.novo, index=True)
    notes: Mapped[str] = mapped_column(Text, default="")
    vacancy_id: Mapped[int | None] = mapped_column(ForeignKey("vacancies.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)
    vacancy: Mapped["Vacancy | None"] = relationship(back_populates="candidates")


class Vacancy(Base):
    __tablename__ = "vacancies"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(160))
    profession: Mapped[str] = mapped_column(String(120), index=True)
    city: Mapped[str] = mapped_column(String(120), default="")
    positions: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[VacancyStatus] = mapped_column(SAEnum(VacancyStatus), default=VacancyStatus.aberta, index=True)
    owner: Mapped[str] = mapped_column(String(120), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    candidates: Mapped[list[Candidate]] = relationship(back_populates="vacancy")


class FinancialReference(Base):
    __tablename__ = "financial_references"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    service: Mapped[str] = mapped_column(String(160), unique=True)
    current_value: Mapped[float] = mapped_column(Float, default=0)
    max_value: Mapped[float] = mapped_column(Float, default=0)


class AuditLog(Base):
    __tablename__ = "audit_logs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    action: Mapped[str] = mapped_column(String(80), index=True)
    entity: Mapped[str] = mapped_column(String(80), index=True)
    entity_id: Mapped[str] = mapped_column(String(80), default="")
    actor: Mapped[str] = mapped_column(String(120), default="system")
    details: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)


class SessionToken(Base):
    __tablename__ = "session_tokens"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    user: Mapped[User] = relationship()
