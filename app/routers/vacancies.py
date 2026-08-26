from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import User, Vacancy
from ..schemas import VacancyCreate, VacancyRead
from ..security import current_user
from ..services import audit, normalize_profession

router = APIRouter(prefix="/api/vacancies", tags=["vacancies"])


@router.get("", response_model=list[VacancyRead])
def list_vacancies(db: Session = Depends(get_db), user: User = Depends(current_user)):
    return db.scalars(select(Vacancy).order_by(Vacancy.created_at.desc())).all()


@router.post("", response_model=VacancyRead, status_code=201)
def create_vacancy(payload: VacancyCreate, db: Session = Depends(get_db), user: User = Depends(current_user)):
    data = payload.model_dump()
    data["profession"] = normalize_profession(data["profession"])
    vacancy = Vacancy(**data)
    db.add(vacancy)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Código de vaga já existe")
    audit(db, action="create", entity="vacancy", entity_id=str(vacancy.id), actor=user.username, details=vacancy.code)
    db.commit()
    db.refresh(vacancy)
    return vacancy


@router.get("/{vacancy_id}", response_model=VacancyRead)
def get_vacancy(vacancy_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    vacancy = db.get(Vacancy, vacancy_id)
    if not vacancy:
        raise HTTPException(status_code=404, detail="Vaga não encontrada")
    return vacancy
