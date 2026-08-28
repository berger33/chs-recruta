"""add time treatment and payroll batches

Revision ID: 20260828_06
Revises: 20260828_05
"""

from alembic import op

from app import time_payroll_models  # noqa: F401
from app.database import Base

revision = "20260828_06"
down_revision = "20260828_05"
branch_labels = None
depends_on = None

TABLES = (
    "work_schedules",
    "employee_schedules",
    "time_adjustment_requests",
    "time_adjustments",
    "timesheets",
    "payroll_batches",
    "payroll_statements",
)


def upgrade():
    bind = op.get_bind()
    for table_name in TABLES:
        Base.metadata.tables[table_name].create(bind=bind, checkfirst=True)

    if bind.dialect.name != "postgresql":
        return
    for table_name in TABLES:
        op.execute(f'ALTER TABLE "{table_name}" ENABLE ROW LEVEL SECURITY')
        op.execute(f'ALTER TABLE "{table_name}" FORCE ROW LEVEL SECURITY')
        op.execute(
            f"""CREATE POLICY {table_name}_tenant_isolation ON "{table_name}"
            USING (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::integer)
            WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::integer)"""
        )


def downgrade():
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        for table_name in reversed(TABLES):
            op.execute(f'DROP POLICY IF EXISTS {table_name}_tenant_isolation ON "{table_name}"')
            op.execute(f'ALTER TABLE "{table_name}" DISABLE ROW LEVEL SECURITY')
    for table_name in reversed(TABLES):
        Base.metadata.tables[table_name].drop(bind=bind, checkfirst=True)

