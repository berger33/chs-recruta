"""add identity security controls

Revision ID: 20260828_07
Revises: 20260828_06
"""

from alembic import op
import sqlalchemy as sa

from app import identity_models  # noqa: F401
from app.database import Base

revision = "20260828_07"
down_revision = "20260828_06"
branch_labels = None
depends_on = None

NEW_TABLES = (
    "user_mfa",
    "mfa_login_challenges",
    "password_reset_tokens",
    "security_rate_events",
    "security_events",
    "privileged_access_grants",
)

USER_COLUMNS = {
    "failed_login_attempts": sa.Column(
        "failed_login_attempts", sa.Integer(), nullable=False, server_default=sa.text("0")
    ),
    "locked_until": sa.Column("locked_until", sa.DateTime(), nullable=True),
    "last_login_at": sa.Column("last_login_at", sa.DateTime(), nullable=True),
    "password_changed_at": sa.Column(
        "password_changed_at", sa.DateTime(), nullable=False, server_default=sa.func.now()
    ),
}

SESSION_COLUMNS = {
    "revoked_at": sa.Column("revoked_at", sa.DateTime(), nullable=True),
    "revoke_reason": sa.Column(
        "revoke_reason", sa.String(160), nullable=False, server_default=""
    ),
    "ip_address": sa.Column(
        "ip_address", sa.String(64), nullable=False, server_default=""
    ),
    "user_agent": sa.Column(
        "user_agent", sa.String(500), nullable=False, server_default=""
    ),
    "device_name": sa.Column(
        "device_name", sa.String(160), nullable=False, server_default=""
    ),
    "mfa_verified": sa.Column(
        "mfa_verified", sa.Boolean(), nullable=False, server_default=sa.false()
    ),
    "authenticated_at": sa.Column(
        "authenticated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()
    ),
    "privileged_grant_id": sa.Column(
        "privileged_grant_id",
        sa.Integer(),
        sa.ForeignKey(
            "privileged_access_grants.id",
            name="fk_session_tokens_privileged_grant_id",
            ondelete="SET NULL",
        ),
        nullable=True,
    ),
}

INDEXES = (
    ("ix_users_locked_until", "users", ["locked_until"]),
    ("ix_session_tokens_revoked_at", "session_tokens", ["revoked_at"]),
    ("ix_session_tokens_mfa_verified", "session_tokens", ["mfa_verified"]),
    ("ix_session_tokens_privileged_grant_id", "session_tokens", ["privileged_grant_id"]),
)


def _column_names(table_name: str) -> set[str]:
    return {item["name"] for item in sa.inspect(op.get_bind()).get_columns(table_name)}


def _index_names(table_name: str) -> set[str]:
    return {item["name"] for item in sa.inspect(op.get_bind()).get_indexes(table_name)}


def upgrade():
    bind = op.get_bind()
    for table_name in NEW_TABLES:
        Base.metadata.tables[table_name].create(bind=bind, checkfirst=True)

    existing_users = _column_names("users")
    for name, column in USER_COLUMNS.items():
        if name not in existing_users:
            op.add_column("users", column)

    existing_sessions = _column_names("session_tokens")
    missing_sessions = [
        column for name, column in SESSION_COLUMNS.items()
        if name not in existing_sessions
    ]
    if bind.dialect.name == "sqlite" and missing_sessions:
        # Batch mode is required when adding the privileged-grant FK to an
        # existing SQLite database.
        with op.batch_alter_table("session_tokens", recreate="always") as batch:
            for column in missing_sessions:
                batch.add_column(column)
    else:
        for column in missing_sessions:
            op.add_column("session_tokens", column)

    for index_name, table_name, columns in INDEXES:
        if index_name not in _index_names(table_name):
            op.create_index(index_name, table_name, columns)

    if bind.dialect.name == "postgresql":
        op.execute('ALTER TABLE "privileged_access_grants" ENABLE ROW LEVEL SECURITY')
        op.execute('ALTER TABLE "privileged_access_grants" FORCE ROW LEVEL SECURITY')
        op.execute(
            """CREATE POLICY privileged_access_grants_tenant_isolation
            ON "privileged_access_grants"
            USING (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::integer)
            WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::integer)"""
        )


def downgrade():
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute(
            'DROP POLICY IF EXISTS privileged_access_grants_tenant_isolation '
            'ON "privileged_access_grants"'
        )
        op.execute('ALTER TABLE "privileged_access_grants" DISABLE ROW LEVEL SECURITY')
    for index_name, table_name, _ in reversed(INDEXES):
        if index_name in _index_names(table_name):
            op.drop_index(index_name, table_name=table_name)
    session_columns = [
        name for name in reversed(tuple(SESSION_COLUMNS))
        if name in _column_names("session_tokens")
    ]
    user_columns = [
        name for name in reversed(tuple(USER_COLUMNS))
        if name in _column_names("users")
    ]
    if bind.dialect.name == "sqlite":
        # SQLite cannot drop a column referenced by an inline FK without
        # rebuilding the table. Alembic batch mode recreates constraints safely.
        with op.batch_alter_table("session_tokens", recreate="always") as batch:
            for name in session_columns:
                batch.drop_column(name)
        with op.batch_alter_table("users", recreate="always") as batch:
            for name in user_columns:
                batch.drop_column(name)
    else:
        for name in session_columns:
            op.drop_column("session_tokens", name)
        for name in user_columns:
            op.drop_column("users", name)
    for table_name in reversed(NEW_TABLES):
        Base.metadata.tables[table_name].drop(bind=bind, checkfirst=True)
