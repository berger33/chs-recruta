from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Annotated

import pyotp
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError
from cryptography.fernet import Fernet, InvalidToken
from fastapi import Depends, HTTPException, Request, Response, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from .config import get_settings
from .database import activate_tenant_scope, get_db
from .identity_models import (
    PrivilegedAccessGrant,
    PrivilegedAccessStatus,
    SecurityEvent,
    SecurityRateEvent,
    UserMfa,
)
from .models import Membership, SessionToken, Tenant, User
from .permissions import Permission, permissions_for_role


PBKDF2_ITERATIONS = 600_000
MIN_PASSWORD_LENGTH = 15
PASSWORD_BLOCKLIST = frozenset(
    {
        "123456789012345",
        "administrador123",
        "chsrecruta12345",
        "passwordpassword",
        "qwertyuiop12345",
        "senhasenhasenha",
        "senha123456789",
    }
)
PASSWORD_HASHER = PasswordHasher(
    time_cost=3,
    memory_cost=65_536,
    parallelism=4,
    hash_len=32,
    salt_len=16,
)
bearer = HTTPBearer(auto_error=False)


def utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def client_ip(request: Request) -> str:
    return request.client.host[:64] if request.client and request.client.host else "unknown"


def client_metadata(request: Request) -> tuple[str, str, str]:
    ip_address = client_ip(request)
    user_agent = request.headers.get("user-agent", "")[:500]
    lowered = user_agent.lower()
    if "mobile" in lowered:
        device = "Dispositivo móvel"
    elif user_agent:
        device = "Navegador web"
    else:
        device = "Cliente de API"
    return ip_address, user_agent, device


def validate_password(password: str, user: User | None = None) -> None:
    normalized = password.casefold().strip()
    if len(password) < MIN_PASSWORD_LENGTH:
        raise ValueError(f"A senha deve ter pelo menos {MIN_PASSWORD_LENGTH} caracteres")
    if len(password) > 256:
        raise ValueError("A senha deve ter no máximo 256 caracteres")
    if normalized in PASSWORD_BLOCKLIST:
        raise ValueError("Escolha uma senha que não esteja na lista de senhas comuns")
    if user:
        personal = {
            user.username.casefold(),
            user.email.split("@", 1)[0].casefold(),
            *(part.casefold() for part in user.display_name.split() if len(part) >= 3),
        }
        if any(value and value in normalized for value in personal):
            raise ValueError("A senha não deve conter seu usuário ou e-mail")


def hash_password(password: str, salt: bytes | None = None) -> str:
    del salt  # Compatibilidade com a assinatura anterior; Argon2id gera o próprio salt.
    validate_password(password)
    return PASSWORD_HASHER.hash(password)


def _verify_legacy_pbkdf2(password: str, stored: str) -> bool:
    try:
        algorithm, iterations, salt_hex, digest_hex = stored.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        digest = hashlib.pbkdf2_hmac(
            "sha256", password.encode(), bytes.fromhex(salt_hex), int(iterations)
        )
        return hmac.compare_digest(digest.hex(), digest_hex)
    except (ValueError, TypeError):
        return False


def verify_password(password: str, stored: str) -> bool:
    if stored.startswith("pbkdf2_sha256$"):
        return _verify_legacy_pbkdf2(password, stored)
    try:
        return PASSWORD_HASHER.verify(stored, password)
    except (VerifyMismatchError, InvalidHashError, TypeError):
        return False


def password_needs_rehash(stored: str) -> bool:
    if stored.startswith("pbkdf2_sha256$"):
        return True
    try:
        return PASSWORD_HASHER.check_needs_rehash(stored)
    except InvalidHashError:
        return True


def rehash_verified_password(password: str) -> str:
    """Upgrade de hash após a senha antiga já ter sido validada com sucesso."""
    return PASSWORD_HASHER.hash(password)


def _fernet() -> Fernet:
    digest = hashlib.sha256(get_settings().security_secret_key.encode()).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def encrypt_secret(value: str) -> str:
    return _fernet().encrypt(value.encode()).decode()


def decrypt_secret(value: str) -> str:
    try:
        return _fernet().decrypt(value.encode()).decode()
    except InvalidToken as error:
        raise HTTPException(500, "Não foi possível acessar o segredo MFA") from error


def recovery_code_hash(code: str) -> str:
    return hmac.new(
        get_settings().security_secret_key.encode(),
        code.replace("-", "").strip().upper().encode(),
        hashlib.sha256,
    ).hexdigest()


def generate_recovery_codes() -> tuple[list[str], list[str]]:
    plain = [f"{secrets.token_hex(4).upper()}-{secrets.token_hex(4).upper()}" for _ in range(10)]
    return plain, [recovery_code_hash(code) for code in plain]


def verify_totp(credential: UserMfa, code: str, *, consume: bool = True) -> bool:
    digits = code.replace(" ", "").strip()
    if not digits.isdigit() or len(digits) != 6:
        return False
    totp = pyotp.TOTP(decrypt_secret(credential.secret_ciphertext))
    current = datetime.now(UTC)
    for offset in (-1, 0, 1):
        candidate_time = current + timedelta(seconds=offset * totp.interval)
        if hmac.compare_digest(totp.at(candidate_time), digits):
            step = int(candidate_time.timestamp()) // totp.interval
            if credential.last_used_step is not None and step <= credential.last_used_step:
                return False
            if consume:
                credential.last_used_step = step
            return True
    return False


