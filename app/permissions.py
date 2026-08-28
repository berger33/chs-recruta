from __future__ import annotations
from enum import Enum

class Permission(str, Enum):
    tenant_manage="tenant.manage"; users_read="users.read"; users_manage="users.manage"
    candidates_read="candidates.read"; candidates_write="candidates.write"; candidates_delete="candidates.delete"
    vacancies_read="vacancies.read"; vacancies_write="vacancies.write"; applications_manage="applications.manage"
    employees_read="employees.read"; employees_write="employees.write"; onboarding_manage="onboarding.manage"
    benefits_manage="benefits.manage"; time_own="time.own"; time_team="time.team"
    payroll_own="payroll.own"; payroll_manage="payroll.manage"; knowledge_read="knowledge.read"
    knowledge_manage="knowledge.manage"; audit_read="audit.read"; reports_read="reports.read"; billing_manage="billing.manage"
    contracts_read="contracts.read"; contracts_manage="contracts.manage"
    performance_read="performance.read"; performance_manage="performance.manage"
    esocial_manage="esocial.manage"
    portal_own="portal.own"; portal_team="portal.team"; portal_manage="portal.manage"
    employee_files_manage="employee_files.manage"
    time_manage="time.manage"; time_adjust_approve="time.adjust.approve"; time_close="time.close"

ALL_PERMISSIONS=frozenset(Permission)
ROLE_PERMISSIONS={
    "tenant_owner":ALL_PERMISSIONS, "admin":ALL_PERMISSIONS,
    "hr":frozenset({Permission.users_read,Permission.candidates_read,Permission.candidates_write,Permission.candidates_delete,Permission.vacancies_read,Permission.vacancies_write,Permission.applications_manage,Permission.employees_read,Permission.employees_write,Permission.onboarding_manage,Permission.benefits_manage,Permission.time_own,Permission.time_team,Permission.time_manage,Permission.time_adjust_approve,Permission.time_close,Permission.payroll_own,Permission.payroll_manage,Permission.knowledge_read,Permission.knowledge_manage,Permission.audit_read,Permission.reports_read,Permission.contracts_read,Permission.contracts_manage,Permission.performance_read,Permission.performance_manage,Permission.esocial_manage,Permission.portal_manage,Permission.employee_files_manage}),
    "recruiter":frozenset({Permission.candidates_read,Permission.candidates_write,Permission.vacancies_read,Permission.vacancies_write,Permission.applications_manage,Permission.knowledge_read,Permission.reports_read,Permission.portal_own}),
    "manager":frozenset({Permission.candidates_read,Permission.vacancies_read,Permission.employees_read,Permission.time_own,Permission.time_team,Permission.time_adjust_approve,Permission.payroll_own,Permission.knowledge_read,Permission.reports_read,Permission.performance_read,Permission.portal_own,Permission.portal_team}),
    "employee":frozenset({Permission.time_own,Permission.payroll_own,Permission.knowledge_read,Permission.performance_read,Permission.portal_own}),
    "auditor":frozenset({Permission.users_read,Permission.candidates_read,Permission.vacancies_read,Permission.employees_read,Permission.audit_read,Permission.reports_read,Permission.contracts_read,Permission.performance_read}),
}
def permissions_for_role(role: str) -> frozenset[Permission]:
    return ROLE_PERMISSIONS.get(role,frozenset())
