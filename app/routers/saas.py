from __future__ import annotations
import csv,io
from datetime import UTC,datetime
from typing import Annotated
from fastapi import APIRouter,Depends,HTTPException,Query,Request,status
from fastapi.responses import StreamingResponse
from sqlalchemy import or_,select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from ..config import get_settings
from ..database import get_db
from ..models import *
from ..permissions import Permission,permissions_for_role
from ..schemas import *
from ..security import AuthContext,active_memberships,bearer,current_context,find_user,hash_password,issue_session,require_permissions,revoke_session,verify_password
from ..services import audit,dashboard,knowledge_answer,model_snapshot,normalize_profession,possible_duplicate,search_candidates,time_entry_hash

router=APIRouter()

def tutorial_state(m):
    version=get_settings().tutorial_version
    return TutorialState(current_version=version,version_seen=m.tutorial_version_seen,dismissed=m.tutorial_dismissed,should_show=not m.tutorial_dismissed and m.tutorial_version_seen<version)
def tenant_summary(m): return TenantSummary(id=m.tenant.id,name=m.tenant.name,slug=m.tenant.slug,role=m.role)
def context_payload(c):
    return ContextRead(user_id=c.user.id,username=c.user.username,display_name=c.user.display_name,email=c.user.email,role=c.membership.role,tenant=tenant_summary(c.membership),permissions=sorted(x.value for x in c.permissions),tutorial=tutorial_state(c.membership))
def member_payload(m): return MembershipRead(id=m.id,user_id=m.user.id,username=m.user.username,display_name=m.user.display_name,email=m.user.email,role=m.role,active=m.active)
def scoped(db,model,tenant_id,object_id,detail):
    obj=db.scalar(select(model).where(model.id==object_id,model.tenant_id==tenant_id))
    if not obj: raise HTTPException(404,detail)
    return obj
def scoped_candidate(db,tenant_id,object_id):
    obj=db.scalar(select(Candidate).where(Candidate.id==object_id,Candidate.tenant_id==tenant_id,Candidate.deleted_at.is_(None)))
    if not obj: raise HTTPException(404,"Candidato não encontrado")
    return obj
def scoped_vacancy(db,tenant_id,object_id):
    obj=db.scalar(select(Vacancy).where(Vacancy.id==object_id,Vacancy.tenant_id==tenant_id,Vacancy.deleted_at.is_(None)))
    if not obj: raise HTTPException(404,"Vaga não encontrada")
    return obj
def own_employee(db,c):
    obj=db.scalar(select(Employee).where(Employee.tenant_id==c.tenant_id,Employee.user_id==c.user.id))
    if not obj: raise HTTPException(403,"Usuário não está vinculado a um colaborador")
    return obj
def time_employee_scope(db,c):
    if Permission.time_manage in c.permissions: return None
    employee=own_employee(db,c); allowed={employee.id}
    if Permission.time_team in c.permissions:
        allowed.update(db.scalars(select(Employee.id).where(Employee.tenant_id==c.tenant_id,Employee.manager_id==employee.id)).all())
    elif Permission.time_own not in c.permissions: raise HTTPException(403,"Permissão insuficiente")
    return allowed

@router.post("/api/auth/login",response_model=LoginResponse,tags=["auth"])
def login(payload:LoginRequest,db:Annotated[Session,Depends(get_db)]):
    user=find_user(db,payload.identifier)
    if not user or not user.active or not verify_password(payload.password,user.password_hash): raise HTTPException(401,"Credenciais inválidas")
    memberships=active_memberships(db,user.id)
    if not memberships: raise HTTPException(403,"Usuário sem empresa ativa")
    selected=memberships[0]
    if payload.tenant_slug:
        selected=next((x for x in memberships if x.tenant.slug==payload.tenant_slug),None)
        if not selected: raise HTTPException(403,"Empresa não autorizada")
    token=issue_session(db,user,selected)
    return LoginResponse(token=token,user_id=user.id,username=user.username,display_name=user.display_name,email=user.email,role=selected.role,tenant=tenant_summary(selected),tenants=[tenant_summary(x) for x in memberships],permissions=sorted(x.value for x in permissions_for_role(selected.role.value)),tutorial=tutorial_state(selected))
@router.get("/api/auth/me",response_model=ContextRead,tags=["auth"])
def me(c:Annotated[AuthContext,Depends(current_context)]): return context_payload(c)
@router.post("/api/auth/logout",status_code=204,tags=["auth"])
def logout(credentials=Depends(bearer),db:Session=Depends(get_db)):
    if credentials: revoke_session(db,credentials.credentials)

