from __future__ import annotations

import hashlib
import secrets
from datetime import timedelta
from typing import Annotated

import pyotp
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request, Response
from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..database import get_db
from ..email_service import safely_send_password_reset_email
from ..identity_models import (
    MfaLoginChallenge,
    PasswordResetToken,
    PrivilegedAccessGrant,
    PrivilegedAccessStatus,
    SecurityEvent,
    UserMfa,
)
from ..identity_schemas import (
    MfaDisable,
    MfaEnable,
    MfaEnabledRead,
    MfaSetupRead,
    MfaStatusRead,
    MfaVerifyLogin,
    PasswordChangeRequest,
    PasswordConfirmation,
    PasswordForgotRead,
    PasswordForgotRequest,
    PasswordResetRequest,
    PrivilegedAccessCreate,
    PrivilegedAccessDecision,
    PrivilegedAccessRead,
    PrivilegedSessionRead,
    SecurityEventRead,
    SessionRead,
    StepUpRequest,
)
from ..models import Membership, SessionToken, Tenant, User
from ..permissions import Permission, permissions_for_role
from ..schemas import LoginResponse, TenantSummary, TutorialState
from ..security import (
    AuthContext,
    active_memberships,
    attach_session_cookies,
    clear_session_cookies,
    client_ip,
    consume_rate_limit,
    current_context,
    decrypt_secret,
    encrypt_secret,
    find_user,
    generate_recovery_codes,
    hash_password,
    issue_session,
    record_security_event,
    require_permissions,
    require_recent_mfa,
    revoke_all_user_sessions,
    utcnow,
    validate_password,
    verify_mfa_or_recovery,
    verify_password,
    verify_totp,
)
from ..services import audit, model_snapshot


router = APIRouter(prefix="/api", tags=["identity-security"])

ELEVATABLE_PERMISSIONS = frozenset(
    {
        Permission.audit_read,
        Permission.payroll_manage,
        Permission.employee_files_manage,
        Permission.knowledge_manage,
        Permission.esocial_manage,
        Permission.contracts_manage,
        Permission.performance_manage,
        Permission.reports_read,
    }
)


def tutorial_state(membership: Membership) -> TutorialState:
    version = get_settings().tutorial_version
    return TutorialState(
        current_version=version,
        version_seen=membership.tutorial_version_seen,
        dismissed=membership.tutorial_dismissed,
        should_show=(
            not membership.tutorial_dismissed
            and membership.tutorial_version_seen < version
        ),
    )


def tenant_summary(membership: Membership) -> TenantSummary:
    return TenantSummary(
        id=membership.tenant.id,
        name=membership.tenant.name,
        slug=membership.tenant.slug,
        role=membership.role,
    )


def login_response(
    user: User,
    membership: Membership,
    memberships: list[Membership],
    token: str | None,
) -> LoginResponse:
    return LoginResponse(
        token=token,
        user_id=user.id,
        username=user.username,
        display_name=user.display_name,
        email=user.email,
        role=membership.role,
        tenant=tenant_summary(membership),
        tenants=[tenant_summary(item) for item in memberships],
        permissions=sorted(
            item.value for item in permissions_for_role(membership.role.value)
        ),
        tutorial=tutorial_state(membership),
    )


def mfa_credential(db: Session, user_id: int, *, required: bool = True) -> UserMfa | None:
    credential = db.get(UserMfa, user_id)
    if required and (not credential or not credential.enabled):
        raise HTTPException(409, "MFA ainda não está habilitado")
    return credential


def consume_confirmation_limit(
    db: Session, context: AuthContext, *, scope: str
) -> None:
    consume_rate_limit(
        db,
        scope=scope,
        key=str(context.user.id),
        limit=6,
        window=timedelta(minutes=15),
        commit_event=False,
    )


def deny_confirmation(
    db: Session,
    request: Request,
    context: AuthContext,
    *,
    event_type: str,
    reason: str,
    detail: str = "Confirmação inválida",
    status_code: int = 401,
):
    record_security_event(
        db,
        request,
        event_type=event_type,
        outcome="denied",
        user_id=context.user.id,
        tenant_id=context.tenant_id,
        details={"reason": reason},
        commit=True,
    )
    raise HTTPException(status_code, detail)


