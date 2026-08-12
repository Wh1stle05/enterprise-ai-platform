from sqlalchemy import inspect

from app.models import KnowledgeBaseACL


def test_acl_has_ranked_access_contract():
    assert {c.key for c in inspect(KnowledgeBaseACL).columns} == {
        "knowledge_base_id",
        "subject_id",
        "access_level",
        "created_at",
    }
