from __future__ import annotations

from app.database import SessionLocal
from app.models import AuditLog, Employee, EmploymentStatus, Membership, Role, User


def add_employee(identity, password_hash, *, suffix: str, role: Role, manager_id: int | None = None):
    with SessionLocal() as db:
        user = User(
            username=f"{suffix}-{identity['tenant_id']}",
            display_name=f"Pessoa {suffix}",
            email=f"{suffix}-{identity['tenant_id']}@example.com",
            password_hash=password_hash,
        )
        db.add(user)
        db.flush()
        db.add(Membership(tenant_id=identity["tenant_id"], user_id=user.id, role=role))
        employee = Employee(
            tenant_id=identity["tenant_id"],
            user_id=user.id,
            manager_id=manager_id,
            employee_number=f"EMP-{suffix.upper()}",
            full_name=f"Pessoa {suffix}",
            job_title="Analista",
            status=EmploymentStatus.ativo,
        )
        db.add(employee)
        db.commit()
        return {
            "tenant_id": identity["tenant_id"],
            "user_id": user.id,
            "employee_id": employee.id,
            "username": user.username,
            "slug": identity["slug"],
        }


def test_employee_requests_are_private_and_audited(client, identity_factory, login, password_hash):
    owner = identity_factory(slug="portal-private")
    employee = add_employee(owner, password_hash, suffix="employee", role=Role.employee)
    coworker = add_employee(owner, password_hash, suffix="coworker", role=Role.employee)
    headers = login(employee)

    created = client.post(
        "/api/portal/requests",
        headers=headers,
        json={
            "category": "cadastro",
            "subject": "Atualização de endereço",
            "description": "Solicito atualização cadastral.",
            "priority": "normal",
        },
    )
    assert created.status_code == 201, created.text
    assert created.json()["employee_id"] == employee["employee_id"]

    forbidden = client.post(
        "/api/portal/requests",
        headers=headers,
        json={
            "employee_id": coworker["employee_id"],
            "category": "cadastro",
            "subject": "Solicitação indevida",
            "priority": "normal",
        },
    )
    assert forbidden.status_code == 403
    assert len(client.get("/api/portal/requests", headers=headers).json()) == 1

    on_behalf = client.post(
        "/api/portal/requests",
        headers=login(owner),
        json={
            "employee_id": coworker["employee_id"],
            "category": "documentos",
            "subject": "Entrega de comprovante",
            "priority": "normal",
        },
    )
    assert on_behalf.status_code == 201, on_behalf.text
    assert on_behalf.json()["employee_id"] == coworker["employee_id"]

    cancelled = client.patch(
        f"/api/portal/requests/{created.json()['id']}",
        headers=headers,
        json={"status": "cancelled", "resolution": "Não é mais necessário"},
    )
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "cancelled"
    with SessionLocal() as db:
        events = db.query(AuditLog).filter_by(
            tenant_id=owner["tenant_id"], entity="employee_request"
        ).all()
        assert [event.action for event in events].count("submit") == 2
        assert [event.action for event in events].count("transition") == 1


def test_manager_can_decide_only_direct_reports(client, identity_factory, login, password_hash):
    owner = identity_factory(slug="portal-team")
    manager = add_employee(owner, password_hash, suffix="manager", role=Role.manager)
    report = add_employee(
        owner,
        password_hash,
        suffix="report",
        role=Role.employee,
        manager_id=manager["employee_id"],
    )
    outsider = add_employee(owner, password_hash, suffix="outsider", role=Role.employee)
    report_headers = login(report)
    outsider_headers = login(outsider)
    manager_headers = login(manager)

    leave = client.post(
        "/api/portal/leave-requests",
        headers=report_headers,
        json={
            "leave_type": "ferias",
            "start_date": "2026-10-01",
            "end_date": "2026-10-10",
            "reason": "Período planejado",
        },
    )
    assert leave.status_code == 201, leave.text
    assert leave.json()["total_days"] == 10

    overlap = client.post(
        "/api/portal/leave-requests",
        headers=report_headers,
        json={
            "leave_type": "folga",
            "start_date": "2026-10-08",
            "end_date": "2026-10-11",
        },
    )
    assert overlap.status_code == 409

    outsider_leave = client.post(
        "/api/portal/leave-requests",
        headers=outsider_headers,
        json={
            "leave_type": "ferias",
            "start_date": "2026-11-01",
            "end_date": "2026-11-02",
        },
    ).json()
    visible = client.get("/api/portal/leave-requests", headers=manager_headers).json()
    assert [item["id"] for item in visible] == [leave.json()["id"]]

    hidden = client.patch(
        f"/api/portal/leave-requests/{outsider_leave['id']}",
        headers=manager_headers,
        json={"status": "approved", "decision_notes": "fora da equipe"},
    )
    assert hidden.status_code == 404
    approved = client.patch(
        f"/api/portal/leave-requests/{leave.json()['id']}",
        headers=manager_headers,
        json={"status": "approved", "decision_notes": "Escala conferida"},
    )
    assert approved.status_code == 200, approved.text
    assert approved.json()["status"] == "approved"


def test_employee_files_visibility_and_tenant_isolation(client, identity_factory, login, password_hash):
    company_a = identity_factory(slug="portal-files-a")
    company_b = identity_factory(slug="portal-files-b")
    employee = add_employee(company_a, password_hash, suffix="files", role=Role.employee)
    owner_a_headers = login(company_a)
    employee_headers = login(employee)
    owner_b_headers = login(company_b)

    base = {
        "employee_id": employee["employee_id"],
        "category": "contrato",
        "filename": "contrato.pdf",
        "storage_key": "tenant-a/employee/contrato.pdf",
        "checksum": "a" * 64,
        "mime_type": "application/pdf",
        "visibility": "employee",
    }
    published = client.post("/api/portal/files", headers=owner_a_headers, json=base)
    assert published.status_code == 201, published.text
    internal = client.post(
        "/api/portal/files",
        headers=owner_a_headers,
        json={
            **base,
            "filename": "analise-interna.pdf",
            "storage_key": "tenant-a/hr/analise-interna.pdf",
            "visibility": "hr_only",
        },
    )
    assert internal.status_code == 201, internal.text

    employee_files = client.get("/api/portal/files", headers=employee_headers).json()
    assert [item["filename"] for item in employee_files] == ["contrato.pdf"]
    assert len(client.get("/api/portal/files", headers=owner_a_headers).json()) == 2

    cross_tenant = client.post("/api/portal/files", headers=owner_b_headers, json=base)
    assert cross_tenant.status_code == 404