@router.post("/auth/mfa/verify", response_model=LoginResponse)
def verify_login_mfa(
    payload: MfaVerifyLogin,
    request: Request,
    response: Response,
    db: Annotated[Session, Depends(get_db)],
):
    consume_rate_limit(
        db,
        scope="mfa_ip",
        key=client_ip(request),
        limit=15,
        window=timedelta(minutes=5),
    )
    token_hash = hashlib.sha256(payload.challenge_token.encode()).hexdigest()
    challenge = db.scalar(
        select(MfaLoginChallenge).where(MfaLoginChallenge.token_hash == token_hash)
    )
    current = utcnow()
    if (
        not challenge
        or challenge.consumed_at is not None
        or challenge.expires_at <= current
        or challenge.attempts >= 5
    ):
        raise HTTPException(401, "Desafio MFA inválido ou expirado")
    credential = mfa_credential(db, challenge.user_id)
    valid, used_recovery = verify_mfa_or_recovery(credential, payload.code)
    if not valid:
        challenge.attempts += 1
        if challenge.attempts >= 5:
            challenge.consumed_at = current
        record_security_event(
            db,
            request,
            event_type="login_mfa",
            outcome="denied",
            user_id=challenge.user_id,
            tenant_id=challenge.tenant_id,
            details={"attempt": challenge.attempts},
            commit=True,
        )
        raise HTTPException(401, "Código MFA inválido")
    user = db.get(User, challenge.user_id)
    membership = db.get(Membership, challenge.membership_id)
    tenant = db.get(Tenant, challenge.tenant_id)
    if (
        not user
        or not user.active
        or not membership
        or not membership.active
        or not tenant
        or not tenant.active
        or membership.user_id != user.id
        or membership.tenant_id != tenant.id
    ):
        raise HTTPException(401, "Acesso inativo")
    challenge.consumed_at = current
    user.last_login_at = current
    record_security_event(
        db,
        request,
        event_type="login_mfa",
        outcome="success",
        user_id=user.id,
        tenant_id=tenant.id,
        details={"recovery_code": used_recovery},
    )
    raw = issue_session(db, user, membership, request=request, mfa_verified=True)
    attach_session_cookies(response, raw)
    browser = request.headers.get("x-session-mode", "").lower() == "cookie"
    return login_response(
        user,
        membership,
        active_memberships(db, user.id),
        None if browser else raw,
    )


@router.get("/security/mfa", response_model=MfaStatusRead)
def get_mfa_status(
    context: Annotated[AuthContext, Depends(current_context)],
    db: Annotated[Session, Depends(get_db)],
):
    credential = db.get(UserMfa, context.user.id)
    return MfaStatusRead(
        enabled=bool(credential and credential.enabled),
        confirmed_at=credential.confirmed_at if credential else None,
        recovery_codes_remaining=(
            len(credential.recovery_code_hashes) if credential and credential.enabled else 0
        ),
    )


@router.post("/security/mfa/setup", response_model=MfaSetupRead)
def setup_mfa(
    payload: PasswordConfirmation,
    request: Request,
    context: Annotated[AuthContext, Depends(current_context)],
    db: Annotated[Session, Depends(get_db)],
):
    consume_confirmation_limit(db, context, scope="mfa_setup_user")
    if not verify_password(payload.password, context.user.password_hash):
        deny_confirmation(
            db,
            request,
            context,
            event_type="mfa_setup",
            reason="invalid_password",
            detail="Senha atual inválida",
        )
    existing = db.get(UserMfa, context.user.id)
    if existing and existing.enabled:
        raise HTTPException(409, "MFA já está habilitado")
    secret = pyotp.random_base32(length=32)
    if existing:
        before = {"enabled": existing.enabled}
        existing.secret_ciphertext = encrypt_secret(secret)
        existing.recovery_code_hashes = []
        existing.last_used_step = None
        credential = existing
    else:
        before = None
        credential = UserMfa(
            user_id=context.user.id,
            secret_ciphertext=encrypt_secret(secret),
        )
        db.add(credential)
    audit(
        db,
        context=context,
        request=request,
        action="setup",
        entity="mfa",
        entity_id=str(context.user.id),
        details="Segredo pendente de confirmação",
        before=before,
        after={"enabled": False},
    )
    db.commit()
    uri = pyotp.TOTP(secret).provisioning_uri(
        name=context.user.email,
        issuer_name=get_settings().app_name,
    )
    return MfaSetupRead(secret=secret, provisioning_uri=uri)


