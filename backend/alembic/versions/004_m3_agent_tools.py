"""M3 durable agent runs and tool calls."""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "agent_runs",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column(
            "conversation_id",
            sa.UUID(),
            sa.ForeignKey("conversations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id", sa.UUID(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("status", sa.String(32), nullable=False, server_default="running"),
        sa.Column("allowed_tools", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("model_context", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("step_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("elapsed_ms", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "status IN ('running','waiting_confirmation','completed','limit_reached','failed')",
            name="ck_agent_runs_status",
        ),
    )
    op.create_table(
        "tool_calls",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column(
            "run_id", sa.UUID(), sa.ForeignKey("agent_runs.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("step_number", sa.Integer(), nullable=False),
        sa.Column("provider_call_id", sa.String(256), nullable=False),
        sa.Column("tool_name", sa.String(128), nullable=False),
        sa.Column("arguments", sa.Text(), nullable=False),
        sa.Column("side_effect", sa.String(8), nullable=False),
        sa.Column("impact", sa.Text(), nullable=False, server_default=""),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("result", sa.Text()),
        sa.Column("error", sa.Text()),
        sa.Column("expires_at", sa.DateTime(timezone=True)),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "side_effect IN ('read','write')", name="ck_tool_calls_side_effect"
        ),
        sa.CheckConstraint(
            "status IN ('pending_confirmation','running','succeeded','denied','expired','failed')",
            name="ck_tool_calls_status",
        ),
        sa.UniqueConstraint("run_id", "step_number", name="uq_tool_calls_run_step"),
    )
    op.create_index(
        "ix_agent_runs_conversation_created", "agent_runs", ["conversation_id", "created_at"]
    )
    op.create_index("ix_agent_runs_user_status", "agent_runs", ["user_id", "status"])
    op.create_index("ix_tool_calls_run_status", "tool_calls", ["run_id", "status"])


def downgrade() -> None:
    op.drop_index("ix_tool_calls_run_status", table_name="tool_calls")
    op.drop_index("ix_agent_runs_user_status", table_name="agent_runs")
    op.drop_index("ix_agent_runs_conversation_created", table_name="agent_runs")
    op.drop_table("tool_calls")
    op.drop_table("agent_runs")
