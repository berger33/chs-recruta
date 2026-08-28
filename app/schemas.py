from __future__ import annotations
from datetime import date,datetime
from decimal import Decimal
from pydantic import BaseModel,ConfigDict,EmailStr,Field,field_validator
from .models import ApplicationStage,CandidateStatus,EmploymentStatus,KnowledgeVisibility,Role,TaskStatus,TimeEntryKind,VacancyStatus

class ORMModel(BaseModel): model_config=ConfigDict(from_attributes=True)
class TenantSummary(ORMModel): id:int; name:str; slug:str; role:Role
class TutorialState(BaseModel): current_version:int; version_seen:int; dismissed:bool; should_show:bool
class LoginRequest(BaseModel): identifier:str=Field(min_length=3,max_length=160); password:str=Field(min_length=8,max_length=256); tenant_slug:str|None=Field(default=None,max_length=100)
class LoginResponse(BaseModel):
    token:str; token_type:str="bearer"; user_id:int; username:str; display_name:str; email:str; role:Role; tenant:TenantSummary; tenants:list[TenantSummary]; permissions:list[str]; tutorial:TutorialState
class ContextRead(BaseModel): user_id:int; username:str; display_name:str; email:str; role:Role; tenant:TenantSummary; permissions:list[str]; tutorial:TutorialState
class TenantRead(ORMModel):
    id:int; name:str; slug:str; legal_name:str; tax_id:str; timezone:str; locale:str; theme:str; active:bool; created_at:datetime; updated_at:datetime
class TenantUpdate(BaseModel):
    name:str|None=Field(default=None,min_length=2,max_length=160); legal_name:str|None=Field(default=None,max_length=200); tax_id:str|None=Field(default=None,max_length=32); timezone:str|None=Field(default=None,max_length=64); locale:str|None=Field(default=None,max_length=16); theme:str|None=Field(default=None,max_length=32)
class TenantSwitchRequest(BaseModel): tenant_id:int
class TutorialPreferenceUpdate(BaseModel): completed:bool=False; dismissed:bool=False; version:int=Field(ge=0)

class CandidateCreate(BaseModel):
    name:str=Field(min_length=2,max_length=160); profession:str=Field(min_length=2,max_length=120); city:str=Field(default="",max_length=120); professional_registry:str=Field(default="",max_length=80); phone:str=Field(default="",max_length=40); email:str=Field(default="",max_length=160); source:str=Field(default="",max_length=120); source_url:str=Field(default="",max_length=500); status:CandidateStatus=CandidateStatus.novo; notes:str=Field(default="",max_length=10_000)
    @field_validator("email")
    @classmethod
    def normalize_email(cls,value): return value.strip().lower()
class CandidateRead(CandidateCreate,ORMModel): id:int; created_by_id:int|None; created_at:datetime; updated_at:datetime
class VacancyCreate(BaseModel):
    code:str=Field(min_length=2,max_length=40); title:str=Field(min_length=2,max_length=160); profession:str=Field(min_length=2,max_length=120); city:str=Field(default="",max_length=120); positions:int=Field(default=1,ge=1,le=10_000); status:VacancyStatus=VacancyStatus.rascunho; description:str=Field(default="",max_length=20_000)
class VacancyRead(VacancyCreate,ORMModel): id:int; owner_id:int|None; created_at:datetime; updated_at:datetime
class ApplicationCreate(BaseModel): candidate_id:int; vacancy_id:int; stage:ApplicationStage=ApplicationStage.inscrito; score:int|None=Field(default=None,ge=0,le=100); notes:str=Field(default="",max_length=10_000)
class ApplicationUpdate(BaseModel): stage:ApplicationStage|None=None; score:int|None=Field(default=None,ge=0,le=100); notes:str|None=Field(default=None,max_length=10_000)
class ApplicationRead(ApplicationCreate,ORMModel): id:int; created_at:datetime; updated_at:datetime
class DepartmentCreate(BaseModel): name:str=Field(min_length=2,max_length=160); code:str=Field(min_length=2,max_length=40); active:bool=True
class DepartmentRead(DepartmentCreate,ORMModel): id:int; created_at:datetime
class EmployeeCreate(BaseModel):
    employee_number:str=Field(min_length=1,max_length=40); full_name:str=Field(min_length=2,max_length=160); corporate_email:str=Field(default="",max_length=160); job_title:str=Field(default="",max_length=160); status:EmploymentStatus=EmploymentStatus.pre_admissao; hire_date:date|None=None; termination_date:date|None=None; department_id:int|None=None; manager_id:int|None=None; user_id:int|None=None; candidate_id:int|None=None
