from __future__ import annotations

from datetime import date

from app.database import SessionLocal
from app.models import Employee, EmploymentStatus, Membership, OnboardingTask, Role, User


def add_employee(
    identity,
    password_hash,
    *,
    suffix: str,
    role: Role = Role.employee,
    hire_date: date | None = None,
    manager_id: int | None = None,
):
    with SessionLocal() as db:
        user = User(
            username=f"wf-{suffix}-{identity['tenant_id']}",
            display_name=f"Pessoa {suffix}",
            email=f"wf-{suffix}-{identity['tenant_id']}@example.com",
            password_hash=password_hash,
        )
        db.add(user)
        db.flush()
        db.add(Membership(tenant_id=identity["tenant_id"], user_id=user.id, role=role))
        employee = Employee(
            tenant_id=identity["tenant_id"],
            user_id=user.id,
            manager_id=manager_id,
            employee_number=f"WF-{suffix.upper()}",
            full_name=f"Pessoa {suffix}",
            job_title="Analista",
            status=EmploymentStatus.ativo,
            hire_date=hire_date,
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


def create_plan(client, headers, name="Plano Saúde"):
    response = client.post(
        "/api/benefits",
        headers=headers,
        json={
            "name": name,
            "category": "saude",
            "provider": "Operadora Exemplo",
            "employee_cost": 120,
            "active": True,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_onboarding_template_application_is_idempotent_and_assigns_roles(
    client, identity_factory, login, password_hash
):
    owner = identity_factory(slug="onboarding-template")
    manager = add_employee(owner, password_hash, suffix="manager", role=Role.manager)
    employee = add_employee(
        owner,
        password_hash,
        suffix="new-hire",
        hire_date=date(2026, 9, 1),
        manager_id=manager["employee_id"],
    )
    headers = login(owner)
    template = client.post(
        "/api/workforce/onboarding/templates",
        headers=headers,
        json={
            "name": "Admissão padrão",
            "description": "Checklist corporativo",
            "active": True,
            "items": [
                {
                    "title": "Confirmar dados",
                    "description": "Revise o cadastro.",
                    "due_offset_days": -1,
                    "assigned_role": "employee",
                    "position": 1,
                    "required": True,
                },
                {
                    "title": "Reunião de boas-vindas",
                    "description": "Apresente a equipe.",
                    "due_offset_days": 2,
                    "assigned_role": "manager",
                    "position": 2,
                    "required": True,
                },
            ],
        },
    )
    assert template.status_code == 201, template.text
    assert len(template.json()["items"]) == 2

    applied = client.post(
        f"/api/workforce/onboarding/templates/{template.json()['id']}/apply",
        headers=headers,
        json={"employee_id": employee["employee_id"]},
    )
    assert applied.status_code == 201, applied.text
    assert len(applied.json()["task_ids"]) == 2
    duplicate = client.post(
        f"/api/workforce/onboarding/templates/{template.json()['id']}/apply",
        headers=headers,
        json={"employee_id": employee["employee_id"]},
    )
    assert duplicate.status_code == 409

    with SessionLocal() as db:
        tasks = db.query(OnboardingTask).filter_by(
            tenant_id=owner["tenant_id"], employee_id=employee["employee_id"]
        ).order_by(OnboardingTask.due_date).all()
        assert [task.due_date.isoformat() for task in tasks] == ["2026-08-31", "2026-09-03"]
        assert tasks[0].assigned_to_id == employee["user_id"]
        assert tasks[1].assigned_to_id == manager["user_id"]


def test_benefit_eligibility_enrollment_and_employee_scope(
    client, identity_factory, login, password_hash
):
    owner = identity_factory(slug="benefit-flow")
    recent = add_employee(
        owner, password_hash, suffix="recent", hire_date=date.today()
    )
    other = add_employee(
        owner, password_hash, suffix="other", hire_date=date(2020, 1, 1)
    )
    owner_headers = login(owner)
    recent_headers = login(recent)
    other_headers = login(other)
    plan = create_plan(client, owner_headers)

    rule = client.put(
        f"/api/workforce/benefits/{plan['id']}/eligibility",
        headers=owner_headers,
        json={
            "department_id": None,
            "employment_status": "ativo",
            "minimum_tenure_days": 90,
            "active": True,
        },
    )
    assert rule.status_code == 200, rule.text
    eligibility = client.get(
        "/api/workforce/benefits/eligibility", headers=recent_headers
    ).json()
    assert eligibility == [
        {
            "plan_id": plan["id"],
            "plan_name": "Plano Saúde",
            "eligible": False,
            "reason": "Carência de 90 dias",
        }
    ]
    denied = client.post(
        "/api/workforce/benefits/enrollments",
        headers=recent_headers,
        json={"plan_id": plan["id"]},
    )
    assert denied.status_code == 409

    client.put(
        f"/api/workforce/benefits/{plan['id']}/eligibility",
        headers=owner_headers,
        json={
            "department_id": None,
            "employment_status": "ativo",
            "minimum_tenure_days": 0,
            "active": True,
        },
    )
    requested = client.post(
        "/api/workforce/benefits/enrollments",
        headers=recent_headers,
        json={"plan_id": plan["id"]},
    )
    assert requested.status_code == 201, requested.text
    assert requested.json()["status"] == "requested"
    assert client.post(
        "/api/workforce/benefits/enrollments",
        headers=recent_headers,
        json={"plan_id": plan["id"]},
    ).status_code == 409

    assert client.get(
        "/api/workforce/benefits/enrollments", headers=other_headers
    ).json() == []
    tamper = client.patch(
        f"/api/workforce/benefits/enrollments/{requested.json()['id']}",
        headers=recent_headers,
        json={"status": "cancelled", "employee_contribution": 1},
    )
    assert tamper.status_code == 403
    activated = client.patch(
        f"/api/workforce/benefits/enrollments/{requested.json()['id']}",
        headers=owner_headers,
        json={
            "status": "active",
            "effective_on": "2026-10-01",
            "employee_contribution": 100,
            "employer_contribution": 250,
            "decision_notes": "Elegibilidade confirmada",
        },
    )
    assert activated.status_code == 200, activated.text
    assert activated.json()["status"] == "active"
    assert activated.json()["employee_contribution"] == "100.00"


def test_workforce_resources_reject_cross_tenant_references(
    client, identity_factory, login, password_hash
):
    company_a = identity_factory(slug="workforce-a")
    company_b = identity_factory(slug="workforce-b")
    employee_a = add_employee(company_a, password_hash, suffix="tenant-a")
    plan_a = create_plan(client, login(company_a), name="Plano A")
    headers_b = login(company_b)

    cross_plan = client.put(
        f"/api/workforce/benefits/{plan_a['id']}/eligibility",
        headers=headers_b,
        json={"minimum_tenure_days": 0, "active": True},
    )
    assert cross_plan.status_code == 404

    template_b = client.post(
        "/api/workforce/onboarding/templates",
        headers=headers_b,
        json={
            "name": "Template B",
            "active": True,
            "items": [
                {
                    "title": "Tarefa B",
                    "due_offset_days": 0,
                    "assigned_role": "hr",
                    "position": 1,
                    "required": True,
                }
            ],
        },
    ).json()
    cross_employee = client.post(
        f"/api/workforce/onboarding/templates/{template_b['id']}/apply",
        headers=headers_b,
        json={"employee_id": employee_a["employee_id"]},
    )
    assert cross_employee.status_code == 404
