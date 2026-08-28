from __future__ import annotations

import hashlib
import secrets
from datetime import UTC, datetime, timedelta

import pyotp
import pytest
from sqlalchemy import select

from app.config import get_settings
from app.database import SessionLocal
from app.models import Membership, Role, SessionToken, User


TEST_PASSWORD = "Senha-Segura-2026!"


def test_production_identity_configuration_is_fail_closed(monkeypatch):
    get_settings.cache_clear()
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.delenv("SECURITY_SECRET_KEY", raising=False)
    with pytest.raises(RuntimeError, match="SECURITY_SECRET_KEY"):
        get_settings()

    monkeypatch.setenv("SECURITY_SECRET_KEY", "production-secret-with-at-least-32-characters")
    monkeypatch.setenv("PASSWORD_RESET_URL", "https://rh.example/reset#reset_token={token}")
    monkeypatch.delenv("SMTP_HOST", raising=False)
    monkeypatch.delenv("SMTP_FROM", raising=False)
    get_settings.cache_clear()
    with pytest.raises(RuntimeError, match="SMTP_HOST"):
        get_settings()

    # Restaura o cache usado pelos demais testes antes do teardown do monkeypatch.
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("SECURITY_SECRET_KEY", "test-security-secret-key-with-32-characters")
    get_settings.cache_clear()
    assert get_settings().environment == "test"


def add_member(company, password_hash, *, suffix: str, role: Role = Role.employee):
    with SessionLocal() as db:
        user = User(
            username=f"security-{suffix}-{company['tenant_id']}",
            display_name=f"Segurança {suffix}",
            email=f"security-{suffix}-{company['tenant_id']}@example.com",
            password_hash=password_hash,
        )
        db.add(user)
        db.flush()
        membership = Membership(
            tenant_id=company["tenant_id"],
            user_id=user.id,
            role=role,
        )
        db.add(membership)
        db.commit()
        return {
            "tenant_id": company["tenant_id"],
            "user_id": user.id,
            "membership_id": membership.id,
            "username": user.username,
            "slug": company["slug"],
        }


def setup_mfa(client, identity, headers):
    setup = client.post(
        "/api/security/mfa/setup",
        headers=headers,
        json={"password": TEST_PASSWORD},
    )
    assert setup.status_code == 200, setup.text
    secret = setup.json()["secret"]
    enabled = client.post(
        "/api/security/mfa/enable",
        headers=headers,
        json={"code": pyotp.TOTP(secret).now()},
    )
    assert enabled.status_code == 200, enabled.text
    return secret, enabled.json()["recovery_codes"]


def test_legacy_password_is_upgraded_and_account_lock_expires(
    client, identity_factory
):
    identity = identity_factory(slug="legacy-security")
    salt = secrets.token_bytes(16)
    legacy_password = "legacy-password"
    digest = hashlib.pbkdf2_hmac(
        "sha256", legacy_password.encode(), salt, 600_000
    )
    with SessionLocal() as db:
        user = db.get(User, identity["user_id"])
        user.password_hash = (
            f"pbkdf2_sha256$600000${salt.hex()}${digest.hex()}"
        )
        db.commit()

    login = client.post(
        "/api/auth/login",
        json={
            "identifier": identity["username"],
            "password": legacy_password,
            "tenant_slug": identity["slug"],
        },
    )
    assert login.status_code == 200, login.text
    with SessionLocal() as db:
        assert db.get(User, identity["user_id"]).password_hash.startswith("$argon2id$")

    for _ in range(5):
        denied = client.post(
            "/api/auth/login",
            json={
                "identifier": identity["username"],
                "password": "incorrect-password",
                "tenant_slug": identity["slug"],
            },
        )
        assert denied.status_code == 401
    assert client.post(
        "/api/auth/login",
        json={
            "identifier": identity["username"],
            "password": legacy_password,
            "tenant_slug": identity["slug"],
        },
    ).status_code == 401
    with SessionLocal() as db:
        user = db.get(User, identity["user_id"])
        assert user.locked_until is not None
        user.locked_until = datetime.now(UTC).replace(tzinfo=None) - timedelta(seconds=1)
        db.commit()
    restored = client.post(
        "/api/auth/login",
        json={
            "identifier": identity["username"],
            "password": legacy_password,
            "tenant_slug": identity["slug"],
        },
    )
    assert restored.status_code == 200, restored.text