class EmployeeRead(EmployeeCreate,ORMModel): id:int; created_at:datetime; updated_at:datetime
class OnboardingTaskCreate(BaseModel): employee_id:int; title:str=Field(min_length=2,max_length=200); description:str=Field(default="",max_length=10_000); status:TaskStatus=TaskStatus.pendente; due_date:date|None=None; assigned_to_id:int|None=None
class OnboardingTaskUpdate(BaseModel): title:str|None=Field(default=None,min_length=2,max_length=200); description:str|None=Field(default=None,max_length=10_000); status:TaskStatus|None=None; due_date:date|None=None; assigned_to_id:int|None=None
class OnboardingTaskRead(OnboardingTaskCreate,ORMModel): id:int; completed_at:datetime|None; created_at:datetime; updated_at:datetime
class BenefitPlanCreate(BaseModel): name:str=Field(min_length=2,max_length=160); category:str=Field(default="",max_length=80); provider:str=Field(default="",max_length=160); employee_cost:Decimal=Field(default=Decimal("0.00"),ge=0); active:bool=True
class BenefitPlanRead(BenefitPlanCreate,ORMModel): id:int; created_at:datetime
class TimeEntryCreate(BaseModel): employee_id:int; kind:TimeEntryKind; recorded_at:datetime; source:str=Field(default="manual",max_length=40); note:str=Field(default="",max_length=500)
class TimeEntryRead(TimeEntryCreate,ORMModel): id:int; integrity_hash:str; created_by_id:int|None; created_at:datetime
class PayrollDocumentCreate(BaseModel): employee_id:int; competence:str=Field(pattern=r"^\d{4}-(0[1-9]|1[0-2])$"); kind:str=Field(default="holerite",max_length=40); filename:str=Field(min_length=1,max_length=255); storage_key:str=Field(default="",max_length=500); checksum:str=Field(default="",max_length=64); published_at:datetime|None=None
class PayrollDocumentRead(PayrollDocumentCreate,ORMModel): id:int; created_at:datetime
class KnowledgeDocumentCreate(BaseModel): title:str=Field(min_length=2,max_length=200); content:str=Field(min_length=10,max_length=200_000); visibility:KnowledgeVisibility=KnowledgeVisibility.todos; status:str=Field(default="published",max_length=32)
class KnowledgeDocumentRead(KnowledgeDocumentCreate,ORMModel): id:int; version:int; owner_id:int|None; created_at:datetime; updated_at:datetime
class KnowledgeQuestion(BaseModel): question:str=Field(min_length=3,max_length=2_000)
class KnowledgeCitation(BaseModel): document_id:int; title:str; excerpt:str; version:int
class KnowledgeAnswer(BaseModel): answer:str; grounded:bool; citations:list[KnowledgeCitation]
class FinancialCreate(BaseModel): service:str=Field(min_length=2,max_length=160); current_value:Decimal=Field(ge=0); max_value:Decimal=Field(ge=0)
class FinancialRead(FinancialCreate,ORMModel): id:int
class DashboardRead(BaseModel): candidates:int; new_candidates:int; open_vacancies:int; open_positions:int; applications:int; hires:int; employees:int; onboarding_pending:int; conversion_rate:float; funnel:dict[str,int]
class AuditRead(ORMModel): id:int; action:str; entity:str; entity_id:str; actor:str; request_id:str; ip_address:str; details:str; before_data:dict|None; after_data:dict|None; created_at:datetime
class UserCreate(BaseModel): username:str=Field(min_length=3,max_length=80); display_name:str=Field(min_length=2,max_length=120); email:EmailStr; password:str=Field(min_length=8,max_length=256); role:Role=Role.employee
class MembershipRead(BaseModel): id:int; user_id:int; username:str; display_name:str; email:str; role:Role; active:bool
