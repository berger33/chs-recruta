from __future__ import annotations
import hashlib,hmac,secrets
from dataclasses import dataclass
from datetime import UTC,datetime,timedelta
from typing import Annotated
from fastapi import Depends,HTTPException,status
from fastapi.security import HTTPAuthorizationCredentials,HTTPBearer
from sqlalchemy import or_,select
from sqlalchemy.orm import Session
from .config import get_settings
from .database import activate_tenant_scope,get_db
from .models import Membership,SessionToken,Tenant,User
from .permissions import Permission,permissions_for_role

PBKDF2_ITERATIONS=600_000
bearer=HTTPBearer(auto_error=False)
def _utcnow(): return datetime.now(UTC).replace(tzinfo=None)
def hash_password(password: str,salt: bytes|None=None)->str:
    if len(password)<8: raise ValueError("A senha deve ter pelo menos 8 caracteres.")
    salt=salt or secrets.token_bytes(16)
    digest=hashlib.pbkdf2_hmac("sha256",password.encode(),salt,PBKDF2_ITERATIONS)
    return "pbkdf2_sha256$"+str(PBKDF2_ITERATIONS)+"$"+salt.hex()+"$"+digest.hex()
def verify_password(password: str,stored: str)->bool:
    try:
        algorithm,iterations,salt_hex,digest_hex=stored.split("$",3)
        if algorithm!="pbkdf2_sha256": return False
        digest=hashlib.pbkdf2_hmac("sha256",password.encode(),bytes.fromhex(salt_hex),int(iterations))
        return hmac.compare_digest(digest.hex(),digest_hex)
    except (ValueError,TypeError): return False

@dataclass(frozen=True,slots=True)
class AuthContext:
    user: User; membership: Membership; tenant: Tenant
    @property
    def tenant_id(self): return self.tenant.id
    @property
    def permissions(self): return permissions_for_role(self.membership.role.value)

def find_user(db: Session,identifier: str):
    value=identifier.strip().lower()
    return db.scalar(select(User).where(or_(User.username==value,User.email==value)))
def active_memberships(db: Session,user_id: int):
    return list(db.scalars(select(Membership).join(Tenant,Tenant.id==Membership.tenant_id).where(Membership.user_id==user_id,Membership.active.is_(True),Tenant.active.is_(True)).order_by(Tenant.name)).all())
def issue_session(db: Session,user: User,membership: Membership)->str:
    raw=secrets.token_urlsafe(32)
    db.add(SessionToken(token_hash=hashlib.sha256(raw.encode()).hexdigest(),user_id=user.id,membership_id=membership.id,tenant_id=membership.tenant_id,expires_at=_utcnow()+timedelta(hours=get_settings().session_ttl_hours)))
    db.commit(); return raw
def revoke_session(db: Session,raw: str):
    token=db.scalar(select(SessionToken).where(SessionToken.token_hash==hashlib.sha256(raw.encode()).hexdigest()))
    if token: db.delete(token); db.commit()
def context_from_token(db: Session,raw: str)->AuthContext:
    token=db.scalar(select(SessionToken).where(SessionToken.token_hash==hashlib.sha256(raw.encode()).hexdigest()))
    if not token or token.expires_at<=_utcnow(): raise HTTPException(401,"Sessão inválida ou expirada")
    user=db.get(User,token.user_id); membership=db.get(Membership,token.membership_id); tenant=db.get(Tenant,token.tenant_id)
    if not user or not user.active or not membership or not membership.active or not tenant or not tenant.active: raise HTTPException(401,"Acesso inativo")
    if membership.user_id!=user.id or membership.tenant_id!=tenant.id: raise HTTPException(401,"Sessão inconsistente")
    activate_tenant_scope(db,tenant.id); return AuthContext(user,membership,tenant)
def current_context(credentials: Annotated[HTTPAuthorizationCredentials|None,Depends(bearer)],db: Annotated[Session,Depends(get_db)]):
    if not credentials: raise HTTPException(401,"Autenticação necessária")
    return context_from_token(db,credentials.credentials)
def require_permissions(*required: Permission):
    def dependency(context: Annotated[AuthContext,Depends(current_context)]):
        missing=set(required)-context.permissions
        if missing: raise HTTPException(status.HTTP_403_FORBIDDEN,{"message":"Permissão insuficiente","missing":sorted(x.value for x in missing)})
        return context
    return dependency