@router.get("/api/tenants",response_model=list[TenantSummary],tags=["tenants"])
def tenants(c:Annotated[AuthContext,Depends(current_context)],db:Annotated[Session,Depends(get_db)]): return [tenant_summary(x) for x in active_memberships(db,c.user.id)]
@router.get("/api/tenants/current",response_model=TenantRead,tags=["tenants"])
def tenant_current(c:Annotated[AuthContext,Depends(current_context)]): return c.tenant
@router.patch("/api/tenants/current",response_model=TenantRead,tags=["tenants"])
def tenant_update(payload:TenantUpdate,request:Request,c:Annotated[AuthContext,Depends(require_permissions(Permission.tenant_manage))],db:Annotated[Session,Depends(get_db)]):
    before=model_snapshot(c.tenant)
    for key,value in payload.model_dump(exclude_unset=True).items(): setattr(c.tenant,key,value)
    audit(db,context=c,request=request,action="update",entity="tenant",entity_id=str(c.tenant.id),before=before,after=model_snapshot(c.tenant)); db.commit(); db.refresh(c.tenant); return c.tenant
@router.post("/api/tenants/switch",response_model=LoginResponse,tags=["tenants"])
def tenant_switch(payload:TenantSwitchRequest,c:Annotated[AuthContext,Depends(current_context)],db:Annotated[Session,Depends(get_db)]):
    m=db.scalar(select(Membership).where(Membership.user_id==c.user.id,Membership.tenant_id==payload.tenant_id,Membership.active.is_(True))); tenant=db.get(Tenant,payload.tenant_id)
    if not m or not tenant or not tenant.active: raise HTTPException(403,"Empresa não autorizada")
    token=issue_session(db,c.user,m); memberships=active_memberships(db,c.user.id)
    return LoginResponse(token=token,user_id=c.user.id,username=c.user.username,display_name=c.user.display_name,email=c.user.email,role=m.role,tenant=tenant_summary(m),tenants=[tenant_summary(x) for x in memberships],permissions=sorted(x.value for x in permissions_for_role(m.role.value)),tutorial=tutorial_state(m))
@router.put("/api/tenants/tutorial",tags=["tenants"])
def tutorial_update(payload:TutorialPreferenceUpdate,request:Request,c:Annotated[AuthContext,Depends(current_context)],db:Annotated[Session,Depends(get_db)]):
    before={"version_seen":c.membership.tutorial_version_seen,"dismissed":c.membership.tutorial_dismissed}
    version=min(payload.version,get_settings().tutorial_version)
    if payload.completed or payload.dismissed: c.membership.tutorial_version_seen=version
    c.membership.tutorial_dismissed=payload.dismissed
    after={"version_seen":c.membership.tutorial_version_seen,"dismissed":c.membership.tutorial_dismissed}
    audit(db,context=c,request=request,action="update_tutorial_preference",entity="membership",entity_id=str(c.membership.id),before=before,after=after); db.commit(); return tutorial_state(c.membership)

@router.get("/api/users",response_model=list[MembershipRead],tags=["users"])
def users(c:Annotated[AuthContext,Depends(require_permissions(Permission.users_read))],db:Annotated[Session,Depends(get_db)]):
    items=db.scalars(select(Membership).where(Membership.tenant_id==c.tenant_id).join(User,User.id==Membership.user_id).order_by(User.display_name)).all()
    return [member_payload(x) for x in items]
@router.post("/api/users",response_model=MembershipRead,status_code=201,tags=["users"])
def user_create(payload:UserCreate,request:Request,c:Annotated[AuthContext,Depends(require_permissions(Permission.users_manage))],db:Annotated[Session,Depends(get_db)]):
    email=str(payload.email).lower(); user=db.scalar(select(User).where(or_(User.username==payload.username.lower(),User.email==email)))
    if user and (user.username!=payload.username.lower() or user.email!=email): raise HTTPException(409,"Usuário ou e-mail já está em uso")
    if not user:
        user=User(username=payload.username.lower(),display_name=payload.display_name,email=email,password_hash=hash_password(payload.password)); db.add(user); db.flush()
    if db.scalar(select(Membership).where(Membership.tenant_id==c.tenant_id,Membership.user_id==user.id)): raise HTTPException(409,"Usuário já pertence a esta empresa")
    m=Membership(tenant_id=c.tenant_id,user_id=user.id,role=payload.role); db.add(m); db.flush()
    audit(db,context=c,request=request,action="create",entity="membership",entity_id=str(m.id),details=f"{user.email} ({m.role.value})",after=model_snapshot(m)); db.commit(); db.refresh(m); return member_payload(m)