def test_login_rate_limit_returns_retry_after(client):
    for attempt in range(9):
        response = client.post(
            "/api/auth/login",
            json={
                "identifier": "unknown@example.com",
                "password": "incorrect-password",
            },
        )
        if attempt < 8:
            assert response.status_code == 401
        else:
            assert response.status_code == 429
            assert int(response.headers["retry-after"]) > 0


def test_password_reset_is_single_use_generic_and_revokes_sessions(
    client, identity_factory, login
):
    identity = identity_factory(slug="password-reset")
    old_headers = login(identity)
    known = client.post(
        "/api/auth/password/forgot",
        json={"identifier": identity["username"]},
    )
    unknown = client.post(
        "/api/auth/password/forgot",
        json={"identifier": "not-found@example.com"},
    )
    assert known.status_code == unknown.status_code == 202
    assert known.json()["message"] == unknown.json()["message"]
    reset_token = known.json()["debug_reset_token"]
    assert reset_token
    new_password = "Nova-Frase-Segura-2026!"
    reset = client.post(
        "/api/auth/password/reset",
        json={
            "token": reset_token,
            "new_password": new_password,
            "confirm_password": new_password,
        },
    )
    assert reset.status_code == 204, reset.text
    assert client.get("/api/auth/me", headers=old_headers).status_code == 401
    assert client.post(
        "/api/auth/password/reset",
        json={
            "token": reset_token,
            "new_password": "Outra-Frase-Segura-2026!",
            "confirm_password": "Outra-Frase-Segura-2026!",
        },
    ).status_code == 400
    relogin = client.post(
        "/api/auth/login",
        json={
            "identifier": identity["username"],
            "password": new_password,
            "tenant_slug": identity["slug"],
        },
    )
    assert relogin.status_code == 200, relogin.text


def test_mfa_challenge_replay_protection_and_recovery_code(
    client, identity_factory, login
):
    identity = identity_factory(slug="mfa-flow")
    headers = login(identity)
    secret, recovery_codes = setup_mfa(client, identity, headers)
    status = client.get("/api/security/mfa", headers=headers).json()
    assert status["enabled"] is True
    assert status["recovery_codes_remaining"] == 10

    challenge = client.post(
        "/api/auth/login",
        json={
            "identifier": identity["username"],
            "password": TEST_PASSWORD,
            "tenant_slug": identity["slug"],
        },
    )
    assert challenge.status_code == 200, challenge.text
    assert challenge.json()["mfa_required"] is True
    next_code = pyotp.TOTP(secret).at(datetime.now(UTC) + timedelta(seconds=30))
    verified = client.post(
        "/api/auth/mfa/verify",
        json={
            "challenge_token": challenge.json()["challenge_token"],
            "code": next_code,
        },
    )
    assert verified.status_code == 200, verified.text
    assert verified.json()["token"]
    replay = client.post(
        "/api/auth/mfa/verify",
        json={
            "challenge_token": challenge.json()["challenge_token"],
            "code": next_code,
        },
    )
    assert replay.status_code == 401

    recovery_challenge = client.post(
        "/api/auth/login",
        json={
            "identifier": identity["username"],
            "password": TEST_PASSWORD,
            "tenant_slug": identity["slug"],
        },
    ).json()
    recovered = client.post(
        "/api/auth/mfa/verify",
        json={
            "challenge_token": recovery_challenge["challenge_token"],
            "code": recovery_codes[0],
        },
    )
    assert recovered.status_code == 200, recovered.text
    assert client.get("/api/security/mfa", headers={
        "Authorization": "Bearer " + recovered.json()["token"]
    }).json()["recovery_codes_remaining"] == 9


def test_step_up_checks_password_before_consuming_totp(
    client, identity_factory, login
):
    identity = identity_factory(slug="step-up-order")
    headers = login(identity)
    secret, _ = setup_mfa(client, identity, headers)
    code = pyotp.TOTP(secret).at(datetime.now(UTC) + timedelta(seconds=30))

    denied = client.post(
        "/api/security/step-up",
        headers=headers,
        json={"password": "incorrect-password", "code": code},
    )
    assert denied.status_code == 401
    accepted = client.post(
        "/api/security/step-up",
        headers=headers,
        json={"password": TEST_PASSWORD, "code": code},
    )
    assert accepted.status_code == 200, accepted.text


