def test_rag_api_contract_is_exposed():
    from app.main import app

    paths = {route.path for route in app.routes}
    assert "/api/v1/knowledge-bases/{kb_id}/ask" in paths
