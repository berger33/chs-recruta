from __future__ import annotations
import hashlib,re,unicodedata
from datetime import date,datetime
from decimal import Decimal
from enum import Enum
from typing import Any
from fastapi import Request
from sqlalchemy import func,or_,select
from sqlalchemy.inspection import inspect
from sqlalchemy.orm import Session
from .models import Application,ApplicationStage,AuditLog,Candidate,CandidateStatus,Employee,KnowledgeDocument,KnowledgeVisibility,OnboardingTask,TaskStatus,TimeEntryKind,Vacancy,VacancyStatus
from .security import AuthContext

ALIASES={"fonoaudiologa":"Fonoaudiólogo","fonoaudiologo":"Fonoaudiólogo","enfermeira":"Enfermeiro","enfermeiro":"Enfermeiro","psicologa":"Psicólogo","psicologo":"Psicólogo","fisioterapeuta":"Fisioterapeuta","nutricionista":"Nutricionista","terapeutaocupacional":"Terapeuta Ocupacional"}
def normalize_text(value):
    value=unicodedata.normalize("NFD",value.lower()); value="".join(c for c in value if unicodedata.category(c)!="Mn")
    return re.sub(r"[^a-z0-9]+"," ",value).strip()
def normalize_profession(value):
    return ALIASES.get(normalize_text(value).replace(" ",""),value.strip().title())
def _json_value(value):
    if isinstance(value,Enum): return value.value
    if isinstance(value,(datetime,date)): return value.isoformat()
    if isinstance(value,Decimal): return str(value)
    return value
def model_snapshot(model): return {c.key:_json_value(getattr(model,c.key)) for c in inspect(model).mapper.column_attrs}
def audit(db:Session,*,context:AuthContext,action:str,entity:str,entity_id:str,request:Request|None=None,details:str="",before:dict|None=None,after:dict|None=None):
    request_id=getattr(request.state,"request_id","") if request else ""
    forwarded=request.headers.get("x-forwarded-for","") if request else ""; ip=forwarded.split(",")[0].strip() if forwarded else ""
    if not ip and request and request.client: ip=request.client.host
    db.add(AuditLog(tenant_id=context.tenant_id,action=action,entity=entity,entity_id=entity_id,actor_user_id=context.user.id,actor=context.user.username,request_id=request_id,ip_address=ip,details=details,before_data=before,after_data=after))
def possible_duplicate(db,tenant_id,name,phone="",registry="",exclude_id=None):
    stmt=select(Candidate).where(Candidate.tenant_id==tenant_id,Candidate.deleted_at.is_(None))
    if exclude_id: stmt=stmt.where(Candidate.id!=exclude_id)
    for c in db.scalars(stmt).all():
        if normalize_text(c.name)==normalize_text(name) and ((phone and normalize_text(c.phone)==normalize_text(phone)) or (registry and normalize_text(c.professional_registry)==normalize_text(registry))): return c
def search_candidates(db,tenant_id,q="",limit=50,offset=0):
    stmt=select(Candidate).where(Candidate.tenant_id==tenant_id,Candidate.deleted_at.is_(None))
    if q.strip():
        like=f"%{q.strip()}%"; stmt=stmt.where(or_(Candidate.name.ilike(like),Candidate.profession.ilike(like),Candidate.city.ilike(like),Candidate.phone.ilike(like),Candidate.email.ilike(like),Candidate.professional_registry.ilike(like)))
    return list(db.scalars(stmt.order_by(Candidate.updated_at.desc()).limit(limit).offset(offset)).all())
def dashboard(db,tenant_id):
    active=(Candidate.tenant_id==tenant_id,Candidate.deleted_at.is_(None))
    candidates=db.scalar(select(func.count(Candidate.id)).where(*active)) or 0
    new=db.scalar(select(func.count(Candidate.id)).where(*active,Candidate.status==CandidateStatus.novo)) or 0
    openv=db.scalar(select(func.count(Vacancy.id)).where(Vacancy.tenant_id==tenant_id,Vacancy.deleted_at.is_(None),Vacancy.status==VacancyStatus.aberta)) or 0
    positions=db.scalar(select(func.coalesce(func.sum(Vacancy.positions),0)).where(Vacancy.tenant_id==tenant_id,Vacancy.deleted_at.is_(None),Vacancy.status==VacancyStatus.aberta)) or 0
    apps=db.scalar(select(func.count(Application.id)).where(Application.tenant_id==tenant_id)) or 0
    hires=db.scalar(select(func.count(Application.id)).where(Application.tenant_id==tenant_id,Application.stage==ApplicationStage.contratado)) or 0
    employees=db.scalar(select(func.count(Employee.id)).where(Employee.tenant_id==tenant_id)) or 0
    pending=db.scalar(select(func.count(OnboardingTask.id)).where(OnboardingTask.tenant_id==tenant_id,OnboardingTask.status.in_([TaskStatus.pendente,TaskStatus.em_andamento]))) or 0
    rows=db.execute(select(Candidate.status,func.count(Candidate.id)).where(*active).group_by(Candidate.status)).all()
    return {"candidates":candidates,"new_candidates":new,"open_vacancies":openv,"open_positions":int(positions),"applications":apps,"hires":hires,"employees":employees,"onboarding_pending":pending,"conversion_rate":round(hires/apps*100 if apps else 0,2),"funnel":{getattr(x,"value",str(x)):n for x,n in rows}}
def time_entry_hash(tenant_id,employee_id,kind:TimeEntryKind,recorded_at): return hashlib.sha256(f"{tenant_id}:{employee_id}:{kind.value}:{recorded_at.isoformat()}".encode()).hexdigest()
def knowledge_answer(db,context,question):
    permitted=[KnowledgeVisibility.todos]; role=context.membership.role.value
    if role in {"manager","tenant_owner","admin","hr"}: permitted.append(KnowledgeVisibility.gestores)
    if role in {"tenant_owner","admin","hr"}: permitted.append(KnowledgeVisibility.rh)
    docs=db.scalars(select(KnowledgeDocument).where(KnowledgeDocument.tenant_id==context.tenant_id,KnowledgeDocument.status=="published",KnowledgeDocument.visibility.in_(permitted))).all()
    terms={x for x in normalize_text(question).split() if len(x)>2}; ranked=[]
    for doc in docs:
        searchable=normalize_text(f"{doc.title} {doc.content}"); score=sum(searchable.count(x) for x in terms)
        if score: ranked.append((score,doc))
    ranked.sort(key=lambda item:(item[0],item[1].updated_at),reverse=True); top=[x for _,x in ranked[:3]]
    if not top: return {"answer":"Não encontrei uma fonte corporativa autorizada para responder com segurança. Encaminhe a dúvida ao RH.","grounded":False,"citations":[]}
    citations=[]
    for doc in top:
        compact=re.sub(r"\s+"," ",doc.content).strip()
        citations.append({"document_id":doc.id,"title":doc.title,"excerpt":compact[:360]+("…" if len(compact)>360 else ""),"version":doc.version})
    answer="Com base nas fontes corporativas autorizadas:\n\n"+"\n\n".join(x["excerpt"] for x in citations)
    return {"answer":answer,"grounded":True,"citations":citations}
