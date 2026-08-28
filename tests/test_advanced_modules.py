from __future__ import annotations

from datetime import date, timedelta

from app.database import SessionLocal
from app.models import Employee, EmploymentStatus, Membership, Role, Subscription, SubscriptionStatus, User


def create_application(client, headers):
    candidate = client.post(
        "/api/candidates",
        headers=headers,
        json={
            "name": "Maria Candidata",
            "profession": "Enfermeira",
            "city": "Campinas",
            "professional_registry": "COREN-321",
            "phone": "19999999999",
            "email": "maria@example.com",
            "source": "Portal",
            "source_url": "",
            "status": "Novo",
            "notes": "",
        },
    ).json()
    vacancy = client.post(
        "/api/vacancies",
        headers=headers,
        json={
            "code": "V-001",
            "title": "Enfermagem assistencial",
            "profession": "Enfermeira",
            "city": "Campinas",
            "positions": 1,
            "status": "aberta",
            "description": "Atendimento domiciliar",
        },
    ).json()
    return client.post(
        "/api/applications",
        headers=headers,
        json={
            "candidate_id": candidate["id"],
            "vacancy_id": vacancy["id"],
            "stage": "Inscrito",
            "score": None,
            "notes": "",
        },
    ).json()


def create_employee(identity, *, user_id=None, number="EMP-001", manager_id=None):
    with SessionLocal() as db:
        employee = Employee(
            tenant_id=identity["tenant_id"],
            user_id=user_id,
            employee_number=number,
            full_name=f"Colaborador {number}",
            job_title="Analista",
            status=EmploymentStatus.ativo,
            manager_id=manager_id,
        )
        db.add(employee)
        db.commit()
        return employee.id


def test_ats_requisition_stage_history_interview_and_offer(client, identity_factory, login):
    owner = identity_factory()
    headers = login(owner)

    requisition = client.post(
        "/api/ats/requisitions",
        headers=headers,
        json={"code": "REQ-001", "title": "Nova posição", "positions": 2, "description": "Expansão"},
    )
    assert requisition.status_code == 201, requisition.text
    decided = client.post(
        f"/api/ats/requisitions/{requisition.json()['id']}/decision",
        headers=headers,
        json={"approved": True, "reason": "Headcount aprovado"},
    )
    assert decided.json()["status"] == "approved"

    application = create_application(client, headers)
    transition = client.post(
        f"/api/ats/applications/{application['id']}/stage",
        headers=headers,
        json={"stage": "Entrevista", "reason": "Triagem concluída"},
    )
    assert transition.status_code == 200, transition.text
    assert transition.json()["from_stage"] == "Inscrito"
    assert transition.json()["to_stage"] == "Entrevista"
    history = client.get(f"/api/ats/applications/{application['id']}/history", headers=headers).json()
    assert len(history) == 1

    interview = client.post(
        "/api/ats/interviews",
        headers=headers,
        json={
            "application_id": application["id"],
            "scheduled_at": "2026-09-02T14:00:00Z",
            "duration_minutes": 45,
            "location": "Google Meet",
            "interviewer_ids": [owner["user_id"]],
            "notes": "Entrevista técnica",
        },
    )
    assert interview.status_code == 201, interview.text
    scorecard = client.post(
        f"/api/ats/interviews/{interview.json()['id']}/scorecards",
        headers=headers,
        json={
            "overall_score": 5,
            "recommendation": "strong_yes",
            "criteria": {"técnica": 5, "comunicação": 4},
            "feedback": "Aderente",
        },
    )
    assert scorecard.status_code == 201, scorecard.text

    offer = client.post(
        "/api/ats/offers",
        headers=headers,
        json={"application_id": application["id"], "salary": "6500.00", "currency": "BRL"},
    )
    assert offer.status_code == 201, offer.text
    accepted = client.patch(
        f"/api/ats/offers/{offer.json()['id']}/status",
        headers=headers,
        json={"status": "accepted", "reason": "Aceite eletrônico"},
    )
    assert accepted.json()["status"] == "accepted"
    applications = client.get("/api/applications", headers=headers).json()
    assert applications[0]["stage"] == "Contratado"


def test_contracts_and_movements_are_tenant_scoped(client, identity_factory, login):
    company_a = identity_factory(slug="contratos-a")
    company_b = identity_factory(slug="contratos-b")
    employee_a = create_employee(company_a)
    headers_a = login(company_a)
    headers_b = login(company_b)

    contract = client.post(
        "/api/core-hr/contracts",
        headers=headers_a,
        json={
            "employee_id": employee_a,
            "contract_number": "CT-001",
            "contract_type": "clt",
            "start_date": "2026-09-01",
            "weekly_hours": "44.00",
            "salary": "5000.00",
            "currency": "BRL",
            "status": "active",
        },
    )
    assert contract.status_code == 201, contract.text
    movement = client.post(
        "/api/core-hr/movements",
        headers=headers_a,
        json={
            "employee_id": employee_a,
            "movement_type": "promotion",
            "effective_date": "2026-10-01",
            "reason": "Mérito",
            "before_data": {"cargo": "Analista"},
            "after_data": {"cargo": "Analista Sênior"},
        },
    )
    assert movement.status_code == 201, movement.text
    assert client.get("/api/core-hr/contracts", headers=headers_b).json() == []
    assert client.get("/api/core-hr/movements", headers=headers_b).json() == []


