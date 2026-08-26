from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Role, User
from ..security import admin_user, hash_password

router = APIRouter(prefix="/api/users", tags=["users"])


class UserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=80)
    display_name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    password: str = Field(min_length=8)
    role: Role = Role.recruiter


@router.get("")
def list_users(db: Session = Depends(get_db), admin: User = Depends(admin_user)):
    users = db.scalars(select(User).order_by(User.username)).all()
    return [{"id": u.id, "username": u.username, "display_name": u.display_name, "email": u.email, "role": u.role.value, "active": u.active} for u in users]


@router.post("", status_code=201)
def create_user(payload: UserCreate, db: Session = Depends(get_db), admin: User = Depends(admin_user)):
    user = User(username=payload.username, display_name=payload.display_name, email=str(payload.email), password_hash=hash_password(payload.password), role=payload.role)
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Usuário ou e-mail já cadastrado")
    db.refresh(user)
    return {"id": user.id, "username": user.username, "display_name": user.display_name, "email": user.email, "role": user.role.value, "active": user.active}