def test_cookie_session_requires_csrf_and_is_http_only(
    client, identity_factory
):
    identity = identity_factory(slug="cookie-session")
    response = client.post(
        "/api/auth/login",
        headers={"X-Session-Mode": "cookie"},
        json={
            "identifier": identity["username"],
            "password": TEST_PASSWORD,
            "tenant_slug": identity["slug"],
        },
    )
    assert response.status_code == 200, response.text
    assert response.json()["token"] is None
    cookies = "; ".join(response.headers.get_list("set-cookie"))
    assert "HttpOnly" in cookies and "SameSite=strict" in cookies
    assert client.get("/api/auth/me").status_code == 200
    denied = client.put(
        "/api/tenants/tutorial",
        json={"completed": True, "dismissed": False, "version": 4},
    )
    assert denied.status_code == 403
    csrf = client.cookies.get("chs_csrf")
    accepted = client.put(
        "/api/tenants/tutorial",
        headers={"X-CSRF-Token": csrf},
        json={"completed": True, "dismissed": False, "version": 4},
    )
    assert accepted.status_code == 200, accepted.text


def test_sessions_are_listed_revocable_and_idle_expire(
    client, identity_factory
):
    identity = identity_factory(slug="session-control")
    payload = {
        "identifier": identity["username"],
        "password": TEST_PASSWORD,
        "tenant_slug": identity["slug"],
    }
    first = client.post("/api/auth/login", json=payload).json()["token"]
    second = client.post("/api/auth/login", json=payload).json()["token"]
    second_headers = {"Authorization": "Bearer " + second}
    sessions = client.get("/api/security/sessions", headers=second_headers).json()
    first_session = next(item for item in sessions if not item["current"])
    assert client.delete(
        f"/api/security/sessions/{first_session['id']}", headers=second_headers
    ).status_code == 204
    assert client.get(
        "/api/auth/me", headers={"Authorization": "Bearer " + first}
    ).status_code == 401

    with SessionLocal() as db:
        current = db.scalar(
            select(SessionToken).where(
                SessionToken.user_id == identity["user_id"],
                SessionToken.revoked_at.is_(None),
            )
        )
        current.last_seen_at = datetime.now(UTC).replace(tzinfo=None) - timedelta(hours=2)
        db.commit()
    assert client.get("/api/auth/me", headers=second_headers).status_code == 401


def test_privileged_access_requires_mfa_dual_approval_and_expires_on_revoke(
    client, identity_factory, login, password_hash
):
    company = identity_factory(slug="privileged-access")
    requester = add_member(company, password_hash, suffix="requester")
    owner_headers = login(company)
    requester_headers = login(requester)
    setup_mfa(client, company, owner_headers)
    setup_mfa(client, requester, requester_headers)

    assert client.get("/api/audit", headers=requester_headers).status_code == 403
    requested = client.post(
        "/api/security/privileged-access",
        headers=requester_headers,
        json={
            "requested_permissions": ["audit.read"],
            "reason": "Investigar incidente documentado no atendimento interno",
            "duration_minutes": 30,
        },
    )
    assert requested.status_code == 201, requested.text
    grant_id = requested.json()["id"]
    self_decision = client.post(
        f"/api/security/privileged-access/{grant_id}/decision",
        headers=requester_headers,
        json={"approved": True, "review_notes": "Tentativa indevida"},
    )
    assert self_decision.status_code == 403
    approved = client.post(
        f"/api/security/privileged-access/{grant_id}/decision",
        headers=owner_headers,
        json={"approved": True, "review_notes": "Incidente e prazo conferidos"},
    )
    assert approved.status_code == 200, approved.text
    activated = client.post(
        f"/api/security/privileged-access/{grant_id}/activate",
        headers=requester_headers,
    )
    assert activated.status_code == 200, activated.text
    privileged_headers = {
        "Authorization": "Bearer " + activated.json()["token"]
    }
    assert client.get("/api/audit", headers=privileged_headers).status_code == 200
    revoked = client.post(
        f"/api/security/privileged-access/{grant_id}/revoke",
        headers=owner_headers,
    )
    assert revoked.status_code == 200, revoked.text
    assert revoked.json()["status"] == "revoked"
    assert client.get("/api/audit", headers=privileged_headers).status_code == 401