@router.post("/security/mfa/enable", response_model=MfaEnabledRead)
def enable_mfa(
    payload: MfaEnable,
    request: Request,
    context: Annotated[AuthContext, Depends(current_context)],
    db: Annotated[Session, Depends(get_db)],
):
    consume_confirmation_limit(db, context, scope="mfa_enable_user")
    credential = db.get(UserMfa, context.user.id)
    if not credential or credential.enabled:
        raise HTTPException(409, "Configuração MFA pendente não encontrada")
    if not verify_totp(credential, payload.code):
        deny_confirmation(
            db,
            request,
            context,
            event_type="mfa_enable",
            reason="invalid_mfa",
            detail="Código MFA inválido",
        )
    codes, hashes = generate_recovery_codes()
    credential.enabled = True
    credential.confirmed_at = utcnow()
    credential.recovery_code_hashes = hashes
    context.session.mfa_verified = True
    context.session.authenticated_at = utcnow()
    revoke_all_user_sessions(
        db,
        context.user.id,
        "MFA habilitado",
        except_session_id=context.session.id,
    )
    audit(
        db,
        context=context,
        request=request,
        action="enable",
        entity="mfa",
        entity_id=str(context.user.id),
        details="MFA TOTP habilitado; códigos exibidos uma única vez",
        after={"enabled": True, "recovery_codes": len(codes)},
    )
    record_security_event(
        db,
        request,
        event_type="mfa_enabled",
        outcome="success",
        user_id=context.user.id,
        tenant_id=context.tenant_id,
    )
    db.commit()
    return MfaEnabledRead(recovery_codes=codes)


@router.post("/security/mfa/recovery-codes", response_model=MfaEnabledRead)
def regenerate_recovery_codes(
    payload: StepUpRequest,
    request: Request,
    context: Annotated[AuthContext, Depends(current_context)],
    db: Annotated[Session, Depends(get_db)],
):
    consume_confirmation_limit(db, context, scope="mfa_recovery_codes_user")
    credential = mfa_credential(db, context.user.id)
    if not verify_password(payload.password, context.user.password_hash):
        deny_confirmation(
            db,
            request,
            context,
            event_type="mfa_recovery_codes",
            reason="invalid_password",
        )
    valid, _ = verify_mfa_or_recovery(credential, payload.code)
    if not valid:
        deny_confirmation(
            db,
            request,
            context,
            event_type="mfa_recovery_codes",
            reason="invalid_mfa",
        )
    codes, hashes = generate_recovery_codes()
    credential.recovery_code_hashes = hashes
    context.session.mfa_verified = True
    context.session.authenticated_at = utcnow()
    audit(
        db,
        context=context,
        request=request,
        action="regenerate_recovery_codes",
        entity="mfa",
        entity_id=str(context.user.id),
        after={"recovery_codes": len(codes)},
    )
    db.commit()
    return MfaEnabledRead(recovery_codes=codes)


@router.post("/security/mfa/disable", response_model=MfaStatusRead)
def disable_mfa(
    payload: MfaDisable,
    request: Request,
    context: Annotated[AuthContext, Depends(current_context)],
    db: Annotated[Session, Depends(get_db)],
):
    consume_confirmation_limit(db, context, scope="mfa_disable_user")
    credential = mfa_credential(db, context.user.id)
    if not verify_password(payload.password, context.user.password_hash):
        deny_confirmation(
            db,
            request,
            context,
            event_type="mfa_disable",
            reason="invalid_password",
        )
    valid, _ = verify_mfa_or_recovery(credential, payload.code)
    if not valid:
        deny_confirmation(
            db,
            request,
            context,
            event_type="mfa_disable",
            reason="invalid_mfa",
        )
    before = {"enabled": credential.enabled}
    db.delete(credential)
    context.session.mfa_verified = False
    context.session.authenticated_at = utcnow()
    revoke_all_user_sessions(
        db,
        context.user.id,
        "MFA desabilitado",
        except_session_id=context.session.id,
    )
    audit(
        db,
        context=context,
        request=request,
        action="disable",
        entity="mfa",
        entity_id=str(context.user.id),
        before=before,
        after={"enabled": False},
    )
    record_security_event(
        db,
        request,
        event_type="mfa_disabled",
        outcome="success",
        user_id=context.user.id,
        tenant_id=context.tenant_id,
    )
    db.commit()
    return MfaStatusRead(enabled=False, confirmed_at=None, recovery_codes_remaining=0)


