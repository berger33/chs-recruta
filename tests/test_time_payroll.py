from __future__ import annotations

from datetime import date

from app.database import SessionLocal
from app.models import Employee, EmploymentStatus, Membership, Role, User


def add_employee(
    identity,
    password_hash,
    *,
    suffix: str,
    role: Role = Role.employee,
    manager_id: int | None = None,
):
    with SessionLocal() as db:
        user = User(
            username=f"tp-{suffix}-{identity['tenant_id']}",
            display_name=f"Pessoa {suffix}",
            email=f"tp-{suffix}-{identity['tenant_id']}@example.com",
            password_hash=password_hash,
        )
        db.add(user)
        db.flush()
        db.add(Membership(tenant_id=identity["tenant_id"], user_id=user.id, role=role))
        employee = Employee(
            tenant_id=identity["tenant_id"],
            user_id=user.id,
            manager_id=manager_id,
            employee_number=f"TP-{suffix.upper()}",
            full_name=f"Pessoa {suffix}",
            job_title="Analista",
            status=EmploymentStatus.ativo,
            hire_date=date(2026, 1, 1),
        )
        db.add(employee)
        db.commit()
        return {
            "tenant_id": identity["tenant_id"],
            "user_id": user.id,
            "employee_id": employee.id,
            "employee_number": employee.employee_number,
            "username": user.username,
            "slug": identity["slug"],
        }


