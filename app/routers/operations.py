from __future__ import annotations

import csv
import io

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import AuditLog, Candidate, FinancialReference, User
from ..schemas import DashboardRead, FinancialCreate, FinancialRead, VacancyRead
from ..security import current_user
from ..services import dashboard, match_vacancies

router = APIRouter(prefix="/api", tags=["operations"])


@router.get("/dashboard", response_model=DashboardRead)
def dashboard_endpoint(db: Session = Depends(get_db), user: User = Depends(current_user)):
    return dashboard(db)


@router.get("/candidates/{candidate_id}/matches", response_model=list[VacancyRead])
def candidate_matches(candidate_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    candidate = db.get(Candidate, candidate_id)
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidato não encontrado")
    return match_vacancies(db, candidate)


@router.get("/financial", response_model=list[FinancialRead])
def list_financial(db: Session = Depends(get_db), user: User = Depends(current_user)):
    return db.scalars(select(FinancialReference).order_by(FinancialReference.service)).all()


@router.post("/financial", response_model=FinancialRead, status_code=201)
def create_financial(payload: FinancialCreate, db: Session = Depends(get_db), user: User = Depends(current_user)):
    item = FinancialReference(**payload.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.get("/audit")
def list_audit(db: Session = Depends(get_db), user: User = Depends(current_user)):
    return db.scalars(select(AuditLog).order_by(AuditLog.created_at.desc()).limit(200)).all()


@router.get("/export/candidates.csv")
def export_candidates(db: Session = Depends(get_db), user: User = Depends(current_user)):
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["id", "name", "profession", "city", "phone", "email", "status", "recruiter"])
    for candidate in db.scalars(select(Candidate).order_by(Candidate.name)).all():
        writer.writerow([candidate.id, candidate.name, candidate.profession, candidate.city, candidate.phone, candidate.email, candidate.status.value, candidate.recruiter])
    payload = "\ufeff" + output.getvalue()
    return StreamingResponse(iter([payload]), media_type="text/csv; charset=utf-8", headers={"Content-Disposition": "attachment; filename=chs-candidates.csv"})