@router.post("/security/step-up", response_model=MfaStatusRead)
def step_up(
    payload: StepUpRequest,
    request: Request,
    context: Annotated[AuthContext, Depends(current_context)],
    db: Annotated[Session, Depends(get_db)],
):
    consume_rate_limit(
        db,
        scope="step_up_user",
        key=str(context.user.id),
        limit=6,
        window=timedelta(minutes=15),
    )
    credential = mfa_credential(db, context.user.id)
    if not verify_password(payload.password, context.user.password_hash):
        deny_confirmation(
            db,
            request,
            context,
            event_type="step_up",
            reason="invalid_password",
        )
    valid, _ = verify_mfa_or_recovery(credential, payload.code)
    if not valid:
        deny_confirmation(
            db,
            request,
            context,
            event_type="step_up",
            reason="invalid_mfa",
        )
    context.session.mfa_verified = True
    context.session.authenticated_at = utcnow()
    record_security_event(
        db,
        request,
        event_type="step_up",
        outcome="success",
        user_id=context.user.id,
        tenant_id=context.tenant_id,
    )
    db.commit()
    return MfaStatusRead(
        enabled=True,
        confirmed_at=credential.confirmed_at,
        recovery_codes_remaining=len(credential.recovery_code_hashes),
    )


@router.post("/auth/password/forgot", response_model=PasswordForgotRead, status_code=202)
def forgot_password(
    payload: PasswordForgotRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    db: Annotated[Session, Depends(get_db)],
):
    consume_rate_limit(
        db,
        scope="forgot_ip",
        key=client_ip(request),
        limit=5,
        window=timedelta(minutes=15),
        commit_event=False,
    )
    consume_rate_limit(
        db,
        scope="forgot_identity",
        key=payload.identifier,
        limit=3,
        window=timedelta(hours=1),
    )
    user = find_user(db, payload.identifier)
    debug_token = None
    if user and user.active:
        current = utcnow()
        for old in db.scalars(
            select(PasswordResetToken).where(
                PasswordResetToken.user_id == user.id,
                PasswordResetToken.used_at.is_(None),
            )
        ).all():
            old.used_at = current
        raw = secrets.token_urlsafe(48)
        db.add(
            PasswordResetToken(
                token_hash=hashlib.sha256(raw.encode()).hexdigest(),
                user_id=user.id,
                expires_at=current
                + timedelta(minutes=get_settings().password_reset_ttl_minutes),
                requested_ip=client_ip(request),
            )
        )
        reset_url = get_settings().password_reset_url.format(token=raw)
        settings = get_settings()
        queued = bool(settings.smtp_host and settings.smtp_from)
        if queued:
            background_tasks.add_task(
                safely_send_password_reset_email,
                user.email,
                user.display_name,
                reset_url,
            )
        record_security_event(
            db,
            request,
            event_type="password_reset_requested",
            outcome="queued" if queued else "delivery_unavailable",
            user_id=user.id,
            details={"delivery": "smtp" if queued else "not_configured"},
        )
        if get_settings().environment in {"development", "test"}:
            debug_token = raw
        db.commit()
    return PasswordForgotRead(
        message="Se a conta existir, as instruções de recuperação serão enviadas.",
        debug_reset_token=debug_token,
    )


@router.post("/auth/password/reset", status_code=204)
def reset_password(
    payload: PasswordResetRequest,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
):
    consume_rate_limit(
        db,
        scope="reset_ip",
        key=client_ip(request),
        limit=10,
        window=timedelta(minutes=15),
    )
    item = db.scalar(
        select(PasswordResetToken).where(
            PasswordResetToken.token_hash
            == hashlib.sha256(payload.token.encode()).hexdigest()
        )
    )
    current = utcnow()
    if not item or item.used_at is not None or item.expires_at <= current:
        raise HTTPException(400, "Token inválido ou expirado")
    user = db.get(User, item.user_id)
    if not user or not user.active:
        raise HTTPException(400, "Token inválido ou expirado")
    try:
        validate_password(payload.new_password, user)
    except ValueError as error:
        raise HTTPException(422, str(error)) from error
    user.password_hash = hash_password(payload.new_password)
    user.password_changed_at = current
    user.failed_login_attempts = 0
    user.locked_until = None
    item.used_at = current
    revoke_all_user_sessions(db, user.id, "Senha redefinida")
    record_security_event(
        db,
        request,
        event_type="password_reset_completed",
        outcome="success",
        user_id=user.id,
    )
    db.commit()