@router.get("/api/candidates",response_model=list[CandidateRead],tags=["ats"])
def candidates(c:Annotated[AuthContext,Depends(require_permissions(Permission.candidates_read))],db:Annotated[Session,Depends(get_db)],q:str=Query("",max_length=200),limit:int=Query(50,ge=1,le=200),offset:int=Query(0,ge=0)): return search_candidates(db,c.tenant_id,q,limit,offset)
@router.post("/api/candidates",response_model=CandidateRead,status_code=201,tags=["ats"])
def candidate_create(payload:CandidateCreate,request:Request,c:Annotated[AuthContext,Depends(require_permissions(Permission.candidates_write))],db:Annotated[Session,Depends(get_db)]):
    duplicate=possible_duplicate(db,c.tenant_id,payload.name,payload.phone,payload.professional_registry)
    if duplicate: raise HTTPException(409,{"message":"Possível duplicidade","candidate_id":duplicate.id})
    data=payload.model_dump(); data["profession"]=normalize_profession(data["profession"])
    obj=Candidate(tenant_id=c.tenant_id,created_by_id=c.user.id,**data); db.add(obj); db.flush()
    audit(db,context=c,request=request,action="create",entity="candidate",entity_id=str(obj.id),details=obj.name,after=model_snapshot(obj)); db.commit(); db.refresh(obj); return obj
@router.get("/api/candidates/{candidate_id}",response_model=CandidateRead,tags=["ats"])
def candidate_get(candidate_id:int,c:Annotated[AuthContext,Depends(require_permissions(Permission.candidates_read))],db:Annotated[Session,Depends(get_db)]): return scoped_candidate(db,c.tenant_id,candidate_id)
@router.put("/api/candidates/{candidate_id}",response_model=CandidateRead,tags=["ats"])
def candidate_update(candidate_id:int,payload:CandidateCreate,request:Request,c:Annotated[AuthContext,Depends(require_permissions(Permission.candidates_write))],db:Annotated[Session,Depends(get_db)]):
    obj=scoped_candidate(db,c.tenant_id,candidate_id); duplicate=possible_duplicate(db,c.tenant_id,payload.name,payload.phone,payload.professional_registry,obj.id)
    if duplicate: raise HTTPException(409,{"message":"Possível duplicidade","candidate_id":duplicate.id})
    before=model_snapshot(obj); data=payload.model_dump(); data["profession"]=normalize_profession(data["profession"])
    for key,value in data.items(): setattr(obj,key,value)
    audit(db,context=c,request=request,action="update",entity="candidate",entity_id=str(obj.id),details=obj.name,before=before,after=model_snapshot(obj)); db.commit(); db.refresh(obj); return obj
@router.delete("/api/candidates/{candidate_id}",status_code=204,tags=["ats"])
def candidate_delete(candidate_id:int,request:Request,c:Annotated[AuthContext,Depends(require_permissions(Permission.candidates_delete))],db:Annotated[Session,Depends(get_db)]):
    obj=scoped_candidate(db,c.tenant_id,candidate_id); before=model_snapshot(obj); obj.deleted_at=utcnow()
    audit(db,context=c,request=request,action="soft_delete",entity="candidate",entity_id=str(obj.id),details=obj.name,before=before,after=model_snapshot(obj)); db.commit()
@router.get("/api/candidates/{candidate_id}/matches",response_model=list[VacancyRead],tags=["ats"])
def matches(candidate_id:int,c:Annotated[AuthContext,Depends(require_permissions(Permission.candidates_read,Permission.vacancies_read))],db:Annotated[Session,Depends(get_db)]):
    candidate=scoped_candidate(db,c.tenant_id,candidate_id); profession=normalize_profession(candidate.profession)
    return [x for x in db.scalars(select(Vacancy).where(Vacancy.tenant_id==c.tenant_id,Vacancy.deleted_at.is_(None),Vacancy.status==VacancyStatus.aberta)).all() if normalize_profession(x.profession)==profession]

@router.get("/api/vacancies",response_model=list[VacancyRead],tags=["ats"])
def vacancies(c:Annotated[AuthContext,Depends(require_permissions(Permission.vacancies_read))],db:Annotated[Session,Depends(get_db)]): return db.scalars(select(Vacancy).where(Vacancy.tenant_id==c.tenant_id,Vacancy.deleted_at.is_(None)).order_by(Vacancy.updated_at.desc())).all()
@router.post("/api/vacancies",response_model=VacancyRead,status_code=201,tags=["ats"])
def vacancy_create(payload:VacancyCreate,request:Request,c:Annotated[AuthContext,Depends(require_permissions(Permission.vacancies_write))],db:Annotated[Session,Depends(get_db)]):
    data=payload.model_dump(); data["profession"]=normalize_profession(data["profession"]); obj=Vacancy(tenant_id=c.tenant_id,owner_id=c.user.id,**data); db.add(obj)
    try: db.flush()
    except IntegrityError as error: db.rollback(); raise HTTPException(409,"Código de vaga já existe") from error
    audit(db,context=c,request=request,action="create",entity="vacancy",entity_id=str(obj.id),details=obj.title,after=model_snapshot(obj)); db.commit(); db.refresh(obj); return obj
