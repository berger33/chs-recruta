from __future__ import annotations
from datetime import UTC,date,datetime
from decimal import Decimal
from enum import Enum
from sqlalchemy import JSON,Boolean,Date,DateTime,Enum as SAEnum,ForeignKey,Index,Integer,Numeric,String,Text,UniqueConstraint
from sqlalchemy.orm import Mapped,mapped_column,relationship
from .database import Base

def utcnow(): return datetime.now(UTC).replace(tzinfo=None)
def enum_type(cls,name): return SAEnum(cls,name=name,native_enum=False,values_callable=lambda values:[x.value for x in values])

class Role(str,Enum):
    tenant_owner="tenant_owner"; admin="admin"; hr="hr"; recruiter="recruiter"; manager="manager"; employee="employee"; auditor="auditor"
class CandidateStatus(str,Enum):
    novo="Novo"; em_contato="Em Contato"; contatado="Contatado"; sem_resposta="Sem resposta"; respondeu="Respondeu"; entrevista_marcada="Entrevista marcada"; entrevistado="Entrevistado"; contratado="Contratado"; banco_talentos="Banco de Talentos"; nao_interessado="Não interessado"; arquivado="Arquivado"
class VacancyStatus(str,Enum):
    rascunho="rascunho"; aprovacao="aprovacao"; aberta="aberta"; pausada="pausada"; fechada="fechada"; cancelada="cancelada"
class ApplicationStage(str,Enum):
    inscrito="Inscrito"; triagem="Triagem"; entrevista="Entrevista"; proposta="Proposta"; contratado="Contratado"; rejeitado="Rejeitado"; desistente="Desistente"
class EmploymentStatus(str,Enum):
    pre_admissao="pre_admissao"; ativo="ativo"; afastado="afastado"; desligado="desligado"
class TaskStatus(str,Enum):
    pendente="pendente"; em_andamento="em_andamento"; concluida="concluida"; cancelada="cancelada"
class TimeEntryKind(str,Enum):
    entrada="entrada"; inicio_intervalo="inicio_intervalo"; fim_intervalo="fim_intervalo"; saida="saida"
class KnowledgeVisibility(str,Enum):
    todos="todos"; rh="rh"; gestores="gestores"
class SubscriptionStatus(str,Enum):
    trial="trial"; active="active"; past_due="past_due"; canceled="canceled"

class Tenant(Base):
    __tablename__="tenants"
    id:Mapped[int]=mapped_column(Integer,primary_key=True)
    name:Mapped[str]=mapped_column(String(160),index=True)
    slug:Mapped[str]=mapped_column(String(100),unique=True,index=True)
    legal_name:Mapped[str]=mapped_column(String(200),default="")
    tax_id:Mapped[str]=mapped_column(String(32),default="")
    timezone:Mapped[str]=mapped_column(String(64),default="America/Sao_Paulo")
    locale:Mapped[str]=mapped_column(String(16),default="pt-BR")
    theme:Mapped[str]=mapped_column(String(32),default="rose")
    active:Mapped[bool]=mapped_column(Boolean,default=True,index=True)
    created_at:Mapped[datetime]=mapped_column(DateTime,default=utcnow)
    updated_at:Mapped[datetime]=mapped_column(DateTime,default=utcnow,onupdate=utcnow)

class User(Base):
    __tablename__="users"
    id:Mapped[int]=mapped_column(Integer,primary_key=True)
    username:Mapped[str]=mapped_column(String(80),unique=True,index=True)
    display_name:Mapped[str]=mapped_column(String(120))
    email:Mapped[str]=mapped_column(String(160),unique=True,index=True)
    password_hash:Mapped[str]=mapped_column(String(255))
    active:Mapped[bool]=mapped_column(Boolean,default=True,index=True)
    platform_admin:Mapped[bool]=mapped_column(Boolean,default=False)
    created_at:Mapped[datetime]=mapped_column(DateTime,default=utcnow)
    updated_at:Mapped[datetime]=mapped_column(DateTime,default=utcnow,onupdate=utcnow)
    memberships:Mapped[list["Membership"]]=relationship(back_populates="user",cascade="all, delete-orphan")

