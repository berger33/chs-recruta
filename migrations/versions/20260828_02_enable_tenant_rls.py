"""enable and force tenant row level security"""
from alembic import op
revision="20260828_02"; down_revision="20260828_01"; branch_labels=None; depends_on=None
TABLES=("candidates","vacancies","applications","departments","employees","onboarding_tasks","benefit_plans","employee_benefits","time_entries","payroll_documents","knowledge_documents","financial_references","subscriptions","audit_logs")
def upgrade():
    if op.get_bind().dialect.name!="postgresql": return
    for table in TABLES:
        op.execute(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY')
        op.execute(f'ALTER TABLE "{table}" FORCE ROW LEVEL SECURITY')
        op.execute(f"""CREATE POLICY {table}_tenant_isolation ON "{table}"
            USING (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::integer)
            WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::integer)""")
def downgrade():
    if op.get_bind().dialect.name!="postgresql": return
    for table in reversed(TABLES):
        op.execute(f'DROP POLICY IF EXISTS {table}_tenant_isolation ON "{table}"')
        op.execute(f'ALTER TABLE "{table}" DISABLE ROW LEVEL SECURITY')
