from __future__ import annotations
import os
os.environ["DATABASE_URL"]="sqlite://"; os.environ["AUTO_CREATE_SCHEMA"]="true"; os.environ["APP_ENV"]="test"
import pytest
from fastapi.testclient import TestClient
from app.database import Base,SessionLocal,engine
from app.main import app
from app.models import Membership,Role,Tenant,User
from app.security import hash_password
@pytest.fixture(autouse=True)
def clean_database():
    Base.metadata.drop_all(bind=engine); Base.metadata.create_all(bind=engine); yield; Base.metadata.drop_all(bind=engine)
@pytest.fixture
def client():
    with TestClient(app) as value: yield value
@pytest.fixture(scope="session")
def password_hash(): return hash_password("senha12345")
@pytest.fixture
def identity_factory(password_hash):
    counter=0
    def create(*,role=Role.tenant_owner,slug=None):
        nonlocal counter; counter+=1; suffix=slug or f"empresa-{counter}"
        with SessionLocal() as db:
            tenant=Tenant(name=f"Empresa {counter}",slug=suffix); user=User(username=f"usuario{counter}",display_name=f"Usuário {counter}",email=f"usuario{counter}@example.com",password_hash=password_hash)
            db.add_all([tenant,user]); db.flush(); db.add(Membership(tenant_id=tenant.id,user_id=user.id,role=role)); db.commit()
            return {"tenant_id":tenant.id,"user_id":user.id,"username":user.username,"slug":suffix}
    return create
@pytest.fixture
def login(client):
    def authenticate(identity):
        response=client.post("/api/auth/login",json={"identifier":identity["username"],"password":"senha12345","tenant_slug":identity["slug"]})
        assert response.status_code==200,response.text
        return {"Authorization":"Bearer "+response.json()["token"]}
    return authenticate
