from __future__ import annotations

import hashlib
import hmac
import os
import secrets
from datetime import UTC, datetime, timedelta

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from .database import get_db
from .models import Role, SessionToken, User

PBKDF2_ITERATIONS = 310_000
TOKEN_TTL_HOURS = int(os.getenv("SESSION_TTL_HOURS", "12"))
bearer = HTTPBearer(auto_error=False)


def _utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def hash_password(password: str, salt: bytes | None = None) -> str:
    if len(password) < 8:
        raise ValueError("A senha deve ter pelo menos 8 caracteres.")
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, PBKDF2_ITERATIONS)
    return f"pbkdf2_sha256${PBKDF2_ITERATIONS}${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algorithm, iterations, salt_hex, digest_hex = stored.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        digest = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt_hex), int(iterations))
        return hmac.compare_digest(digest.hex(), digest_hex)
    except (ValueError, TypeError):
        return False


def issue_session(db: Session, user: User) -> str:
    raw = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(raw.encode()).hexdigest()
    db.add(SessionToken(token_hash=token_hash, user_id=user.id, expires_at=_utcnow() + timedelta(hours=TOKEN_TTL_HOURS)))
    db.commit()
    return raw


def revoke_session(db: Session, raw: str) -> None:
    token_hash = hashlib.sha256(raw.encode()).hexdigest()
    token = db.scalar(select(SessionToken).where(SessionToken.token_hash == token_hash))
    if token:
        db.delete(token)
        db.commit()


def current_user(credentials: HTTPAuthorizationCredentials | None = Depends(bearer), db: Session = Depends(get_db)) -> User:
    if not credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Autenticação necessária")
    token_hash = hashlib.sha256(credentials.credentials.encode()).hexdigest()
    token = db.scalar(select(SessionToken).where(SessionToken.token_hash == token_hash))
    if not token or token.expires_at <= _utcnow():
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Sessão inválida ou expirada")
    user = db.get(User, token.user_id)
    if not user or not user.active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Usuário inativo")
    return user


def admin_user(user: User = Depends(current_user)) -> User:
    if user.role != Role.admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acesso restrito ao administrador")
    return user