class Membership(Base):
    __tablename__="memberships"; __table_args__=(UniqueConstraint("tenant_id","user_id",name="uq_membership_tenant_user"),)
    id:Mapped[int]=mapped_column(Integer,primary_key=True)
    tenant_id:Mapped[int]=mapped_column(ForeignKey("tenants.id",ondelete="CASCADE"),index=True)
    user_id:Mapped[int]=mapped_column(ForeignKey("users.id",ondelete="CASCADE"),index=True)
    role:Mapped[Role]=mapped_column(enum_type(Role,"membership_role"),default=Role.employee,index=True)
    active:Mapped[bool]=mapped_column(Boolean,default=True,index=True)
    tutorial_version_seen:Mapped[int]=mapped_column(Integer,default=0)
    tutorial_dismissed:Mapped[bool]=mapped_column(Boolean,default=False)
    created_at:Mapped[datetime]=mapped_column(DateTime,default=utcnow)
    updated_at:Mapped[datetime]=mapped_column(DateTime,default=utcnow,onupdate=utcnow)
    tenant:Mapped[Tenant]=relationship()
    user:Mapped[User]=relationship(back_populates="memberships")

class SessionToken(Base):
    __tablename__="session_tokens"
    id:Mapped[int]=mapped_column(Integer,primary_key=True)
    token_hash:Mapped[str]=mapped_column(String(64),unique=True,index=True)
    user_id:Mapped[int]=mapped_column(ForeignKey("users.id",ondelete="CASCADE"),index=True)
    membership_id:Mapped[int]=mapped_column(ForeignKey("memberships.id",ondelete="CASCADE"),index=True)
    tenant_id:Mapped[int]=mapped_column(ForeignKey("tenants.id",ondelete="CASCADE"),index=True)
    expires_at:Mapped[datetime]=mapped_column(DateTime,index=True)
    created_at:Mapped[datetime]=mapped_column(DateTime,default=utcnow)
    last_seen_at:Mapped[datetime]=mapped_column(DateTime,default=utcnow)
    user:Mapped[User]=relationship(); membership:Mapped[Membership]=relationship(); tenant:Mapped[Tenant]=relationship()

class Candidate(Base):
    __tablename__="candidates"; __table_args__=(Index("ix_candidate_tenant_name","tenant_id","name"),Index("ix_candidate_tenant_status","tenant_id","status"))
    id:Mapped[int]=mapped_column(Integer,primary_key=True)
    tenant_id:Mapped[int]=mapped_column(ForeignKey("tenants.id",ondelete="CASCADE"),index=True)
    name:Mapped[str]=mapped_column(String(160)); profession:Mapped[str]=mapped_column(String(120),index=True)
    city:Mapped[str]=mapped_column(String(120),default=""); professional_registry:Mapped[str]=mapped_column(String(80),default="")
    phone:Mapped[str]=mapped_column(String(40),default="",index=True); email:Mapped[str]=mapped_column(String(160),default="")
    source:Mapped[str]=mapped_column(String(120),default=""); source_url:Mapped[str]=mapped_column(String(500),default="")
    status:Mapped[CandidateStatus]=mapped_column(enum_type(CandidateStatus,"candidate_status"),default=CandidateStatus.novo,index=True)
    notes:Mapped[str]=mapped_column(Text,default="")
    created_by_id:Mapped[int|None]=mapped_column(ForeignKey("users.id",ondelete="SET NULL"),nullable=True)
    deleted_at:Mapped[datetime|None]=mapped_column(DateTime,nullable=True,index=True)
    created_at:Mapped[datetime]=mapped_column(DateTime,default=utcnow); updated_at:Mapped[datetime]=mapped_column(DateTime,default=utcnow,onupdate=utcnow)

class Vacancy(Base):
    __tablename__="vacancies"; __table_args__=(UniqueConstraint("tenant_id","code",name="uq_vacancy_tenant_code"),Index("ix_vacancy_tenant_status","tenant_id","status"))
    id:Mapped[int]=mapped_column(Integer,primary_key=True); tenant_id:Mapped[int]=mapped_column(ForeignKey("tenants.id",ondelete="CASCADE"),index=True)
    code:Mapped[str]=mapped_column(String(40),index=True); title:Mapped[str]=mapped_column(String(160)); profession:Mapped[str]=mapped_column(String(120),index=True)
    city:Mapped[str]=mapped_column(String(120),default=""); positions:Mapped[int]=mapped_column(Integer,default=1)
    status:Mapped[VacancyStatus]=mapped_column(enum_type(VacancyStatus,"vacancy_status"),default=VacancyStatus.rascunho,index=True)
    owner_id:Mapped[int|None]=mapped_column(ForeignKey("users.id",ondelete="SET NULL"),nullable=True); description:Mapped[str]=mapped_column(Text,default="")
    deleted_at:Mapped[datetime|None]=mapped_column(DateTime,nullable=True,index=True); created_at:Mapped[datetime]=mapped_column(DateTime,default=utcnow); updated_at:Mapped[datetime]=mapped_column(DateTime,default=utcnow,onupdate=utcnow)

