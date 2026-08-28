from __future__ import annotations
from datetime import UTC,datetime
from app.database import SessionLocal
from app.models import Employee,EmploymentStatus,KnowledgeDocument,KnowledgeVisibility,PayrollDocument,Role

def candidate_payload(name="Ana Silva"):
    return {"name":name,"profession":"psicologa","city":"São Paulo","professional_registry":"CRP-123","phone":"11999999999","email":"ana@example.com","source":"Indicação","source_url":"","status":"Novo","notes":"Disponível"}

def test_health_frontend_and_security_headers(client):
    response=client.get("/health"); assert response.status_code==200
    assert response.json()=={"status":"ok","service":"chs-rh","version":"3.0.0"}
    assert response.headers["x-content-type-options"]=="nosniff"; assert response.headers["x-request-id"]
    assert "Toda a rotina de RH" in client.get("/").text; assert client.get("/docs").status_code==200

def test_authentication_is_required(client):
    assert client.get("/api/candidates").status_code==401; assert client.get("/api/audit").status_code==401

def test_candidate_crud_creates_structured_audit(client,identity_factory,login):
    owner=identity_factory(); headers=login(owner)
    created=client.post("/api/candidates",json=candidate_payload(),headers=headers)
    assert created.status_code==201,created.text; assert created.json()["profession"]=="Psicólogo"
    assert [x["name"] for x in client.get("/api/candidates?q=ana",headers=headers).json()]==["Ana Silva"]
    event=client.get("/api/audit?entity=candidate",headers=headers).json()[0]
    assert event["action"]=="create"; assert event["actor"]==owner["username"]; assert event["after_data"]["name"]=="Ana Silva"; assert event["request_id"]

def test_tenant_data_isolation(client,identity_factory,login):
    a=identity_factory(slug="empresa-a"); b=identity_factory(slug="empresa-b"); ha=login(a); hb=login(b)
    candidate=client.post("/api/candidates",json=candidate_payload(),headers=ha).json()
    assert client.get("/api/candidates",headers=hb).json()==[]
    assert client.get("/api/candidates/"+str(candidate["id"]),headers=hb).status_code==404

def test_role_permissions_deny_employee_ats(client,identity_factory,login):
    employee=identity_factory(role=Role.employee); response=client.get("/api/candidates",headers=login(employee))
    assert response.status_code==403; assert response.json()["detail"]["missing"]==["candidates.read"]

def test_tutorial_preference_persists(client,identity_factory,login):
    owner=identity_factory(); headers=login(owner)
    state=client.get("/api/auth/me",headers=headers).json()["tutorial"]
    assert state["should_show"] is True
    updated=client.put("/api/tenants/tutorial",json={"completed":True,"dismissed":False,"version":state["current_version"]},headers=headers)
    assert updated.status_code==200; assert updated.json()["dismissed"] is False; assert updated.json()["should_show"] is False
    assert client.get("/api/auth/me",headers=headers).json()["tutorial"]["should_show"] is False
    other=identity_factory(slug="tutorial-dismissed"); other_headers=login(other)
    updated=client.put("/api/tenants/tutorial",json={"completed":False,"dismissed":True,"version":state["current_version"]},headers=other_headers)
    assert updated.status_code==200; assert updated.json()["dismissed"] is True; assert updated.json()["should_show"] is False
    assert client.get("/api/auth/me",headers=other_headers).json()["tutorial"]["should_show"] is False

def test_employee_sees_only_own_payroll_and_time(client,identity_factory,login):
    identity=identity_factory(role=Role.employee)
    with SessionLocal() as db:
        own=Employee(tenant_id=identity["tenant_id"],user_id=identity["user_id"],employee_number="001",full_name="Colaborador Um",status=EmploymentStatus.ativo)
        other=Employee(tenant_id=identity["tenant_id"],employee_number="002",full_name="Colaborador Dois",status=EmploymentStatus.ativo)
        db.add_all([own,other]); db.flush(); db.add_all([PayrollDocument(tenant_id=identity["tenant_id"],employee_id=own.id,competence="2026-08",filename="meu.pdf"),PayrollDocument(tenant_id=identity["tenant_id"],employee_id=other.id,competence="2026-08",filename="outro.pdf")]); db.commit(); own_id,other_id=own.id,other.id
    headers=login(identity); docs=client.get("/api/payroll-documents",headers=headers)
    assert [x["filename"] for x in docs.json()]==["meu.pdf"]
    assert client.get("/api/payroll-documents?employee_id="+str(other_id),headers=headers).status_code==403
    entry=client.post("/api/time-entries",json={"employee_id":own_id,"kind":"entrada","recorded_at":datetime.now(UTC).isoformat(),"source":"test","note":""},headers=headers)
    assert entry.status_code==201,entry.text; assert len(entry.json()["integrity_hash"])==64
    denied=client.post("/api/time-entries",json={"employee_id":other_id,"kind":"entrada","recorded_at":datetime.now(UTC).isoformat(),"source":"test","note":""},headers=headers)
    assert denied.status_code==403

def test_knowledge_acl_and_abstention(client,identity_factory,login):
    identity=identity_factory(role=Role.employee)
    with SessionLocal() as db:
        db.add_all([KnowledgeDocument(tenant_id=identity["tenant_id"],title="Política de férias",content="As férias devem ser solicitadas no portal com trinta dias de antecedência.",visibility=KnowledgeVisibility.todos),KnowledgeDocument(tenant_id=identity["tenant_id"],title="Política confidencial de salários",content="A tabela salarial confidencial usa faixas internas exclusivas do RH.",visibility=KnowledgeVisibility.rh)]); db.commit()
    headers=login(identity); grounded=client.post("/api/knowledge/ask",json={"question":"Como solicito férias?"},headers=headers).json()
    assert grounded["grounded"] is True; assert grounded["citations"][0]["title"]=="Política de férias"
    protected=client.post("/api/knowledge/ask",json={"question":"Qual é a tabela salarial?"},headers=headers).json()
    assert protected["grounded"] is False; assert protected["citations"]==[]