@router.post("/security/password/change", status_code=204)
def change_password(
    payload: PasswordChangeRequest,
    request: Request,
    context: Annotated[AuthContext, Depends(current_context)],
    db: Annotated[Session, Depends(get_db)],
):
    consume_rate_limit(
        db,
        scope="password_change_user",
        key=str(context.user.id),
        limit=5,
        window=timedelta(minutes=15),
        commit_event=False,
    )
    if not verify_password(payload.current_password, context.user.password_hash):
        record_security_event(
            db,
            request,
            event_type="password_change",
            outcome="denied",
            user_id=context.user.id,
            tenant_id=context.tenant_id,
            details={"reason": "invalid_password"},
            commit=True,
        )
        raise HTTPException(401, "Senha atual inválida")
    credential = db.get(UserMfa, context.user.id)
    if credential and credential.enabled:
        if not payload.mfa_code:
            record_security_event(
                db,
                request,
                event_type="password_change",
                outcome="denied",
                user_id=context.user.id,
                tenant_id=context.tenant_id,
                details={"reason": "mfa_required"},
                commit=True,
            )
            raise HTTPException(422, "Informe o código MFA")
        valid, _ = verify_mfa_or_recovery(credential, payload.mfa_code)
        if not valid:
            record_security_event(
                db,
                request,
                event_type="password_change",
                outcome="denied",
                user_id=context.user.id,
                tenant_id=context.tenant_id,
                details={"reason": "invalid_mfa"},
                commit=True,
            )
            raise HTTPException(401, "Código MFA inválido")
    try:
        validate_password(payload.new_password, context.user)
    except ValueError as error:
        raise HTTPException(422, str(error)) from error
    context.user.password_hash = hash_password(payload.new_password)
    context.user.password_changed_at = utcnow()
    context.session.authenticated_at = utcnow()
    context.session.mfa_verified = bool(credential and credential.enabled)
    revoke_all_user_sessions(
        db,
        context.user.id,
        "Senha alterada",
        except_session_id=context.session.id,
    )
    audit(
        db,
        context=context,
        request=request,
        action="change_password",
        entity="user_security",
        entity_id=str(context.user.id),
        details="Outras sessões revogadas",
    )
    record_security_event(
        db,
        request,
        event_type="password_changed",
        outcome="success",
        user_id=context.user.id,
        tenant_id=context.tenant_id,
    )
    db.commit()


@router.get("/security/sessions", response_model=list[SessionRead])
def list_sessions(
    context: Annotated[AuthContext, Depends(current_context)],
    db: Annotated[Session, Depends(get_db)],
):
    items = db.scalars(
        select(SessionToken)
        .where(SessionToken.user_id == context.user.id)
        .order_by(SessionToken.created_at.desc())
        .limit(50)
    ).all()
    return [
        SessionRead(
            id=item.id,
            tenant_id=item.tenant_id,
            device_name=item.device_name,
            ip_address=item.ip_address,
            user_agent=item.user_agent,
            mfa_verified=item.mfa_verified,
            privileged=item.privileged_grant_id is not None,
            created_at=item.created_at,
            last_seen_at=item.last_seen_at,
            expires_at=item.expires_at,
            revoked_at=item.revoked_at,
            revoke_reason=item.revoke_reason,
            current=item.id == context.session.id,
        )
        for item in items
    ]


@router.delete("/security/sessions/{session_id}", status_code=204)
def revoke_user_session(
    session_id: int,
    request: Request,
    response: Response,
    context: Annotated[AuthContext, Depends(current_context)],
    db: Annotated[Session, Depends(get_db)],
):
    item = db.scalar(
        select(SessionToken).where(
            SessionToken.id == session_id,
            SessionToken.user_id == context.user.id,
        )
    )
    if not item:
        raise HTTPException(404, "Sessão não encontrada")
    if item.revoked_at is None:
        item.revoked_at = utcnow()
        item.revoke_reason = "Revogada pelo usuário"
    record_security_event(
        db,
        request,
        event_type="session_revoked",
        outcome="success",
        user_id=context.user.id,
        tenant_id=context.tenant_id,
        details={"session_id": item.id, "current": item.id == context.session.id},
    )
    db.commit()
    if item.id == context.session.id:
        clear_session_cookies(response)


