from __future__ import annotations
from collections.abc import Generator
from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.pool import StaticPool
from .config import get_settings

settings=get_settings()
connect_args={"check_same_thread":False} if settings.database_url.startswith("sqlite") else {}
kwargs={"pool_pre_ping":True,"connect_args":connect_args}
if settings.database_url in {"sqlite://","sqlite:///:memory:"}: kwargs["poolclass"]=StaticPool
engine=create_engine(settings.database_url,**kwargs)
SessionLocal=sessionmaker(bind=engine,autoflush=False,expire_on_commit=False)
class Base(DeclarativeBase): pass

def get_db() -> Generator[Session,None,None]:
    db=SessionLocal()
    try: yield db
    finally: db.close()

def activate_tenant_scope(db: Session, tenant_id: int) -> None:
    if db.bind is not None and db.bind.dialect.name=="postgresql":
        db.execute(text("SELECT set_config('app.current_tenant_id', :tenant_id, true)"),{"tenant_id":str(tenant_id)})
