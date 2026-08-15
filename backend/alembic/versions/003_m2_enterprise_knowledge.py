"""M2 enterprise knowledge schema and provenance."""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.create_table(
        "knowledge_base_acl",
        sa.Column(
            "knowledge_base_id",
            sa.UUID(),
            sa.ForeignKey("knowledge_bases.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "subject_id", sa.UUID(), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
        ),
        sa.Column("access_level", sa.String(16), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "access_level IN ('owner','editor','viewer')", name="ck_kb_acl_access_level"
        ),
    )
    op.execute(
        "INSERT INTO knowledge_base_acl (knowledge_base_id, subject_id, access_level) "
        "SELECT id, user_id, 'owner' FROM knowledge_bases ON CONFLICT DO NOTHING"
    )
    for name, column in (
        (
            "storage_uri",
            sa.Column("storage_uri", sa.String(1024), nullable=False, server_default=""),
        ),
        ("checksum", sa.Column("checksum", sa.String(64), nullable=False, server_default="")),
        (
            "parser_version",
            sa.Column("parser_version", sa.String(64), nullable=False, server_default=""),
        ),
        (
            "embedding_model",
            sa.Column("embedding_model", sa.String(128), nullable=False, server_default=""),
        ),
        (
            "embedding_dim",
            sa.Column("embedding_dim", sa.Integer(), nullable=False, server_default="1536"),
        ),
        ("error_message", sa.Column("error_message", sa.Text())),
        ("processed_at", sa.Column("processed_at", sa.DateTime(timezone=True))),
    ):
        op.add_column("documents", column)
    op.add_column(
        "document_chunks",
        sa.Column("source_locator", sa.String(256), nullable=False, server_default=""),
    )
    op.create_check_constraint(
        "ck_documents_status", "documents", "status IN ('pending','processing','ready','failed')"
    )
    op.create_unique_constraint(
        "uq_documents_kb_checksum", "documents", ["knowledge_base_id", "checksum"]
    )
    op.create_unique_constraint(
        "uq_document_chunks_index", "document_chunks", ["document_id", "chunk_index"]
    )
    op.create_index("ix_documents_kb_status", "documents", ["knowledge_base_id", "status"])
    op.execute(
        "CREATE INDEX ix_document_chunks_embedding_hnsw ON document_chunks "
        "USING hnsw (embedding vector_cosine_ops)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_document_chunks_embedding_hnsw")
    op.drop_index("ix_documents_kb_status", table_name="documents")
    op.drop_constraint("uq_document_chunks_index", "document_chunks", type_="unique")
    op.drop_constraint("uq_documents_kb_checksum", "documents", type_="unique")
    op.drop_constraint("ck_documents_status", "documents", type_="check")
    op.drop_column("document_chunks", "source_locator")
    for name in (
        "processed_at", "error_message", "embedding_dim", "embedding_model",
        "parser_version", "checksum", "storage_uri",
    ):
        op.drop_column("documents", name)
    op.drop_table("knowledge_base_acl")