@router.get("/api/vacancies/{vacancy_id}",response_model=VacancyRead,tags=["ats"])
def vacancy_get(vacancy_id:int,c:Annotated[AuthContext,Depends(require_permissions(Permission.vacancies_read))],db:Annotated[Session,Depends(get_db)]): return scoped_vacancy(db,c.tenant_id,vacancy_id)
@router.put("/api/vacancies/{vacancy_id}",response_model=VacancyRead,tags=["ats"])
def vacancy_update(vacancy_id:int,payload:VacancyCreate,request:Request,c:Annotated[AuthContext,Depends(require_permissions(Permission.vacancies_write))],db:Annotated[Session,Depends(get_db)]):
    obj=scoped_vacancy(db,c.tenant_id,vacancy_id); before=model_snapshot(obj); data=payload.model_dump(); data["profession"]=normalize_profession(data["profession"])
    for key,value in data.items(): setattr(obj,key,value)
    audit(db,context=c,request=request,action="update",entity="vacancy",entity_id=str(obj.id),details=obj.title,before=before,after=model_snapshot(obj)); db.commit(); db.refresh(obj); return obj
@router.delete("/api/vacancies/{vacancy_id}",status_code=204,tags=["ats"])
def vacancy_delete(vacancy_id:int,request:Request,c:Annotated[AuthContext,Depends(require_permissions(Permission.vacancies_write))],db:Annotated[Session,Depends(get_db)]):
    obj=scoped_vacancy(db,c.tenant_id,vacancy_id); before=model_snapshot(obj); obj.deleted_at=utcnow()
    audit(db,context=c,request=request,action="soft_delete",entity="vacancy",entity_id=str(obj.id),before=before,after=model_snapshot(obj)); db.commit()

@router.get("/api/applications",response_model=list[ApplicationRead],tags=["ats"])
def applications(c:Annotated[AuthContext,Depends(require_permissions(Permission.candidates_read))],db:Annotated[Session,Depends(get_db)],candidate_id:int|None=None,vacancy_id:int|None=None,limit:int=Query(100,ge=1,le=300)):
    stmt=select(Application).where(Application.tenant_id==c.tenant_id)
    if candidate_id is not None: stmt=stmt.where(Application.candidate_id==candidate_id)
    if vacancy_id is not None: stmt=stmt.where(Application.vacancy_id==vacancy_id)
    return db.scalars(stmt.order_by(Application.updated_at.desc()).limit(limit)).all()
@router.post("/api/applications",response_model=ApplicationRead,status_code=201,tags=["ats"])
def application_create(payload:ApplicationCreate,request:Request,c:Annotated[AuthContext,Depends(require_permissions(Permission.applications_manage))],db:Annotated[Session,Depends(get_db)]):
    candidate=scoped_candidate(db,c.tenant_id,payload.candidate_id); vacancy=scoped_vacancy(db,c.tenant_id,payload.vacancy_id)
    obj=Application(tenant_id=c.tenant_id,**payload.model_dump()); db.add(obj)
    try: db.flush()
    except IntegrityError as error: db.rollback(); raise HTTPException(409,"Candidato já está nesta vaga") from error
    audit(db,context=c,request=request,action="create",entity="application",entity_id=str(obj.id),details=f"{candidate.name} → {vacancy.code}",after=model_snapshot(obj)); db.commit(); db.refresh(obj); return obj
@router.patch("/api/applications/{application_id}",response_model=ApplicationRead,tags=["ats"])
def application_update(application_id:int,payload:ApplicationUpdate,request:Request,c:Annotated[AuthContext,Depends(require_permissions(Permission.applications_manage))],db:Annotated[Session,Depends(get_db)]):
    obj=scoped(db,Application,c.tenant_id,application_id,"Candidatura não encontrada"); before=model_snapshot(obj)
    for key,value in payload.model_dump(exclude_unset=True).items(): setattr(obj,key,value)
    audit(db,context=c,request=request,action="update_stage" if payload.stage else "update",entity="application",entity_id=str(obj.id),before=before,after=model_snapshot(obj)); db.commit(); db.refresh(obj); return obj