def verify_mfa_or_recovery(credential: UserMfa, code: str) -> tuple[bool, bool]:
    if verify_totp(credential, code):
        return True, False
    candidate = recovery_code_hash(code)
    if candidate not in credential.recovery_code_hashes:
        return False, False
    credential.recovery_code_hashes = [
        item for item in credential.recovery_code_hashes if not hmac.compare_digest(item, candidate)
    ]
    return True, True


def rate_key(value: str) -> str:
    return hmac.new(
        get_settings().security_secret_key.encode(), value.casefold().encode(), hashlib.sha256
    ).hexdigest()


def consume_rate_limit(
    db: Session,
    *,
    scope: str,
    key: str,
    limit: int,
    window: timedelta,
    commit_event: bool = True,
) -> None:
    cutoff = utcnow() - window
    key_digest = rate_key(key)
    attempts = db.scalar(
        select(func.count(SecurityRateEvent.id)).where(
            SecurityRateEvent.scope == scope,
            SecurityRateEvent.key_hash == key_digest,
            SecurityRateEvent.created_at >= cutoff,
        )
    )
    if int(attempts or 0) >= limit:
        retry_after = max(1, int(window.total_seconds()))
        raise HTTPException(
            status_code=429,
            detail="Muitas tentativas. Aguarde antes de tentar novamente",
            headers={"Retry-After": str(retry_after)},
        )
    db.add(SecurityRateEvent(scope=scope, key_hash=key_digest))
    if commit_event:
        db.commit()


def record_security_event(
    db: Session,
    request: Request,
    *,
    event_type: str,
    outcome: str,
    user_id: int | None = None,
    tenant_id: int | None = None,
    details: dict | None = None,
    commit: bool = False,
) -> SecurityEvent:
    ip_address, user_agent, _ = client_metadata(request)
    item = SecurityEvent(
        tenant_id=tenant_id,
        user_id=user_id,
        event_type=event_type,
        outcome=outcome,
        ip_address=ip_address,
        user_agent=user_agent,
        request_id=getattr(request.state, "request_id", ""),
        details=details or {},
    )
    db.add(item)
    if commit:
        db.commit()
    return item


@dataclass(frozen=True, slots=True)
class AuthContext:
    user: User
    membership: Membership
    tenant: Tenant
    session: SessionToken
    privileged_permissions: frozenset[Permission] = frozenset()

    @property
    def tenant_id(self) -> int:
        return self.tenant.id

    @property
    def permissions(self) -> frozenset[Permission]:
        return permissions_for_role(self.membership.role.value) | self.privileged_permissions

    def has_recent_mfa(self, minutes: int = 10) -> bool:
        return bool(
            self.session.mfa_verified
            and self.session.authenticated_at >= utcnow() - timedelta(minutes=minutes)
        )


def find_user(db: Session, identifier: str) -> User | None:
    value = identifier.strip().lower()
    return db.scalar(select(User).where(or_(User.username == value, User.email == value)))


def active_memberships(db: Session, user_id: int) -> list[Membership]:
    return list(
        db.scalars(
            select(Membership)
            .join(Tenant, Tenant.id == Membership.tenant_id)
            .where(
                Membership.user_id == user_id,
                Membership.active.is_(True),
                Tenant.active.is_(True),
            )
            .order_by(Tenant.name)
        ).all()
    )


def issue_session(
    db: Session,
    user: User,
    membership: Membership,
    *,
    request: Request | None = None,
    mfa_verified: bool = False,
    privileged_grant_id: int | None = None,
    expires_at: datetime | None = None,
    commit: bool = True,
) -> str:
    raw = secrets.token_urlsafe(48)
    ip_address, user_agent, device_name = (
        client_metadata(request) if request else ("", "", "Cliente de API")
    )
    current = utcnow()
    absolute_expiry = current + timedelta(hours=get_settings().session_ttl_hours)
    if expires_at and expires_at < absolute_expiry:
        absolute_expiry = expires_at
    item = SessionToken(
        token_hash=hashlib.sha256(raw.encode()).hexdigest(),
        user_id=user.id,
        membership_id=membership.id,
        tenant_id=membership.tenant_id,
        expires_at=absolute_expiry,
        ip_address=ip_address,
        user_agent=user_agent,
        device_name=device_name,
        mfa_verified=mfa_verified,
        authenticated_at=current,
        privileged_grant_id=privileged_grant_id,
    )
    db.add(item)
    db.flush()
    active = db.scalars(
        select(SessionToken)
        .where(
            SessionToken.user_id == user.id,
            SessionToken.revoked_at.is_(None),
            SessionToken.expires_at > current,
        )
        .order_by(SessionToken.created_at.desc())
    ).all()
    for stale in active[get_settings().max_active_sessions :]:
        stale.revoked_at = current
        stale.revoke_reason = "Limite de sessões ativas"
    if commit:
        db.commit()
    return raw