@router.post("/security/sessions/revoke-others", status_code=204)
def revoke_other_sessions(
    request: Request,
    context: Annotated[AuthContext, Depends(current_context)],
    db: Annotated[Session, Depends(get_db)],
):
    count = revoke_all_user_sessions(
        db,
        context.user.id,
        "Revogada pelo usuário",
        except_session_id=context.session.id,
    )
    record_security_event(
        db,
        request,
        event_type="sessions_revoked",
        outcome="success",
        user_id=context.user.id,
        tenant_id=context.tenant_id,
        details={"count": count},
    )
    db.commit()


@router.get("/security/events", response_model=list[SecurityEventRead])
def list_security_events(
    context: Annotated[AuthContext, Depends(current_context)],
    db: Annotated[Session, Depends(get_db)],
    limit: int = Query(100, ge=1, le=500),
):
    statement = select(SecurityEvent)
    if Permission.security_manage in context.permissions:
        statement = statement.where(
            or_(
                SecurityEvent.tenant_id == context.tenant_id,
                and_(
                    SecurityEvent.tenant_id.is_(None),
                    SecurityEvent.user_id == context.user.id,
                ),
            )
        )
    else:
        statement = statement.where(SecurityEvent.user_id == context.user.id)
    return db.scalars(statement.order_by(SecurityEvent.created_at.desc()).limit(limit)).all()


@router.get("/security/privileged-access", response_model=list[PrivilegedAccessRead])
def list_privileged_access(
    context: Annotated[AuthContext, Depends(current_context)],
    db: Annotated[Session, Depends(get_db)],
):
    statement = select(PrivilegedAccessGrant).where(
        PrivilegedAccessGrant.tenant_id == context.tenant_id
    )
    if Permission.security_manage not in context.permissions:
        statement = statement.where(
            PrivilegedAccessGrant.membership_id == context.membership.id
        )
    return db.scalars(statement.order_by(PrivilegedAccessGrant.created_at.desc())).all()


@router.post(
    "/security/privileged-access",
    response_model=PrivilegedAccessRead,
    status_code=201,
)
def request_privileged_access(
    payload: PrivilegedAccessCreate,
    request: Request,
    context: Annotated[AuthContext, Depends(current_context)],
    db: Annotated[Session, Depends(get_db)],
):
    require_recent_mfa(context)
    requested = set(payload.requested_permissions)
    unavailable = requested - ELEVATABLE_PERMISSIONS
    already_owned = requested & context.permissions
    if unavailable:
        raise HTTPException(
            422,
            {"permissions_not_elevatable": sorted(item.value for item in unavailable)},
        )
    if already_owned:
        raise HTTPException(
            422,
            {"permissions_already_owned": sorted(item.value for item in already_owned)},
        )
    pending = db.scalar(
        select(PrivilegedAccessGrant.id).where(
            PrivilegedAccessGrant.tenant_id == context.tenant_id,
            PrivilegedAccessGrant.membership_id == context.membership.id,
            PrivilegedAccessGrant.status == PrivilegedAccessStatus.requested,
        )
    )
    if pending:
        raise HTTPException(409, "Já existe solicitação privilegiada pendente")
    item = PrivilegedAccessGrant(
        tenant_id=context.tenant_id,
        membership_id=context.membership.id,
        requested_by_user_id=context.user.id,
        requested_permissions=sorted(permission.value for permission in requested),
        reason=payload.reason,
        requested_duration_minutes=payload.duration_minutes,
    )
    db.add(item)
    db.flush()
    audit(
        db,
        context=context,
        request=request,
        action="request",
        entity="privileged_access",
        entity_id=str(item.id),
        details=item.reason,
        after=model_snapshot(item),
    )
    db.commit()
    db.refresh(item)
    return item