class Application(Base):
    __tablename__="applications"; __table_args__=(UniqueConstraint("tenant_id","candidate_id","vacancy_id",name="uq_application_candidate_vacancy"),Index("ix_application_tenant_stage","tenant_id","stage"))
    id:Mapped[int]=mapped_column(Integer,primary_key=True); tenant_id:Mapped[int]=mapped_column(ForeignKey("tenants.id",ondelete="CASCADE"),index=True)
    candidate_id:Mapped[int]=mapped_column(ForeignKey("candidates.id",ondelete="CASCADE"),index=True); vacancy_id:Mapped[int]=mapped_column(ForeignKey("vacancies.id",ondelete="CASCADE"),index=True)
    stage:Mapped[ApplicationStage]=mapped_column(enum_type(ApplicationStage,"application_stage"),default=ApplicationStage.inscrito,index=True)
    score:Mapped[int|None]=mapped_column(Integer,nullable=True); notes:Mapped[str]=mapped_column(Text,default="")
    created_at:Mapped[datetime]=mapped_column(DateTime,default=utcnow); updated_at:Mapped[datetime]=mapped_column(DateTime,default=utcnow,onupdate=utcnow)

class Department(Base):
    __tablename__="departments"; __table_args__=(UniqueConstraint("tenant_id","code",name="uq_department_tenant_code"),)
    id:Mapped[int]=mapped_column(Integer,primary_key=True); tenant_id:Mapped[int]=mapped_column(ForeignKey("tenants.id",ondelete="CASCADE"),index=True)
    name:Mapped[str]=mapped_column(String(160)); code:Mapped[str]=mapped_column(String(40)); active:Mapped[bool]=mapped_column(Boolean,default=True); created_at:Mapped[datetime]=mapped_column(DateTime,default=utcnow)

class Employee(Base):
    __tablename__="employees"; __table_args__=(UniqueConstraint("tenant_id","employee_number",name="uq_employee_tenant_number"),Index("ix_employee_tenant_status","tenant_id","status"))
    id:Mapped[int]=mapped_column(Integer,primary_key=True); tenant_id:Mapped[int]=mapped_column(ForeignKey("tenants.id",ondelete="CASCADE"),index=True)
    user_id:Mapped[int|None]=mapped_column(ForeignKey("users.id",ondelete="SET NULL"),nullable=True,index=True)
    candidate_id:Mapped[int|None]=mapped_column(ForeignKey("candidates.id",ondelete="SET NULL"),nullable=True,index=True)
    department_id:Mapped[int|None]=mapped_column(ForeignKey("departments.id",ondelete="SET NULL"),nullable=True,index=True)
    manager_id:Mapped[int|None]=mapped_column(ForeignKey("employees.id",ondelete="SET NULL"),nullable=True)
    employee_number:Mapped[str]=mapped_column(String(40),index=True); full_name:Mapped[str]=mapped_column(String(160),index=True)
    corporate_email:Mapped[str]=mapped_column(String(160),default=""); job_title:Mapped[str]=mapped_column(String(160),default="")
    status:Mapped[EmploymentStatus]=mapped_column(enum_type(EmploymentStatus,"employment_status"),default=EmploymentStatus.pre_admissao,index=True)
    hire_date:Mapped[date|None]=mapped_column(Date,nullable=True); termination_date:Mapped[date|None]=mapped_column(Date,nullable=True)
    created_at:Mapped[datetime]=mapped_column(DateTime,default=utcnow); updated_at:Mapped[datetime]=mapped_column(DateTime,default=utcnow,onupdate=utcnow)