def revoke_session(
    db: Session, raw: str, reason: str = "Logout", *, commit: bool = True
) -> SessionToken | None:
    token = db.scalar(
        select(SessionToken).where(
            SessionToken.token_hash == hashlib.sha256(raw.encode()).hexdigest()
        )
    )
    if token and token.revoked_at is None:
        token.revoked_at = utcnow()
        token.revoke_reason = reason[:160]
        if commit:
            db.commit()
    return token


def revoke_all_user_sessions(
    db: Session, user_id: int, reason: str, *, except_session_id: int | None = None
) -> int:
    statement = select(SessionToken).where(
        SessionToken.user_id == user_id,
        SessionToken.revoked_at.is_(None),
    )
    if except_session_id is not None:
        statement = statement.where(SessionToken.id != except_session_id)
    items = db.scalars(statement).all()
    current = utcnow()
    for item in items:
        item.revoked_at = current
        item.revoke_reason = reason[:160]
    return len(items)


def _privileged_permissions(db: Session, token: SessionToken) -> frozenset[Permission]:
    if token.privileged_grant_id is None:
        return frozenset()
    grant = db.scalar(
        select(PrivilegedAccessGrant).where(
            PrivilegedAccessGrant.id == token.privileged_grant_id,
            PrivilegedAccessGrant.tenant_id == token.tenant_id,
            PrivilegedAccessGrant.membership_id == token.membership_id,
        )
    )
    if (
        not grant
        or grant.status != PrivilegedAccessStatus.approved
        or grant.expires_at is None
        or grant.expires_at <= utcnow()
    ):
        token.revoked_at = utcnow()
        token.revoke_reason = "Acesso privilegiado expirado ou revogado"
        db.commit()
        raise HTTPException(401, "Sessão privilegiada expirada")
    return frozenset(Permission(value) for value in grant.requested_permissions)


def context_from_token(db: Session, raw: str) -> AuthContext:
    token = db.scalar(
        select(SessionToken).where(
            SessionToken.token_hash == hashlib.sha256(raw.encode()).hexdigest()
        )
    )
    current = utcnow()
    if (
        not token
        or token.revoked_at is not None
        or token.expires_at <= current
        or token.last_seen_at < current - timedelta(minutes=get_settings().session_idle_minutes)
    ):
        if token and token.revoked_at is None:
            token.revoked_at = current
            token.revoke_reason = "Sessão expirada por tempo ou inatividade"
            db.commit()
        raise HTTPException(401, "Sessão inválida ou expirada")
    user = db.get(User, token.user_id)
    membership = db.get(Membership, token.membership_id)
    tenant = db.get(Tenant, token.tenant_id)
    if not user or not user.active or not membership or not membership.active or not tenant or not tenant.active:
        raise HTTPException(401, "Acesso inativo")
    if membership.user_id != user.id or membership.tenant_id != tenant.id:
        raise HTTPException(401, "Sessão inconsistente")
    activate_tenant_scope(db, tenant.id)
    elevated = _privileged_permissions(db, token)
    if token.last_seen_at < current - timedelta(minutes=5):
        token.last_seen_at = current
        db.commit()
        activate_tenant_scope(db, tenant.id)
    return AuthContext(user, membership, tenant, token, elevated)


def session_token_from_request(
    request: Request, credentials: HTTPAuthorizationCredentials | None
) -> str | None:
    if credentials:
        return credentials.credentials
    return request.cookies.get(get_settings().session_cookie_name)


def current_context(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
    db: Annotated[Session, Depends(get_db)],
) -> AuthContext:
    raw = session_token_from_request(request, credentials)
    if not raw:
        raise HTTPException(401, "Autenticação necessária")
    return context_from_token(db, raw)


def require_recent_mfa(context: AuthContext, minutes: int = 10) -> None:
    if not context.has_recent_mfa(minutes):
        raise HTTPException(403, "Confirme novamente sua senha e MFA para esta operação")


def attach_session_cookies(response: Response, raw: str) -> None:
    settings = get_settings()
    csrf = secrets.token_urlsafe(32)
    response.set_cookie(
        settings.session_cookie_name,
        raw,
        httponly=True,
        secure=settings.is_production,
        samesite="strict",
        path="/",
        max_age=settings.session_ttl_hours * 3600,
    )
    response.set_cookie(
        "chs_csrf",
        csrf,
        httponly=False,
        secure=settings.is_production,
        samesite="strict",
        path="/",
        max_age=settings.session_ttl_hours * 3600,
    )


def clear_session_cookies(response: Response) -> None:
    settings = get_settings()
    response.delete_cookie(settings.session_cookie_name, path="/")
    response.delete_cookie("chs_csrf", path="/")


def require_permissions(*required: Permission):
    def dependency(context: Annotated[AuthContext, Depends(current_context)]) -> AuthContext:
        missing = set(required) - context.permissions
        if missing:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                {
                    "message": "Permissão insuficiente",
                    "missing": sorted(item.value for item in missing),
                },
            )
        return context

    return dependency
