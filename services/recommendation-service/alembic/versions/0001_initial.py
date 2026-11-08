"""Initial read model: rm_students, rm_internships, rm_applications, processed_events.

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
        "rm_students",
        sa.Column("student_id", sa.Integer, primary_key=True, autoincrement=False),
        sa.Column("name", sa.String(150), nullable=False, server_default=""),
        sa.Column("course", sa.String(120)),
        sa.Column("semester", sa.Integer),
        sa.Column("skills", sa.JSON, nullable=False),
        sa.Column("resume_summary", sa.Text, nullable=False, server_default=""),
        sa.Column("weekly_availability_hours", sa.Integer),
        sa.Column("preferred_modality", sa.String(10)),
        sa.Column("city", sa.String(80)),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_table(
        "rm_internships",
        sa.Column("internship_id", sa.Integer, primary_key=True, autoincrement=False),
        sa.Column("company_id", sa.Integer, nullable=False, index=True),
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
        sa.Column("status", sa.String(10), nullable=False, server_default="open", index=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("popularity", sa.Integer, nullable=False, server_default="0"),
    )
    op.create_table(
        "rm_applications",
        sa.Column("application_id", sa.Integer, primary_key=True, autoincrement=False),
        sa.Column("internship_id", sa.Integer, nullable=False, index=True),
        sa.Column("student_id", sa.Integer, nullable=False, index=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="submitted"),
        sa.UniqueConstraint("internship_id", "student_id", name="uq_rm_applications_internship_id"),
    )
    op.create_table(
        "processed_events",
        sa.Column("event_id", sa.String(64), primary_key=True),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column(
            "processed_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )


def downgrade() -> None:
    for table in ("processed_events", "rm_applications", "rm_internships", "rm_students"):
        op.drop_table(table)
