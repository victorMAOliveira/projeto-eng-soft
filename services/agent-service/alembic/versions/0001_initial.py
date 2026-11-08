"""Initial schema: agent_runs, agent_steps, alerts_sent.

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
        "agent_runs",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("agent", sa.String(40), nullable=False, index=True),
        sa.Column("user_id", sa.Integer, nullable=False, index=True),
        sa.Column("user_role", sa.String(20), nullable=False),
        sa.Column("mode", sa.String(10), nullable=False),
        sa.Column("model", sa.String(60)),
        sa.Column("input", sa.JSON, nullable=False),
        sa.Column("output", sa.Text, nullable=False, server_default=""),
        sa.Column("cover_letter", sa.Text),
        sa.Column("status", sa.String(20), nullable=False, server_default="running"),
        sa.Column("steps_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("error", sa.Text),
        sa.Column(
            "started_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
    )
    op.create_table(
        "agent_steps",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "run_id",
            sa.Integer,
            sa.ForeignKey("agent_runs.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("position", sa.Integer, nullable=False),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("tool_name", sa.String(60)),
        sa.Column("tool_input", sa.JSON),
        sa.Column("tool_output", sa.JSON),
        sa.Column("ok", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("duration_ms", sa.Float, nullable=False, server_default="0"),
    )
    op.create_table(
        "alerts_sent",
        sa.Column("key", sa.String(120), primary_key=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )


def downgrade() -> None:
    for table in ("alerts_sent", "agent_steps", "agent_runs"):
        op.drop_table(table)
