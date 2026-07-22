"""Auth: users.active + sessions table.

Additive, dual-engine (DEC-006) — runs unmodified on SQLite and Postgres,
no dialect-specific SQL. `users.active` supports seeded-config revocation
(rows are never deleted); `sessions.token_hash` holds only the SHA-256 hex
of the opaque bearer token — the raw token is never stored.

Revision ID: 0002
Revises: 0001
Create Date: 2026-07-22

"""

import sqlalchemy as sa

from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
    )

    op.create_table(
        "sessions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("token_hash", name="uq_sessions_token_hash"),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_sessions_user_id_users"
        ),
    )


def downgrade() -> None:
    op.drop_table("sessions")
    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_column("active")