def mark(client, identity, login, recorded_at, kind):
    response = client.post(
        "/api/time-entries",
        headers=login(identity),
        json={
            "employee_id": identity["employee_id"],
            "kind": kind,
            "recorded_at": recorded_at,
            "source": "manual",
            "note": "",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_manager_time_scope_is_limited_to_direct_reports(
    client, identity_factory, login, password_hash
):
    owner = identity_factory(slug="time-scope")
    manager = add_employee(owner, password_hash, suffix="manager", role=Role.manager)
    report = add_employee(
        owner, password_hash, suffix="report", manager_id=manager["employee_id"]
    )
    outsider = add_employee(owner, password_hash, suffix="outsider")
    report_entry = mark(client, report, login, "2026-08-10T08:00:00", "entrada")
    mark(client, outsider, login, "2026-08-10T09:00:00", "entrada")

    manager_headers = login(manager)
    visible = client.get("/api/time-entries", headers=manager_headers).json()
    assert [entry["id"] for entry in visible] == [report_entry["id"]]
    hidden = client.get(
        "/api/time-entries",
        headers=manager_headers,
        params={"employee_id": outsider["employee_id"]},
    )
    assert hidden.status_code == 404
    forge = client.post(
        "/api/time-entries",
        headers=manager_headers,
        json={
            "employee_id": report["employee_id"],
            "kind": "saida",
            "recorded_at": "2026-08-10T17:00:00",
            "source": "manual",
            "note": "",
        },
    )
    assert forge.status_code == 403


def test_adjustment_preserves_raw_entry_and_versions_locked_timesheet(
    client, identity_factory, login, password_hash
):
    owner = identity_factory(slug="time-adjustment")
    manager = add_employee(owner, password_hash, suffix="lead", role=Role.manager)
    employee = add_employee(
        owner, password_hash, suffix="worker", manager_id=manager["employee_id"]
    )
    entry = mark(client, employee, login, "2026-08-12T08:00:00", "entrada")
    exit_entry = mark(client, employee, login, "2026-08-12T17:00:00", "saida")
    employee_headers = login(employee)
    requested = client.post(
        "/api/time-management/adjustment-requests",
        headers=employee_headers,
        json={
            "action": "replace",
            "original_entry_id": exit_entry["id"],
            "requested_kind": "saida",
            "requested_at": "2026-08-12T16:30:00",
            "reason": "Horário de saída registrado incorretamente",
        },
    )
    assert requested.status_code == 201, requested.text
    approved = client.post(
        f"/api/time-management/adjustment-requests/{requested.json()['id']}/decision",
        headers=login(manager),
        json={"approved": True, "review_notes": "Evidência conferida"},
    )
    assert approved.status_code == 200, approved.text

    raw = client.get("/api/time-entries", headers=employee_headers).json()
    assert {item["id"]: item["recorded_at"] for item in raw}[exit_entry["id"]].startswith(
        "2026-08-12T17:00:00"
    )
    effective = client.get(
        "/api/time-management/effective-entries",
        headers=employee_headers,
        params={
            "employee_id": employee["employee_id"],
            "start_at": "2026-08-01T00:00:00",
            "end_at": "2026-08-31T23:59:59",
        },
    ).json()
    assert [(item["source_type"], item["recorded_at"][:16]) for item in effective] == [
        ("raw", "2026-08-12T08:00"),
        ("adjustment", "2026-08-12T16:30"),
    ]
    assert effective[0]["source_id"] == entry["id"]

    owner_headers = login(owner)
    timesheet = client.post(
        "/api/time-management/timesheets/calculate",
        headers=owner_headers,
        json={"employee_id": employee["employee_id"], "competence": "2026-08"},
    )
    assert timesheet.status_code == 200, timesheet.text
    assert timesheet.json()["summary"]["worked_minutes"] == 510
    timesheet_id = timesheet.json()["id"]
    assert client.patch(
        f"/api/time-management/timesheets/{timesheet_id}",
        headers=employee_headers,
        json={"status": "submitted"},
    ).status_code == 200
    assert client.patch(
        f"/api/time-management/timesheets/{timesheet_id}",
        headers=login(manager),
        json={"status": "approved"},
    ).status_code == 200
    locked = client.patch(
        f"/api/time-management/timesheets/{timesheet_id}",
        headers=owner_headers,
        json={"status": "locked"},
    )
    assert locked.status_code == 200, locked.text
    assert len(locked.json()["integrity_hash"]) == 64

    version_two = client.post(
        "/api/time-management/timesheets/calculate",
        headers=owner_headers,
        json={"employee_id": employee["employee_id"], "competence": "2026-08"},
    )
    assert version_two.status_code == 200, version_two.text
    assert version_two.json()["version"] == 2
    assert version_two.json()["supersedes_id"] == timesheet_id


def test_employee_can_cancel_only_own_pending_adjustment(
    client, identity_factory, login, password_hash
):
    company = identity_factory(slug="time-cancel")
    employee = add_employee(company, password_hash, suffix="cancel-own")
    other = add_employee(company, password_hash, suffix="cancel-other")
    requested = client.post(
        "/api/time-management/adjustment-requests",
        headers=login(employee),
        json={
            "action": "add",
            "requested_kind": "entrada",
            "requested_at": "2026-08-15T08:00:00-03:00",
            "reason": "Esqueci de registrar a entrada no início da jornada",
        },
    )
    assert requested.status_code == 201, requested.text
    request_id = requested.json()["id"]
    hidden = client.post(
        f"/api/time-management/adjustment-requests/{request_id}/cancel",
        headers=login(other),
    )
    assert hidden.status_code == 404
    cancelled = client.post(
        f"/api/time-management/adjustment-requests/{request_id}/cancel",
        headers=login(employee),
    )
    assert cancelled.status_code == 200, cancelled.text
    assert cancelled.json()["status"] == "cancelled"
    repeated = client.post(
        f"/api/time-management/adjustment-requests/{request_id}/cancel",
        headers=login(employee),
    )
    assert repeated.status_code == 409


def test_schedule_periods_cannot_overlap(client, identity_factory, login, password_hash):
    owner = identity_factory(slug="schedule-period")
    employee = add_employee(owner, password_hash, suffix="scheduled")
    headers = login(owner)
    schedule = client.post(
        "/api/time-management/schedules",
        headers=headers,
        json={
            "name": "Comercial 44h",
            "timezone": "America/Sao_Paulo",
            "weekly_minutes": 2640,
            "break_minutes": 60,
            "tolerance_minutes": 10,
            "active": True,
        },
    )
    assert schedule.status_code == 201, schedule.text
    assignment = {
        "employee_id": employee["employee_id"],
        "schedule_id": schedule.json()["id"],
        "effective_from": "2026-01-01",
        "effective_to": "2026-12-31",
    }
    assert client.post(
        "/api/time-management/employee-schedules", headers=headers, json=assignment
    ).status_code == 201
    overlap = client.post(
        "/api/time-management/employee-schedules",
        headers=headers,
        json={**assignment, "effective_from": "2026-06-01", "effective_to": None},
    )
    assert overlap.status_code == 409


def test_payroll_batch_is_idempotent_reconciled_and_private(
    client, identity_factory, login, password_hash
):
    company = identity_factory(slug="payroll-private")
    employee_a = add_employee(company, password_hash, suffix="pay-a")
    employee_b = add_employee(company, password_hash, suffix="pay-b")
    owner_headers = login(company)
    payload = {
        "competence": "2026-08",
        "source": "folha-exemplo",
        "idempotency_key": "payroll:2026-08:v1",
        "rows": [
            {
                "employee_number": employee_a["employee_number"],
                "gross_amount": 5000,
                "deduction_amount": 1000,
                "net_amount": 4000,
                "currency": "BRL",
                "filename": "holerite-a.pdf",
                "storage_key": "private/2026-08/a.pdf",
                "checksum": "a" * 64,
            },
            {
                "employee_number": employee_b["employee_number"],
                "gross_amount": 3000,
                "deduction_amount": 500,
                "net_amount": 2500,
                "currency": "BRL",
                "filename": "holerite-b.pdf",
                "storage_key": "private/2026-08/b.pdf",
                "checksum": "b" * 64,
            },
        ],
    }
    batch = client.post("/api/payroll/batches", headers=owner_headers, json=payload)
    assert batch.status_code == 201, batch.text
    assert batch.json()["total_net"] == "6500.00"
    assert client.post(
        "/api/payroll/batches", headers=owner_headers, json=payload
    ).status_code == 409
    batch_id = batch.json()["id"]
    assert client.patch(
        f"/api/payroll/batches/{batch_id}",
        headers=owner_headers,
        json={"status": "validated"},
    ).status_code == 200
    assert client.get(
        "/api/payroll/statements", headers=login(employee_a)
    ).json() == []
    published = client.patch(
        f"/api/payroll/batches/{batch_id}",
        headers=owner_headers,
        json={"status": "published"},
    )
    assert published.status_code == 200, published.text
    own_a = client.get("/api/payroll/statements", headers=login(employee_a)).json()
    own_b = client.get("/api/payroll/statements", headers=login(employee_b)).json()
    assert [item["filename"] for item in own_a] == ["holerite-a.pdf"]
    assert [item["filename"] for item in own_b] == ["holerite-b.pdf"]

    other_company = identity_factory(slug="payroll-other")
    cross_tenant_payload = {
        **payload,
        "idempotency_key": "payroll:2026-08:other",
    }
    rejected = client.post(
        "/api/payroll/batches",
        headers=login(other_company),
        json=cross_tenant_payload,
    )
    assert rejected.status_code == 422
