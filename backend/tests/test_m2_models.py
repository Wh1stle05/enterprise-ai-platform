from sqlalchemy import inspect

from app.models import Document, KnowledgeBaseACL


def test_m2_model_contract():
    acl = inspect(KnowledgeBaseACL)
    assert {column.key for column in acl.columns} == {
        "knowledge_base_id",
        "subject_id",
        "access_level",
        "created_at",
    }
    document_columns = {column.key for column in inspect(Document).columns}
    assert {
        "storage_uri",
        "checksum",
        "parser_version",
        "embedding_model",
        "embedding_dim",
        "error_message",
        "processed_at",
    } <= document_columns
