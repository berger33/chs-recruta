from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Candidate, User
from ..schemas import CandidateCreate, CandidateRead
from ..security import admin_user, current_user
from ..services import audit, find_possible_duplicate, normalize_profession, search_candidates

router = APIRouter(prefix="/api/candidates", tags=["candidates"])


@router.get("", response_model=list[CandidateRead])
def list_candidates(q: str = Query(default=""), db: Session = Depends(get_db), user: User = Depends(current_user)):
    return search_candidates(db, q)


@router.post("", response_model=CandidateRead, status_code=201)
def create_candidate(payload: CandidateCreate, db: Session = Depends(get_db), user: User = Depends(current_user)):
    duplicate = find_possible_duplicate(db, name=payload.name, phone=payload.phone, registry=payload.professional_registry)
    if duplicate:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Possível duplicidade com candidato #{duplicate.id}")
    data = payload.model_dump()
    data["profession"] = normalize_profession(data["profession"])
    candidate = Candidate(**data)
    db.add(candidate)
    db.flush()
    audit(db, action="create", entity="candidate", entity_id=str(candidate.id), actor=user.username, details=candidate.name)
    db.commit()
    db.refresh(candidate)
    return candidate


@router.get("/{candidate_id}", response_model=CandidateRead)
def get_candidate(candidate_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    candidate = db.get(Candidate, candidate_id)
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidato não encontrado")
    return candidate


@router.put("/{candidate_id}", response_model=CandidateRead)
def update_candidate(candidate_id: int, payload: CandidateCreate, db: Session = Depends(get_db), user: User = Depends(current_user)):
    candidate = db.get(Candidate, candidate_id)
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidato não encontrado")
    data = payload.model_dump()
    data["profession"] = normalize_profession(data["profession"])
    for key, value in data.items():
        setattr(candidate, key, value)
    audit(db, action="update", entity="candidate", entity_id=str(candidate.id), actor=user.username, details=candidate.name)
    db.commit()
    db.refresh(candidate)
    return candidate


@router.delete("/{candidate_id}", status_code=204)
def delete_candidate(candidate_id: int, db: Session = Depends(get_db), user: User = Depends(admin_user)):
    candidate = db.get(Candidate, candidate_id)
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidato não encontrado")
    audit(db, action="delete", entity="candidate", entity_id=str(candidate.id), actor=user.username, details=candidate.name)
    db.delete(candidate)
    db.commit()
    return None
