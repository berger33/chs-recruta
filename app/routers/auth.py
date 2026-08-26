from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import User
from ..security import bearer, current_user, issue_session, revoke_session, verify_password

router = APIRouter(prefix="/api/auth", tags=["auth"])


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    token: str
    token_type: str = "bearer"
    username: str
    display_name: str
    role: str


@router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.username == payload.username))
    if not user or not user.active or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Credenciais inválidas")
    token = issue_session(db, user)
    return LoginResponse(token=token, username=user.username, display_name=user.display_name, role=user.role.value)


@router.get("/me")
def me(user: User = Depends(current_user)):
    return {"id": user.id, "username": user.username, "display_name": user.display_name, "email": user.email, "role": user.role.value}


@router.post("/logout", status_code=204)
def logout(credentials=Depends(bearer), db: Session = Depends(get_db)):
    if credentials:
        revoke_session(db, credentials.credentials)
    return None