def test_employee_performance_scope_excludes_other_employee(client, identity_factory, login, password_hash):
    owner = identity_factory(slug="performance-company")
    with SessionLocal() as db:
        employee_user = User(
            username="colaborador.scope",
            display_name="Colaborador Scope",
            email="scope@example.com",
            password_hash=password_hash,
        )
        db.add(employee_user)
        db.flush()
        db.add(Membership(tenant_id=owner["tenant_id"], user_id=employee_user.id, role=Role.employee))
        db.commit()
        employee_identity = {
            "tenant_id": owner["tenant_id"],
            "user_id": employee_user.id,
            "username": employee_user.username,
            "slug": owner["slug"],
        }
    own_employee_id = create_employee(owner, user_id=employee_identity["user_id"], number="OWN-001")
    other_employee_id = create_employee(owner, number="OTHER-001")
    owner_headers = login(owner)
    employee_headers = login(employee_identity)

    cycle = client.post(
        "/api/performance/cycles",
        headers=owner_headers,
        json={
            "name": "Avaliação 2026",
            "start_date": "2026-09-01",
            "end_date": "2026-12-01",
            "description": "Ciclo anual",
        },
    ).json()
    for employee_id, title in ((own_employee_id, "Minha meta"), (other_employee_id, "Meta confidencial")):
        response = client.post(
            "/api/performance/goals",
            headers=owner_headers,
            json={
                "cycle_id": cycle["id"],
                "employee_id": employee_id,
                "title": title,
                "target_value": "100%",
            },
        )
        assert response.status_code == 201, response.text

    own_goals = client.get("/api/performance/goals", headers=employee_headers)
    assert own_goals.status_code == 200
    assert [goal["title"] for goal in own_goals.json()] == ["Minha meta"]
    forbidden = client.get(
        f"/api/performance/goals?employee_id={other_employee_id}",
        headers=employee_headers,
    )
    assert forbidden.status_code == 403


def test_esocial_idempotency_and_state_machine(client, identity_factory, login):
    owner = identity_factory()
    headers = login(owner)
    payload = {
        "event_type": "S-2200",
        "reference": "ADM-001",
        "layout_version": "S-1.3",
        "idempotency_key": "S-2200:ADM-001:2026-09",
        "payload": {"trabalhador": {"matricula": "ADM-001"}},
    }
    created = client.post("/api/esocial/events", headers=headers, json=payload)
    assert created.status_code == 201, created.text
    assert client.post("/api/esocial/events", headers=headers, json=payload).status_code == 409

    event_id = created.json()["id"]
    invalid = client.patch(
        f"/api/esocial/events/{event_id}",
        headers=headers,
        json={"status": "sent"},
    )
    assert invalid.status_code == 409
    for target in ("validated", "queued", "sent"):
        response = client.patch(
            f"/api/esocial/events/{event_id}",
            headers=headers,
            json={"status": target, "receipt": ""},
        )
        assert response.status_code == 200, response.text
    missing_receipt = client.patch(
        f"/api/esocial/events/{event_id}", headers=headers, json={"status": "accepted"}
    )
    assert missing_receipt.status_code == 422
    response = client.patch(
        f"/api/esocial/events/{event_id}",
        headers=headers,
        json={"status": "accepted", "receipt": "REC-001"},
    )
    assert response.status_code == 200, response.text
    assert response.json()["attempts"] == 1


def test_billing_summary_usage_and_invoices(client, identity_factory, login):
    owner = identity_factory()
    with SessionLocal() as db:
        db.add(
            Subscription(
                tenant_id=owner["tenant_id"],
                plan_code="professional",
                status=SubscriptionStatus.active,
                employee_limit=100,
                enabled_modules=["ats", "core_hr", "performance"],
            )
        )
        db.commit()
    headers = login(owner)
    usage = client.put(
        "/api/billing/usage",
        headers=headers,
        json={"metric": "employees", "period": "2026-08", "quantity": 42},
    )
    assert usage.status_code == 200, usage.text
    invoice = client.post(
        "/api/billing/invoices",
        headers=headers,
        json={
            "number": "INV-2026-08",
            "period": "2026-08",
            "amount": "999.00",
            "currency": "BRL",
            "due_date": str(date.today() + timedelta(days=10)),
        },
    )
    assert invoice.status_code == 201, invoice.text
    opened = client.patch(
        f"/api/billing/invoices/{invoice.json()['id']}",
        headers=headers,
        json={"status": "open", "provider_reference": "gateway_123"},
    )
    assert opened.status_code == 200
    summary = client.get("/api/billing/summary", headers=headers)
    assert summary.status_code == 200, summary.text
    assert summary.json()["usage"][0]["quantity"] == 42
    assert summary.json()["open_invoices"][0]["number"] == "INV-2026-08"
