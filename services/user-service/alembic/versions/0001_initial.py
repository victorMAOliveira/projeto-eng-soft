"""Initial schema: users, student_profiles, company_profiles.

Revision ID: 0001
Revises:
"""

import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def _timestamps() -> list[sa.Column]:
    return [
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    ]


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("full_name", sa.String(150), nullable=False),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.true()),
        *_timestamps(),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)
    op.create_index("ix_users_role", "users", ["role"])
    op.create_table(
        "student_profiles",
        sa.Column(
            "user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
        ),
        sa.Column("course", sa.String(120)),
        sa.Column("semester", sa.Integer),
        sa.Column("enrollment", sa.String(30)),
        sa.Column("skills", sa.JSON, nullable=False),
        sa.Column("resume_summary", sa.Text, nullable=False, server_default=""),
        sa.Column("weekly_availability_hours", sa.Integer),
        sa.Column("preferred_modality", sa.String(10)),
        sa.Column("city", sa.String(80)),
        sa.Column("is_pcd", sa.Boolean, nullable=False, server_default=sa.false()),
        *_timestamps(),
    )
    op.create_table(
        "company_profiles",
        sa.Column(
            "user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
        ),
        sa.Column("trade_name", sa.String(150), nullable=False),
        sa.Column("cnpj", sa.String(18)),
        sa.Column("sector", sa.String(80)),
        sa.Column("city", sa.String(80)),
        sa.Column("description", sa.Text, nullable=False, server_default=""),
        sa.Column("website", sa.String(200)),
        *_timestamps(),
    )


def downgrade() -> None:
    op.drop_table("company_profiles")
    op.drop_table("student_profiles")
    op.drop_index("ix_users_role", table_name="users")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