@router.get("/api/departments",response_model=list[DepartmentRead],tags=["people"])
def departments(c:Annotated[AuthContext,Depends(require_permissions(Permission.employees_read))],db:Annotated[Session,Depends(get_db)]): return db.scalars(select(Department).where(Department.tenant_id==c.tenant_id).order_by(Department.name)).all()
@router.post("/api/departments",response_model=DepartmentRead,status_code=201,tags=["people"])
def department_create(payload:DepartmentCreate,request:Request,c:Annotated[AuthContext,Depends(require_permissions(Permission.employees_write))],db:Annotated[Session,Depends(get_db)]):
    obj=Department(tenant_id=c.tenant_id,**payload.model_dump()); db.add(obj)
    try: db.flush()
    except IntegrityError as error: db.rollback(); raise HTTPException(409,"Código de departamento já existe") from error
    audit(db,context=c,request=request,action="create",entity="department",entity_id=str(obj.id),details=obj.name,after=model_snapshot(obj)); db.commit(); db.refresh(obj); return obj
def validate_employee_refs(db,tenant_id,payload):
    for model,object_id,label in ((Department,payload.department_id,"Departamento"),(Employee,payload.manager_id,"Gestor"),(Candidate,payload.candidate_id,"Candidato")):
        if object_id is not None and not db.scalar(select(model.id).where(model.id==object_id,model.tenant_id==tenant_id)): raise HTTPException(404,f"{label} não encontrado nesta empresa")
    if payload.user_id is not None and not db.scalar(select(Membership.id).where(Membership.tenant_id==tenant_id,Membership.user_id==payload.user_id,Membership.active.is_(True))): raise HTTPException(404,"Usuário não pertence a esta empresa")
@router.get("/api/employees/me",response_model=EmployeeRead,tags=["people"])
def employee_me(c:Annotated[AuthContext,Depends(current_context)],db:Annotated[Session,Depends(get_db)]): return own_employee(db,c)
@router.get("/api/employees",response_model=list[EmployeeRead],tags=["people"])
def employees(c:Annotated[AuthContext,Depends(require_permissions(Permission.employees_read))],db:Annotated[Session,Depends(get_db)],q:str="",limit:int=Query(100,ge=1,le=300)):
    stmt=select(Employee).where(Employee.tenant_id==c.tenant_id)
    if q.strip():
        like=f"%{q.strip()}%"; stmt=stmt.where(or_(Employee.full_name.ilike(like),Employee.employee_number.ilike(like),Employee.job_title.ilike(like),Employee.corporate_email.ilike(like)))
    return db.scalars(stmt.order_by(Employee.full_name).limit(limit)).all()
@router.post("/api/employees",response_model=EmployeeRead,status_code=201,tags=["people"])
def employee_create(payload:EmployeeCreate,request:Request,c:Annotated[AuthContext,Depends(require_permissions(Permission.employees_write))],db:Annotated[Session,Depends(get_db)]):
    validate_employee_refs(db,c.tenant_id,payload); obj=Employee(tenant_id=c.tenant_id,**payload.model_dump()); db.add(obj)
    try: db.flush()
    except IntegrityError as error: db.rollback(); raise HTTPException(409,"Matrícula já existe nesta empresa") from error
    audit(db,context=c,request=request,action="create",entity="employee",entity_id=str(obj.id),details=obj.full_name,after=model_snapshot(obj)); db.commit(); db.refresh(obj); return obj
@router.get("/api/employees/{employee_id}",response_model=EmployeeRead,tags=["people"])
def employee_get(employee_id:int,c:Annotated[AuthContext,Depends(require_permissions(Permission.employees_read))],db:Annotated[Session,Depends(get_db)]): return scoped(db,Employee,c.tenant_id,employee_id,"Colaborador não encontrado")
@router.put("/api/employees/{employee_id}",response_model=EmployeeRead,tags=["people"])
def employee_update(employee_id:int,payload:EmployeeCreate,request:Request,c:Annotated[AuthContext,Depends(require_permissions(Permission.employees_write))],db:Annotated[Session,Depends(get_db)]):
    obj=scoped(db,Employee,c.tenant_id,employee_id,"Colaborador não encontrado"); validate_employee_refs(db,c.tenant_id,payload); before=model_snapshot(obj)
    for key,value in payload.model_dump().items(): setattr(obj,key,value)
    audit(db,context=c,request=request,action="update",entity="employee",entity_id=str(obj.id),details=obj.full_name,before=before,after=model_snapshot(obj)); db.commit(); db.refresh(obj); return obj