@router.post(
    "/security/privileged-access/{grant_id}/decision",
    response_model=PrivilegedAccessRead,
)
def decide_privileged_access(
    grant_id: int,
    payload: PrivilegedAccessDecision,
    request: Request,
    context: Annotated[
        AuthContext, Depends(require_permissions(Permission.security_manage))
    ],
    db: Annotated[Session, Depends(get_db)],
):
    require_recent_mfa(context)
    item = db.scalar(
        select(PrivilegedAccessGrant).where(
            PrivilegedAccessGrant.id == grant_id,
            PrivilegedAccessGrant.tenant_id == context.tenant_id,
        )
    )
    if not item:
        raise HTTPException(404, "Solicitação não encontrada")
    if item.status != PrivilegedAccessStatus.requested:
        raise HTTPException(409, "Solicitação já decidida")
    if item.requested_by_user_id == context.user.id:
        raise HTTPException(403, "Solicitante não pode aprovar o próprio acesso")
    before = model_snapshot(item)
    item.status = (
        PrivilegedAccessStatus.approved
        if payload.approved
        else PrivilegedAccessStatus.rejected
    )
    item.reviewed_by_user_id = context.user.id
    item.review_notes = payload.review_notes
    item.reviewed_at = utcnow()
    if payload.approved:
        item.expires_at = utcnow() + timedelta(
            minutes=item.requested_duration_minutes
        )
    audit(
        db,
        context=context,
        request=request,
        action="approve" if payload.approved else "reject",
        entity="privileged_access",
        entity_id=str(item.id),
        details=payload.review_notes,
        before=before,
        after=model_snapshot(item),
    )
    db.commit()
    db.refresh(item)
    return item


@router.post(
    "/security/privileged-access/{grant_id}/activate",
    response_model=PrivilegedSessionRead,
)
def activate_privileged_access(
    grant_id: int,
    request: Request,
    response: Response,
    context: Annotated[AuthContext, Depends(current_context)],
    db: Annotated[Session, Depends(get_db)],
):
    require_recent_mfa(context)
    item = db.scalar(
        select(PrivilegedAccessGrant).where(
            PrivilegedAccessGrant.id == grant_id,
            PrivilegedAccessGrant.tenant_id == context.tenant_id,
            PrivilegedAccessGrant.membership_id == context.membership.id,
        )
    )
    if (
        not item
        or item.status != PrivilegedAccessStatus.approved
        or item.expires_at is None
        or item.expires_at <= utcnow()
    ):
        raise HTTPException(409, "Acesso não está aprovado ou já expirou")
    raw = issue_session(
        db,
        context.user,
        context.membership,
        request=request,
        mfa_verified=True,
        privileged_grant_id=item.id,
        expires_at=item.expires_at,
        commit=False,
    )
    attach_session_cookies(response, raw)
    audit(
        db,
        context=context,
        request=request,
        action="activate",
        entity="privileged_access",
        entity_id=str(item.id),
        details=f"Expira em {item.expires_at.isoformat()}",
    )
    db.commit()
    browser = request.headers.get("x-session-mode", "").lower() == "cookie"
    return PrivilegedSessionRead(
        token=None if browser else raw,
        expires_at=item.expires_at,
        permissions=item.requested_permissions,
    )


@router.post(
    "/security/privileged-access/{grant_id}/revoke",
    response_model=PrivilegedAccessRead,
)
def revoke_privileged_access(
    grant_id: int,
    request: Request,
    context: Annotated[AuthContext, Depends(current_context)],
    db: Annotated[Session, Depends(get_db)],
):
    item = db.scalar(
        select(PrivilegedAccessGrant).where(
            PrivilegedAccessGrant.id == grant_id,
            PrivilegedAccessGrant.tenant_id == context.tenant_id,
        )
    )
    if not item:
        raise HTTPException(404, "Acesso não encontrado")
    owns = item.membership_id == context.membership.id
    manages = Permission.security_manage in context.permissions
    if not owns and not manages:
        raise HTTPException(404, "Acesso não encontrado")
    if item.status not in {
        PrivilegedAccessStatus.requested,
        PrivilegedAccessStatus.approved,
    }:
        raise HTTPException(409, "Acesso não pode mais ser revogado")
    before = model_snapshot(item)
    if item.status == PrivilegedAccessStatus.requested:
        item.status = PrivilegedAccessStatus.cancelled
    else:
        if manages:
            require_recent_mfa(context)
        item.status = PrivilegedAccessStatus.revoked
        item.revoked_by_user_id = context.user.id
        item.revoked_at = utcnow()
        sessions = db.scalars(
            select(SessionToken).where(
                SessionToken.privileged_grant_id == item.id,
                SessionToken.revoked_at.is_(None),
            )
        ).all()
        for session in sessions:
            session.revoked_at = utcnow()
            session.revoke_reason = "Acesso privilegiado revogado"
    audit(
        db,
        context=context,
        request=request,
        action="cancel" if item.status == PrivilegedAccessStatus.cancelled else "revoke",
        entity="privileged_access",
        entity_id=str(item.id),
        before=before,
        after=model_snapshot(item),
    )
    db.commit()
    db.refresh(item)
    return item
