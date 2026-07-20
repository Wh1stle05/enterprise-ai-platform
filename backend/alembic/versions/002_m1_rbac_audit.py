"""M1 roles and audit logs."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("role", sa.String(16), nullable=False, server_default="user"))
    op.create_index("ix_users_role", "users", ["role"])
    op.create_table(
        "audit_logs",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("user_id", sa.UUID(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("action_type", sa.String(32), nullable=False),
        sa.Column("input", sa.Text()),
        sa.Column("output", sa.Text()),
        sa.Column("tool_used", sa.String(128)),
        sa.Column("ip_address", sa.String(64)),
        sa.Column("retention_days", sa.Integer(), nullable=False, server_default="90"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_audit_logs_created_at", "audit_logs", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_audit_logs_created_at", table_name="audit_logs")
    op.drop_table("audit_logs")
    op.drop_index("ix_users_role", table_name="users")
    op.drop_column("users", "role")