@router.get("/api/onboarding",response_model=list[OnboardingTaskRead],tags=["workforce"])
def onboarding(c:Annotated[AuthContext,Depends(require_permissions(Permission.onboarding_manage))],db:Annotated[Session,Depends(get_db)],employee_id:int|None=None):
    stmt=select(OnboardingTask).where(OnboardingTask.tenant_id==c.tenant_id)
    if employee_id is not None: stmt=stmt.where(OnboardingTask.employee_id==employee_id)
    return db.scalars(stmt.order_by(OnboardingTask.status,OnboardingTask.due_date)).all()
@router.get("/api/onboarding/me",response_model=list[OnboardingTaskRead],tags=["workforce"])
def onboarding_me(c:Annotated[AuthContext,Depends(current_context)],db:Annotated[Session,Depends(get_db)]):
    employee=own_employee(db,c); return db.scalars(select(OnboardingTask).where(OnboardingTask.tenant_id==c.tenant_id,OnboardingTask.employee_id==employee.id).order_by(OnboardingTask.status,OnboardingTask.due_date)).all()
@router.post("/api/onboarding",response_model=OnboardingTaskRead,status_code=201,tags=["workforce"])
def onboarding_create(payload:OnboardingTaskCreate,request:Request,c:Annotated[AuthContext,Depends(require_permissions(Permission.onboarding_manage))],db:Annotated[Session,Depends(get_db)]):
    scoped(db,Employee,c.tenant_id,payload.employee_id,"Colaborador não encontrado"); obj=OnboardingTask(tenant_id=c.tenant_id,**payload.model_dump()); db.add(obj); db.flush()
    audit(db,context=c,request=request,action="create",entity="onboarding_task",entity_id=str(obj.id),details=obj.title,after=model_snapshot(obj)); db.commit(); db.refresh(obj); return obj
@router.patch("/api/onboarding/{task_id}",response_model=OnboardingTaskRead,tags=["workforce"])
def onboarding_update(task_id:int,payload:OnboardingTaskUpdate,request:Request,c:Annotated[AuthContext,Depends(require_permissions(Permission.onboarding_manage))],db:Annotated[Session,Depends(get_db)]):
    obj=scoped(db,OnboardingTask,c.tenant_id,task_id,"Tarefa não encontrada"); before=model_snapshot(obj)
    for key,value in payload.model_dump(exclude_unset=True).items(): setattr(obj,key,value)
    if payload.status==TaskStatus.concluida and obj.completed_at is None: obj.completed_at=datetime.now(UTC).replace(tzinfo=None)
    elif payload.status and payload.status!=TaskStatus.concluida: obj.completed_at=None
    audit(db,context=c,request=request,action="update",entity="onboarding_task",entity_id=str(obj.id),details=obj.title,before=before,after=model_snapshot(obj)); db.commit(); db.refresh(obj); return obj

@router.get("/api/benefits",response_model=list[BenefitPlanRead],tags=["workforce"])
def benefits(c:Annotated[AuthContext,Depends(current_context)],db:Annotated[Session,Depends(get_db)]): return db.scalars(select(BenefitPlan).where(BenefitPlan.tenant_id==c.tenant_id,BenefitPlan.active.is_(True)).order_by(BenefitPlan.name)).all()
@router.post("/api/benefits",response_model=BenefitPlanRead,status_code=201,tags=["workforce"])
def benefit_create(payload:BenefitPlanCreate,request:Request,c:Annotated[AuthContext,Depends(require_permissions(Permission.benefits_manage))],db:Annotated[Session,Depends(get_db)]):
    obj=BenefitPlan(tenant_id=c.tenant_id,**payload.model_dump()); db.add(obj)
    try: db.flush()
    except IntegrityError as error: db.rollback(); raise HTTPException(409,"Benefício já cadastrado") from error
    audit(db,context=c,request=request,action="create",entity="benefit_plan",entity_id=str(obj.id),details=obj.name,after=model_snapshot(obj)); db.commit(); db.refresh(obj); return obj

@router.get("/api/time-entries",response_model=list[TimeEntryRead],tags=["workforce"])
def time_entries(c:Annotated[AuthContext,Depends(current_context)],db:Annotated[Session,Depends(get_db)],employee_id:int|None=None,limit:int=Query(100,ge=1,le=500)):
    allowed=time_employee_scope(db,c); target=employee_id
    if target is not None and allowed is not None and target not in allowed: raise HTTPException(404,"Colaborador não encontrado")
    stmt=select(TimeEntry).where(TimeEntry.tenant_id==c.tenant_id)
    if target is not None: stmt=stmt.where(TimeEntry.employee_id==target)
    elif allowed is not None: stmt=stmt.where(TimeEntry.employee_id.in_(allowed))
    return db.scalars(stmt.order_by(TimeEntry.recorded_at.desc()).limit(limit)).all()
