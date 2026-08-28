from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .identity_models import PrivilegedAccessStatus
from .permissions import Permission


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class MfaVerifyLogin(BaseModel):
    challenge_token: str = Field(min_length=32, max_length=256)
    code: str = Field(min_length=6, max_length=32)


class PasswordConfirmation(BaseModel):
    password: str = Field(min_length=8, max_length=256)


class MfaEnable(BaseModel):
    code: str = Field(min_length=6, max_length=6, pattern=r"^\d{6}$")


class MfaDisable(BaseModel):
    password: str = Field(min_length=8, max_length=256)
    code: str = Field(min_length=6, max_length=32)


class StepUpRequest(MfaDisable):
    pass


class MfaStatusRead(BaseModel):
    enabled: bool
    confirmed_at: datetime | None
    recovery_codes_remaining: int


class MfaSetupRead(BaseModel):
    secret: str
    provisioning_uri: str


class MfaEnabledRead(BaseModel):
    enabled: bool = True
    recovery_codes: list[str]


class PasswordForgotRequest(BaseModel):
    identifier: str = Field(min_length=3, max_length=160)


class PasswordForgotRead(BaseModel):
    message: str
    debug_reset_token: str | None = None


class PasswordResetRequest(BaseModel):
    token: str = Field(min_length=32, max_length=256)
    new_password: str = Field(min_length=15, max_length=256)
    confirm_password: str = Field(min_length=15, max_length=256)

    @model_validator(mode="after")
    def passwords_match(self):
        if self.new_password != self.confirm_password:
            raise ValueError("As senhas não coincidem")
        return self


class PasswordChangeRequest(BaseModel):
    current_password: str = Field(min_length=8, max_length=256)
    new_password: str = Field(min_length=15, max_length=256)
    confirm_password: str = Field(min_length=15, max_length=256)
    mfa_code: str | None = Field(default=None, min_length=6, max_length=32)

    @model_validator(mode="after")
    def passwords_match(self):
        if self.new_password != self.confirm_password:
            raise ValueError("As senhas não coincidem")
        if self.current_password == self.new_password:
            raise ValueError("A nova senha deve ser diferente da senha atual")
        return self


class SessionRead(BaseModel):
    id: int
    tenant_id: int
    device_name: str
    ip_address: str
    user_agent: str
    mfa_verified: bool
    privileged: bool
    created_at: datetime
    last_seen_at: datetime
    expires_at: datetime
    revoked_at: datetime | None
    revoke_reason: str
    current: bool


class SecurityEventRead(ORMModel):
    id: int
    tenant_id: int | None
    user_id: int | None
    event_type: str
    outcome: str
    ip_address: str
    user_agent: str
    request_id: str
    details: dict
    created_at: datetime


class PrivilegedAccessCreate(BaseModel):
    requested_permissions: list[Permission] = Field(min_length=1, max_length=12)
    reason: str = Field(min_length=15, max_length=4_000)
    duration_minutes: int = Field(default=30, ge=5, le=120)

    @model_validator(mode="after")
    def unique_permissions(self):
        if len(self.requested_permissions) != len(set(self.requested_permissions)):
            raise ValueError("Não repita permissões")
        return self


class PrivilegedAccessDecision(BaseModel):
    approved: bool
    review_notes: str = Field(min_length=5, max_length=4_000)


class PrivilegedAccessRead(ORMModel):
    id: int
    tenant_id: int
    membership_id: int
    requested_by_user_id: int
    requested_permissions: list[str]
    reason: str
    requested_duration_minutes: int
    status: PrivilegedAccessStatus
    reviewed_by_user_id: int | None
    review_notes: str
    reviewed_at: datetime | None
    expires_at: datetime | None
    revoked_by_user_id: int | None
    revoked_at: datetime | None
    created_at: datetime
    updated_at: datetime


class PrivilegedSessionRead(BaseModel):
    token: str | None = None
    expires_at: datetime
    permissions: list[str]
