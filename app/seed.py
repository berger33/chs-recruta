from __future__ import annotations
import os
from datetime import UTC,datetime,timedelta
from decimal import Decimal
from sqlalchemy import select
from .database import Base,SessionLocal,activate_tenant_scope,engine
from .models import BenefitPlan,Department,Employee,EmploymentStatus,KnowledgeDocument,KnowledgeVisibility,Membership,Role,Subscription,SubscriptionStatus,Tenant,User
from .security import hash_password

def main():
    Base.metadata.create_all(bind=engine)
    username=os.getenv("DEMO_ADMIN_USERNAME","demo").strip().lower(); password=os.getenv("DEMO_ADMIN_PASSWORD","")
    email=os.getenv("DEMO_ADMIN_EMAIL","demo@example.com").strip().lower(); slug=os.getenv("DEMO_TENANT_SLUG","empresa-demo").strip().lower(); name=os.getenv("DEMO_TENANT_NAME","Empresa Demonstração").strip()
    with SessionLocal() as db:
        tenant=db.scalar(select(Tenant).where(Tenant.slug==slug))
        if not tenant: tenant=Tenant(name=name,slug=slug,legal_name=name); db.add(tenant); db.flush()
        user=db.scalar(select(User).where(User.username==username))
        if not user:
            if not password: raise RuntimeError("Defina DEMO_ADMIN_PASSWORD antes de criar o usuário demonstrativo")
            user=User(username=username,display_name="Administrador Demonstração",email=email,password_hash=hash_password(password),platform_admin=True); db.add(user); db.flush()
        if not db.scalar(select(Membership).where(Membership.tenant_id==tenant.id,Membership.user_id==user.id)): db.add(Membership(tenant_id=tenant.id,user_id=user.id,role=Role.tenant_owner))
        activate_tenant_scope(db,tenant.id)
        if not db.scalar(select(Subscription).where(Subscription.tenant_id==tenant.id)): db.add(Subscription(tenant_id=tenant.id,plan_code="professional",status=SubscriptionStatus.trial,employee_limit=100,enabled_modules=["ats","core_hr","onboarding","benefits","time","payroll","knowledge"],trial_ends_at=datetime.now(UTC).replace(tzinfo=None)+timedelta(days=30)))
        department=db.scalar(select(Department).where(Department.tenant_id==tenant.id,Department.code=="RH"))
        if not department: department=Department(tenant_id=tenant.id,name="Recursos Humanos",code="RH"); db.add(department); db.flush()
        if not db.scalar(select(Employee).where(Employee.tenant_id==tenant.id,Employee.employee_number=="ADM-001")): db.add(Employee(tenant_id=tenant.id,user_id=user.id,department_id=department.id,employee_number="ADM-001",full_name=user.display_name,corporate_email=user.email,job_title="Recursos Humanos",status=EmploymentStatus.ativo))
        if not db.scalar(select(BenefitPlan).where(BenefitPlan.tenant_id==tenant.id,BenefitPlan.name=="Vale-refeição")): db.add(BenefitPlan(tenant_id=tenant.id,name="Vale-refeição",category="Alimentação",provider="Configurar fornecedor",employee_cost=Decimal("0.00")))
        if not db.scalar(select(KnowledgeDocument).where(KnowledgeDocument.tenant_id==tenant.id,KnowledgeDocument.title=="Como usar o assistente corporativo")): db.add(KnowledgeDocument(tenant_id=tenant.id,title="Como usar o assistente corporativo",content="O assistente responde somente com base em documentos publicados pela empresa. Quando não encontrar uma fonte autorizada, orientará o usuário a procurar o RH. Confira sempre as citações.",visibility=KnowledgeVisibility.todos,owner_id=user.id))
        db.commit()
if __name__=="__main__": main()
