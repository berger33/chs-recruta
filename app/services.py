from __future__ import annotations

import re
import unicodedata

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from .models import AuditLog, Candidate, CandidateStatus, Vacancy, VacancyStatus

PROFESSION_ALIASES = {
    "fonoaudiologa": "Fonoaudiólogo", "fonoaudiologo": "Fonoaudiólogo",
    "enfermeira": "Enfermeiro", "enfermeiro": "Enfermeiro",
    "psicologa": "Psicólogo", "psicologo": "Psicólogo",
}


def normalize_text(value: str) -> str:
    value = unicodedata.normalize("NFD", value.lower())
    value = "".join(char for char in value if unicodedata.category(char) != "Mn")
    return re.sub(r"[^a-z0-9]+", " ", value).strip()


def normalize_profession(value: str) -> str:
    key = normalize_text(value).replace(" ", "")
    return PROFESSION_ALIASES.get(key, value.strip().title())


def audit(db: Session, *, action: str, entity: str, entity_id: str, actor: str = "system", details: str = "") -> None:
    db.add(AuditLog(action=action, entity=entity, entity_id=entity_id, actor=actor, details=details))


def find_possible_duplicate(db: Session, *, name: str, phone: str = "", registry: str = "") -> Candidate | None:
    normalized_name = normalize_text(name)
    for candidate in db.scalars(select(Candidate)).all():
        same_name = normalize_text(candidate.name) == normalized_name
        same_phone = bool(phone and candidate.phone and normalize_text(candidate.phone) == normalize_text(phone))
        same_registry = bool(registry and candidate.professional_registry and normalize_text(candidate.professional_registry) == normalize_text(registry))
        if same_name and (same_phone or same_registry):
            return candidate
    return None


def search_candidates(db: Session, query: str) -> list[Candidate]:
    query = query.strip()
    if not query:
        return db.scalars(select(Candidate).order_by(Candidate.updated_at.desc())).all()
    like = f"%{query}%"
    return db.scalars(
        select(Candidate)
        .where(or_(Candidate.name.ilike(like), Candidate.profession.ilike(like), Candidate.city.ilike(like), Candidate.phone.ilike(like), Candidate.email.ilike(like)))
        .order_by(Candidate.name)
    ).all()


def dashboard(db: Session) -> dict:
    candidates = db.scalar(select(func.count(Candidate.id))) or 0
    new_candidates = db.scalar(select(func.count(Candidate.id)).where(Candidate.status == CandidateStatus.novo)) or 0
    open_vacancies = db.scalar(select(func.count(Vacancy.id)).where(Vacancy.status == VacancyStatus.aberta)) or 0
    open_positions = db.scalar(select(func.coalesce(func.sum(Vacancy.positions), 0)).where(Vacancy.status == VacancyStatus.aberta)) or 0
    hires = db.scalar(select(func.count(Candidate.id)).where(Candidate.status == CandidateStatus.contratado)) or 0
    status_rows = db.execute(select(Candidate.status, func.count(Candidate.id)).group_by(Candidate.status)).all()
    funnel = {status.value if hasattr(status, "value") else str(status): count for status, count in status_rows}
    return {
        "candidates": candidates,
        "new_candidates": new_candidates,
        "open_vacancies": open_vacancies,
        "open_positions": int(open_positions),
        "hires": hires,
        "conversion_rate": round((hires / candidates * 100) if candidates else 0, 2),
        "funnel": funnel,
    }


def match_vacancies(db: Session, candidate: Candidate) -> list[Vacancy]:
    profession = normalize_profession(candidate.profession)
    vacancies = db.scalars(select(Vacancy).where(Vacancy.status == VacancyStatus.aberta)).all()
    return [vacancy for vacancy in vacancies if normalize_profession(vacancy.profession) == profession]