@router.post("/api/time-entries",response_model=TimeEntryRead,status_code=201,tags=["workforce"])
def time_create(payload:TimeEntryCreate,request:Request,c:Annotated[AuthContext,Depends(current_context)],db:Annotated[Session,Depends(get_db)]):
    employee=scoped(db,Employee,c.tenant_id,payload.employee_id,"Colaborador não encontrado")
    is_own=employee.user_id==c.user.id and Permission.time_own in c.permissions
    is_provider_import=Permission.time_manage in c.permissions and payload.source in {"provider","import"}
    if not is_own and not is_provider_import: raise HTTPException(403,"Marcações brutas só podem vir do próprio colaborador ou de integração autorizada")
    obj=TimeEntry(tenant_id=c.tenant_id,created_by_id=c.user.id,integrity_hash=time_entry_hash(c.tenant_id,employee.id,payload.kind,payload.recorded_at),**payload.model_dump()); db.add(obj); db.flush()
    audit(db,context=c,request=request,action="create",entity="time_entry",entity_id=str(obj.id),details=f"{employee.employee_number}:{obj.kind.value}",after=model_snapshot(obj)); db.commit(); db.refresh(obj); return obj

@router.get("/api/payroll-documents",response_model=list[PayrollDocumentRead],tags=["workforce"])
def payroll(c:Annotated[AuthContext,Depends(current_context)],db:Annotated[Session,Depends(get_db)],employee_id:int|None=None):
    if Permission.payroll_manage in c.permissions: target=employee_id
    elif Permission.payroll_own in c.permissions:
        target=own_employee(db,c).id
        if employee_id is not None and employee_id!=target: raise HTTPException(403,"Acesso limitado aos próprios documentos")
    else: raise HTTPException(403,"Permissão insuficiente")
    stmt=select(PayrollDocument).where(PayrollDocument.tenant_id==c.tenant_id)
    if target is not None: stmt=stmt.where(PayrollDocument.employee_id==target)
    return db.scalars(stmt.order_by(PayrollDocument.competence.desc())).all()
@router.post("/api/payroll-documents",response_model=PayrollDocumentRead,status_code=201,tags=["workforce"])
def payroll_create(payload:PayrollDocumentCreate,request:Request,c:Annotated[AuthContext,Depends(require_permissions(Permission.payroll_manage))],db:Annotated[Session,Depends(get_db)]):
    scoped(db,Employee,c.tenant_id,payload.employee_id,"Colaborador não encontrado"); obj=PayrollDocument(tenant_id=c.tenant_id,**payload.model_dump()); db.add(obj)
    try: db.flush()
    except IntegrityError as error: db.rollback(); raise HTTPException(409,"Documento já existe para a competência") from error
    audit(db,context=c,request=request,action="publish",entity="payroll_document",entity_id=str(obj.id),details=f"{obj.competence}:{obj.kind}",after=model_snapshot(obj)); db.commit(); db.refresh(obj); return obj

@router.get("/api/knowledge/documents",response_model=list[KnowledgeDocumentRead],tags=["knowledge"])
def knowledge_docs(c:Annotated[AuthContext,Depends(require_permissions(Permission.knowledge_read))],db:Annotated[Session,Depends(get_db)],limit:int=Query(100,ge=1,le=300)):
    stmt=select(KnowledgeDocument).where(KnowledgeDocument.tenant_id==c.tenant_id,KnowledgeDocument.status=="published")
    if c.membership.role.value not in {"tenant_owner","admin","hr"}: stmt=stmt.where(KnowledgeDocument.visibility!=KnowledgeVisibility.rh)
    if c.membership.role.value not in {"tenant_owner","admin","hr","manager"}: stmt=stmt.where(KnowledgeDocument.visibility==KnowledgeVisibility.todos)
    return db.scalars(stmt.order_by(KnowledgeDocument.updated_at.desc()).limit(limit)).all()
@router.post("/api/knowledge/documents",response_model=KnowledgeDocumentRead,status_code=201,tags=["knowledge"])
def knowledge_create(payload:KnowledgeDocumentCreate,request:Request,c:Annotated[AuthContext,Depends(require_permissions(Permission.knowledge_manage))],db:Annotated[Session,Depends(get_db)]):
    obj=KnowledgeDocument(tenant_id=c.tenant_id,owner_id=c.user.id,**payload.model_dump()); db.add(obj); db.flush()
    audit(db,context=c,request=request,action="publish",entity="knowledge_document",entity_id=str(obj.id),details=obj.title,after=model_snapshot(obj)); db.commit(); db.refresh(obj); return obj