class OnboardingTask(Base):
    __tablename__="onboarding_tasks"; __table_args__=(Index("ix_onboarding_tenant_status","tenant_id","status"),)
    id:Mapped[int]=mapped_column(Integer,primary_key=True); tenant_id:Mapped[int]=mapped_column(ForeignKey("tenants.id",ondelete="CASCADE"),index=True)
    employee_id:Mapped[int]=mapped_column(ForeignKey("employees.id",ondelete="CASCADE"),index=True); title:Mapped[str]=mapped_column(String(200))
    description:Mapped[str]=mapped_column(Text,default=""); status:Mapped[TaskStatus]=mapped_column(enum_type(TaskStatus,"task_status"),default=TaskStatus.pendente,index=True)
    due_date:Mapped[date|None]=mapped_column(Date,nullable=True); assigned_to_id:Mapped[int|None]=mapped_column(ForeignKey("users.id",ondelete="SET NULL"),nullable=True)
    completed_at:Mapped[datetime|None]=mapped_column(DateTime,nullable=True); created_at:Mapped[datetime]=mapped_column(DateTime,default=utcnow); updated_at:Mapped[datetime]=mapped_column(DateTime,default=utcnow,onupdate=utcnow)

class BenefitPlan(Base):
    __tablename__="benefit_plans"; __table_args__=(UniqueConstraint("tenant_id","name",name="uq_benefit_tenant_name"),)
    id:Mapped[int]=mapped_column(Integer,primary_key=True); tenant_id:Mapped[int]=mapped_column(ForeignKey("tenants.id",ondelete="CASCADE"),index=True)
    name:Mapped[str]=mapped_column(String(160)); category:Mapped[str]=mapped_column(String(80),default=""); provider:Mapped[str]=mapped_column(String(160),default="")
    employee_cost:Mapped[Decimal]=mapped_column(Numeric(12,2),default=Decimal("0.00")); active:Mapped[bool]=mapped_column(Boolean,default=True); created_at:Mapped[datetime]=mapped_column(DateTime,default=utcnow)

class EmployeeBenefit(Base):
    __tablename__="employee_benefits"; __table_args__=(UniqueConstraint("tenant_id","employee_id","plan_id",name="uq_employee_benefit"),)
    id:Mapped[int]=mapped_column(Integer,primary_key=True); tenant_id:Mapped[int]=mapped_column(ForeignKey("tenants.id",ondelete="CASCADE"),index=True)
    employee_id:Mapped[int]=mapped_column(ForeignKey("employees.id",ondelete="CASCADE"),index=True); plan_id:Mapped[int]=mapped_column(ForeignKey("benefit_plans.id",ondelete="CASCADE"),index=True)
    active:Mapped[bool]=mapped_column(Boolean,default=True); enrolled_at:Mapped[date]=mapped_column(Date,default=date.today)

class TimeEntry(Base):
    __tablename__="time_entries"; __table_args__=(Index("ix_time_entry_tenant_employee_recorded","tenant_id","employee_id","recorded_at"),)
    id:Mapped[int]=mapped_column(Integer,primary_key=True); tenant_id:Mapped[int]=mapped_column(ForeignKey("tenants.id",ondelete="CASCADE"),index=True)
    employee_id:Mapped[int]=mapped_column(ForeignKey("employees.id",ondelete="CASCADE"),index=True); kind:Mapped[TimeEntryKind]=mapped_column(enum_type(TimeEntryKind,"time_entry_kind"),index=True)
    recorded_at:Mapped[datetime]=mapped_column(DateTime,index=True); source:Mapped[str]=mapped_column(String(40),default="manual"); note:Mapped[str]=mapped_column(String(500),default="")
    integrity_hash:Mapped[str]=mapped_column(String(64),default=""); created_by_id:Mapped[int|None]=mapped_column(ForeignKey("users.id",ondelete="SET NULL"),nullable=True); created_at:Mapped[datetime]=mapped_column(DateTime,default=utcnow)

class PayrollDocument(Base):
    __tablename__="payroll_documents"; __table_args__=(UniqueConstraint("tenant_id","employee_id","competence","kind",name="uq_payroll_document"),)
    id:Mapped[int]=mapped_column(Integer,primary_key=True); tenant_id:Mapped[int]=mapped_column(ForeignKey("tenants.id",ondelete="CASCADE"),index=True)
    employee_id:Mapped[int]=mapped_column(ForeignKey("employees.id",ondelete="CASCADE"),index=True); competence:Mapped[str]=mapped_column(String(7),index=True)
    kind:Mapped[str]=mapped_column(String(40),default="holerite"); filename:Mapped[str]=mapped_column(String(255)); storage_key:Mapped[str]=mapped_column(String(500),default="")
    checksum:Mapped[str]=mapped_column(String(64),default=""); published_at:Mapped[datetime|None]=mapped_column(DateTime,nullable=True); created_at:Mapped[datetime]=mapped_column(DateTime,default=utcnow)

