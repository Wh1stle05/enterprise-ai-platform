import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.mark.asyncio
async def test_health():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "version": "0.1.0"}


@pytest.mark.asyncio
async def test_health_does_not_depend_on_external_services(monkeypatch):
    # /health 是纯 liveness：即使 DB/Redis checker 全部失败也不影响它。
    async def _fail():
        raise ConnectionError("down")

    monkeypatch.setattr("app.main.check_database", _fail)
    monkeypatch.setattr("app.main.check_redis", _fail)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "version": "0.1.0"}


@pytest.mark.asyncio
async def test_ready_reports_all_checks_ok(monkeypatch):
    async def _ok():
        return None

    monkeypatch.setattr("app.main.check_database", _ok)
    monkeypatch.setattr("app.main.check_redis", _ok)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/ready")
    assert response.status_code == 200
    assert response.json() == {
        "status": "ready",
        "checks": {"database": "ok", "redis": "ok"},
    }


@pytest.mark.asyncio
async def test_ready_returns_503_when_database_down(monkeypatch):
    async def _fail():
        raise ConnectionError("db down")

    async def _ok():
        return None

    monkeypatch.setattr("app.main.check_database", _fail)
    monkeypatch.setattr("app.main.check_redis", _ok)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/ready")
    assert response.status_code == 503
    assert response.json() == {
        "status": "not_ready",
        "checks": {"database": "error", "redis": "ok"},
    }


@pytest.mark.asyncio
async def test_ready_returns_503_when_redis_down(monkeypatch):
    async def _ok():
        return None

    async def _fail():
        raise ConnectionError("redis down")

    monkeypatch.setattr("app.main.check_database", _ok)
    monkeypatch.setattr("app.main.check_redis", _fail)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/ready")
    assert response.status_code == 503
    assert response.json() == {
        "status": "not_ready",
        "checks": {"database": "ok", "redis": "error"},
    }


@pytest.mark.asyncio
async def test_ready_returns_503_when_both_down(monkeypatch):
    async def _fail():
        raise ConnectionError("all down")

    monkeypatch.setattr("app.main.check_database", _fail)
    monkeypatch.setattr("app.main.check_redis", _fail)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/ready")
    assert response.status_code == 503
    assert response.json() == {
        "status": "not_ready",
        "checks": {"database": "error", "redis": "error"},
    }


@pytest.mark.asyncio
async def test_ready_never_raises_500(monkeypatch):
    # 依赖失败时 /ready 必须返回 503（结构化），绝不能抛 500。
    async def _fail():
        raise RuntimeError("boom")

    monkeypatch.setattr("app.main.check_database", _fail)
    monkeypatch.setattr("app.main.check_redis", _fail)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/ready")
    assert response.status_code == 503
    assert response.json()["checks"] == {"database": "error", "redis": "error"}


@pytest.mark.asyncio
async def test_ready_response_carries_request_id(monkeypatch):
    async def _ok():
        return None

    monkeypatch.setattr("app.main.check_database", _ok)
    monkeypatch.setattr("app.main.check_redis", _ok)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/ready", headers={"X-Request-ID": "ready-1"})
    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == "ready-1"