@router.put("/api/knowledge/documents/{document_id}",response_model=KnowledgeDocumentRead,tags=["knowledge"])
def knowledge_update(document_id:int,payload:KnowledgeDocumentCreate,request:Request,c:Annotated[AuthContext,Depends(require_permissions(Permission.knowledge_manage))],db:Annotated[Session,Depends(get_db)]):
    obj=scoped(db,KnowledgeDocument,c.tenant_id,document_id,"Documento não encontrado"); before=model_snapshot(obj)
    for key,value in payload.model_dump().items(): setattr(obj,key,value)
    obj.version+=1; audit(db,context=c,request=request,action="new_version",entity="knowledge_document",entity_id=str(obj.id),details=obj.title,before=before,after=model_snapshot(obj)); db.commit(); db.refresh(obj); return obj
@router.post("/api/knowledge/ask",response_model=KnowledgeAnswer,tags=["knowledge"])
def ask(payload:KnowledgeQuestion,request:Request,c:Annotated[AuthContext,Depends(require_permissions(Permission.knowledge_read))],db:Annotated[Session,Depends(get_db)]):
    answer=knowledge_answer(db,c,payload.question); audit(db,context=c,request=request,action="ask",entity="knowledge_assistant",entity_id="",details=f"grounded={answer['grounded']};citations={len(answer['citations'])}"); db.commit(); return answer

@router.get("/api/dashboard",response_model=DashboardRead,tags=["operations"])
def dashboard_api(c:Annotated[AuthContext,Depends(require_permissions(Permission.reports_read))],db:Annotated[Session,Depends(get_db)]): return dashboard(db,c.tenant_id)
@router.get("/api/financial",response_model=list[FinancialRead],tags=["operations"])
def financial(c:Annotated[AuthContext,Depends(require_permissions(Permission.reports_read))],db:Annotated[Session,Depends(get_db)]): return db.scalars(select(FinancialReference).where(FinancialReference.tenant_id==c.tenant_id).order_by(FinancialReference.service)).all()
@router.post("/api/financial",response_model=FinancialRead,status_code=201,tags=["operations"])
def financial_create(payload:FinancialCreate,request:Request,c:Annotated[AuthContext,Depends(require_permissions(Permission.tenant_manage))],db:Annotated[Session,Depends(get_db)]):
    obj=FinancialReference(tenant_id=c.tenant_id,**payload.model_dump()); db.add(obj)
    try: db.flush()
    except IntegrityError as error: db.rollback(); raise HTTPException(409,"Referência já cadastrada") from error
    audit(db,context=c,request=request,action="create",entity="financial_reference",entity_id=str(obj.id),details=obj.service,after=model_snapshot(obj)); db.commit(); db.refresh(obj); return obj
@router.get("/api/audit",response_model=list[AuditRead],tags=["operations"])
def audit_list(c:Annotated[AuthContext,Depends(require_permissions(Permission.audit_read))],db:Annotated[Session,Depends(get_db)],action:str|None=None,entity:str|None=None,actor:str|None=None,created_from:datetime|None=None,created_to:datetime|None=None,limit:int=Query(200,ge=1,le=1000)):
    stmt=select(AuditLog).where(AuditLog.tenant_id==c.tenant_id)
    if action: stmt=stmt.where(AuditLog.action==action)
    if entity: stmt=stmt.where(AuditLog.entity==entity)
    if actor: stmt=stmt.where(AuditLog.actor.ilike(f"%{actor}%"))
    if created_from: stmt=stmt.where(AuditLog.created_at>=created_from)
    if created_to: stmt=stmt.where(AuditLog.created_at<=created_to)
    return db.scalars(stmt.order_by(AuditLog.created_at.desc()).limit(limit)).all()
@router.get("/api/export/candidates.csv",tags=["operations"])
def export_candidates(request:Request,c:Annotated[AuthContext,Depends(require_permissions(Permission.candidates_read))],db:Annotated[Session,Depends(get_db)]):
    output=io.StringIO(); writer=csv.writer(output); writer.writerow(["id","nome","profissão","cidade","telefone","e-mail","status","cadastrado_em"])
    items=db.scalars(select(Candidate).where(Candidate.tenant_id==c.tenant_id,Candidate.deleted_at.is_(None)).order_by(Candidate.name)).all()
    for x in items: writer.writerow([x.id,x.name,x.profession,x.city,x.phone,x.email,x.status.value,x.created_at.isoformat()])
    audit(db,context=c,request=request,action="export",entity="candidate",entity_id="",details=f"rows={len(items)}"); db.commit()
    return StreamingResponse(iter(["\ufeff"+output.getvalue()]),media_type="text/csv; charset=utf-8",headers={"Content-Disposition":"attachment; filename=chs-candidates.csv"})