class KnowledgeDocument(Base):
    __tablename__="knowledge_documents"; __table_args__=(Index("ix_knowledge_tenant_status","tenant_id","status"),)
    id:Mapped[int]=mapped_column(Integer,primary_key=True); tenant_id:Mapped[int]=mapped_column(ForeignKey("tenants.id",ondelete="CASCADE"),index=True)
    title:Mapped[str]=mapped_column(String(200),index=True); content:Mapped[str]=mapped_column(Text)
    visibility:Mapped[KnowledgeVisibility]=mapped_column(enum_type(KnowledgeVisibility,"knowledge_visibility"),default=KnowledgeVisibility.todos)
    status:Mapped[str]=mapped_column(String(32),default="published",index=True); version:Mapped[int]=mapped_column(Integer,default=1)
    owner_id:Mapped[int|None]=mapped_column(ForeignKey("users.id",ondelete="SET NULL"),nullable=True); created_at:Mapped[datetime]=mapped_column(DateTime,default=utcnow); updated_at:Mapped[datetime]=mapped_column(DateTime,default=utcnow,onupdate=utcnow)

class FinancialReference(Base):
    __tablename__="financial_references"; __table_args__=(UniqueConstraint("tenant_id","service",name="uq_financial_tenant_service"),)
    id:Mapped[int]=mapped_column(Integer,primary_key=True); tenant_id:Mapped[int]=mapped_column(ForeignKey("tenants.id",ondelete="CASCADE"),index=True)
    service:Mapped[str]=mapped_column(String(160)); current_value:Mapped[Decimal]=mapped_column(Numeric(12,2),default=Decimal("0.00")); max_value:Mapped[Decimal]=mapped_column(Numeric(12,2),default=Decimal("0.00"))

class Subscription(Base):
    __tablename__="subscriptions"
    id:Mapped[int]=mapped_column(Integer,primary_key=True); tenant_id:Mapped[int]=mapped_column(ForeignKey("tenants.id",ondelete="CASCADE"),unique=True,index=True)
    plan_code:Mapped[str]=mapped_column(String(60),default="starter"); status:Mapped[SubscriptionStatus]=mapped_column(enum_type(SubscriptionStatus,"subscription_status"),default=SubscriptionStatus.trial)
    employee_limit:Mapped[int]=mapped_column(Integer,default=25); enabled_modules:Mapped[list[str]]=mapped_column(JSON,default=list)
    trial_ends_at:Mapped[datetime|None]=mapped_column(DateTime,nullable=True); created_at:Mapped[datetime]=mapped_column(DateTime,default=utcnow); updated_at:Mapped[datetime]=mapped_column(DateTime,default=utcnow,onupdate=utcnow)

class AuditLog(Base):
    __tablename__="audit_logs"; __table_args__=(Index("ix_audit_tenant_created","tenant_id","created_at"),Index("ix_audit_tenant_entity","tenant_id","entity","entity_id"))
    id:Mapped[int]=mapped_column(Integer,primary_key=True); tenant_id:Mapped[int|None]=mapped_column(ForeignKey("tenants.id",ondelete="SET NULL"),nullable=True)
    action:Mapped[str]=mapped_column(String(80),index=True); entity:Mapped[str]=mapped_column(String(80),index=True); entity_id:Mapped[str]=mapped_column(String(80),default="")
    actor_user_id:Mapped[int|None]=mapped_column(ForeignKey("users.id",ondelete="SET NULL"),nullable=True); actor:Mapped[str]=mapped_column(String(120),default="system")
    request_id:Mapped[str]=mapped_column(String(64),default="",index=True); ip_address:Mapped[str]=mapped_column(String(64),default=""); details:Mapped[str]=mapped_column(Text,default="")
    before_data:Mapped[dict|None]=mapped_column(JSON,nullable=True); after_data:Mapped[dict|None]=mapped_column(JSON,nullable=True); created_at:Mapped[datetime]=mapped_column(DateTime,default=utcnow,index=True)
