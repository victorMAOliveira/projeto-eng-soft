"""Initial schema: applications, placements, status_changes, processed_events.

Revision ID: 0001
Revises:
"""

import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def _ts(name: str) -> sa.Column:
    return sa.Column(name, sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)


def upgrade() -> None:
    op.create_table(
        "applications",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("internship_id", sa.Integer, nullable=False, index=True),
        sa.Column("student_id", sa.Integer, nullable=False, index=True),
        sa.Column("company_id", sa.Integer, nullable=False, index=True),
        sa.Column("student_name", sa.String(150), nullable=False),
        sa.Column("company_name", sa.String(150), nullable=False),
        sa.Column("internship_title", sa.String(150), nullable=False),
        sa.Column("student_course", sa.String(120)),
        sa.Column("student_is_pcd", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("internship_hours_per_day", sa.Integer, nullable=False),
        sa.Column("internship_hours_per_week", sa.Integer, nullable=False),
        sa.Column("internship_stipend", sa.Float, nullable=False),
        sa.Column("cover_letter", sa.Text, nullable=False, server_default=""),
        sa.Column("status", sa.String(20), nullable=False, index=True),
        sa.Column("status_reason", sa.Text),
        _ts("created_at"),
        _ts("updated_at"),
        sa.UniqueConstraint("internship_id", "student_id", name="uq_applications_internship_id"),
    )
    op.create_table(
        "placements",
        sa.Column(
            "application_id",
            sa.Integer,
            sa.ForeignKey("applications.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("start_date", sa.Date, nullable=False),
        sa.Column("end_date", sa.Date, nullable=False),
        sa.Column("hours_per_day", sa.Integer, nullable=False),
        sa.Column("hours_per_week", sa.Integer, nullable=False),
        sa.Column("stipend", sa.Float, nullable=False),
        sa.Column("insurer", sa.String(120), nullable=False),
        sa.Column("insurance_policy", sa.String(60), nullable=False),
        sa.Column("supervisor_name", sa.String(150), nullable=False),
        sa.Column("activities", sa.Text, nullable=False, server_default=""),
        sa.Column("agreement_id", sa.String(64)),
        sa.Column("activated_at", sa.DateTime(timezone=True)),
        sa.Column("last_report_at", sa.Date),
        sa.Column("next_report_due", sa.Date),
        sa.Column("reports_count", sa.Integer, nullable=False, server_default="0"),
        _ts("created_at"),
        _ts("updated_at"),
        sa.CheckConstraint("hours_per_day <= 6", name="placement_max_hours_per_day"),
        sa.CheckConstraint("hours_per_week <= 30", name="placement_max_hours_per_week"),
    )
    op.create_table(
        "status_changes",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "application_id",
            sa.Integer,
            sa.ForeignKey("applications.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("from_status", sa.String(20)),
        sa.Column("to_status", sa.String(20), nullable=False),
        sa.Column("actor_id", sa.Integer, nullable=False),
        sa.Column("actor_role", sa.String(20), nullable=False),
        sa.Column("reason", sa.Text),
        _ts("created_at"),
    )
    op.create_table(
        "processed_events",
        sa.Column("event_id", sa.String(64), primary_key=True),
        sa.Column("event_type", sa.String(64), nullable=False),
        _ts("processed_at"),
    )


def downgrade() -> None:
    op.drop_table("processed_events")
    op.drop_table("status_changes")
    op.drop_table("placements")
    op.drop_table("applications")
