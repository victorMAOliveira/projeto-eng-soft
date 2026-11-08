"""Initial schema: internships.

Revision ID: 0001
Revises:
"""

import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "internships",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("company_id", sa.Integer, nullable=False),
        sa.Column("company_name", sa.String(150), nullable=False),
        sa.Column("title", sa.String(150), nullable=False),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("requirements", sa.JSON, nullable=False),
        sa.Column("course", sa.String(120), nullable=False),
        sa.Column("min_semester", sa.Integer, nullable=False),
        sa.Column("hours_per_day", sa.Integer, nullable=False),
        sa.Column("hours_per_week", sa.Integer, nullable=False),
        sa.Column("modality", sa.String(10), nullable=False),
        sa.Column("city", sa.String(80), nullable=False),
        sa.Column("stipend", sa.Float, nullable=False),
        sa.Column("positions", sa.Integer, nullable=False, server_default="1"),
        sa.Column("status", sa.String(10), nullable=False, server_default="open"),
        sa.Column(
            "published_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("closed_at", sa.DateTime(timezone=True)),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint("hours_per_day <= 6", name="max_hours_per_day"),
        sa.CheckConstraint("hours_per_week <= 30", name="max_hours_per_week"),
    )
    op.create_index("ix_internships_company_id", "internships", ["company_id"])
    op.create_index("ix_internships_course", "internships", ["course"])
    op.create_index("ix_internships_status", "internships", ["status"])


def downgrade() -> None:
    op.drop_table("internships")
