"""Prometheus metrics tests for the enterprise API (P3-01 / T3-01).

The metric registry is process-global and shared across the whole test suite,
so assertions use deltas captured before/after the action instead of absolute
values.
"""

import re
from types import SimpleNamespace
from uuid import uuid4

import pytest
from httpx import AsyncClient
from prometheus_client import generate_latest

from app.core.config import settings
from app.services import retrieval_service
from app.services.embedding_service import embed_texts
from app.services.metrics import REGISTRY

REGISTER_URL = "/api/v1/auth/register"
KNOWLEDGE_BASES_URL = "/api/v1/knowledge-bases"
KB_TEMPLATE = "/api/v1/knowledge-bases/{kb_id}"
UNMATCHED_ROUTE = "__unmatched__"

_COUNTER_LINE = re.compile(
    r'^enterprise_ai_http_requests_total\{method="([^"]*)",route="([^"]*)",status="([^"]*)"\} '
    r"(\S+)$",
    re.MULTILINE,
)


def _scrape() -> str:
    return generate_latest(REGISTRY).decode("utf-8")


def _counter_value(text: str, method: str, route: str, status: str) -> float:
    for match in _COUNTER_LINE.finditer(text):
        if (match.group(1), match.group(2), match.group(3)) == (method, route, status):
            return float(match.group(4))
    return 0.0


def _total_http_counter(text: str) -> float:
    return sum(float(match.group(4)) for match in _COUNTER_LINE.finditer(text))


def _histogram_stats(name: str) -> tuple[int, float]:
    for metric in REGISTRY.collect():
        if metric.name == name:
            samples = {sample.name: sample.value for sample in metric.samples}
            return int(samples[f"{name}_count"]), float(samples[f"{name}_sum"])
    return 0, 0.0


async def _register(client: AsyncClient, username: str) -> dict:
    resp = await client.post(
        REGISTER_URL,
        json={
            "username": username,
            "email": f"{username}@example.com",
            "password": "secret123",
        },
    )
    assert resp.status_code == 201
    return resp.json()


class TestMetricsEndpoint:
    async def test_metrics_endpoint_exposes_all_four_families(self, client: AsyncClient):
        resp = await client.get("/metrics")
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/plain")
        body = resp.text
        for name in (
            "enterprise_ai_http_requests_total",
            "enterprise_ai_http_request_duration_seconds",
            "enterprise_ai_rag_search_duration_seconds",
            "enterprise_ai_embedding_batch_size",
        ):
            assert f"# HELP {name}" in body
            assert f"# TYPE {name}" in body

    async def test_metrics_does_not_require_auth(self, client: AsyncClient):
        resp = await client.get("/metrics")
        assert resp.status_code == 200


class TestHttpRouteLabels:
    async def test_middleware_exception_path_records_500_and_re_raises(self):
        from starlette.requests import Request

        from app.main import metrics_middleware

        async def _inner_call_next(request):
            raise RuntimeError("inner middleware boom")

        scope = {
            "type": "http",
            "asgi": {"version": "3.0"},
            "http_version": "1.1",
            "method": "GET",
            "scheme": "http",
            "path": "/boom",
            "raw_path": b"/boom",
            "query_string": b"",
            "headers": [],
            "client": ("127.0.0.1", 12345),
            "server": ("test", 80),
            "state": {},
        }
        before = _counter_value(_scrape(), "GET", UNMATCHED_ROUTE, "500")

        with pytest.raises(RuntimeError):
            await metrics_middleware(Request(scope), _inner_call_next)

        after = _counter_value(_scrape(), "GET", UNMATCHED_ROUTE, "500")
        assert after == before + 1

    async def test_uuid_route_appears_only_as_template(self, client: AsyncClient):
        token = (await _register(client, "metrics-uuid"))["access_token"]
        kb_id = str(uuid4())
        resp = await client.get(
            f"{KNOWLEDGE_BASES_URL}/{kb_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 404

        body = _scrape()
        assert _counter_value(body, "GET", KB_TEMPLATE, "404") >= 1
        # The real UUID must never leak into any metric label.
        assert kb_id not in body

    async def test_unmatched_route_uses_unmatched_label(self, client: AsyncClient):
        resp = await client.get("/this-route-does-not-exist")
        assert resp.status_code == 404

        body = _scrape()
        assert _counter_value(body, "GET", UNMATCHED_ROUTE, "404") >= 1

    async def test_health_uses_its_route_template(self, client: AsyncClient):
        resp = await client.get("/health")
        assert resp.status_code == 200

        body = _scrape()
        assert _counter_value(body, "GET", "/health", "200") >= 1

    async def test_metrics_scrape_never_counts_itself(self, client: AsyncClient):
        before = _total_http_counter(_scrape())
        resp = await client.get("/metrics")
        assert resp.status_code == 200
        after = _total_http_counter(_scrape())
        assert after == before
        # And no counter line may ever carry the /metrics route.
        assert _counter_value(_scrape(), "GET", "/metrics", "200") == 0


class TestEmbeddingBatchSize:
    def _make_fake_client(self, calls: list) -> SimpleNamespace:
        class FakeEmbeddings:
            def __init__(self):
                self.calls = calls

            async def create(self, **kwargs):
                self.calls.append(kwargs)
                value = 0.1
                return SimpleNamespace(
                    data=[
                        SimpleNamespace(index=i, embedding=[value] * settings.EMBEDDING_DIM)
                        for i in range(len(kwargs["input"]))
                    ]
                )

        return SimpleNamespace(embeddings=FakeEmbeddings())

    @pytest.mark.asyncio
    async def test_observed_once_per_sent_batch(self):
        calls: list = []
        client = self._make_fake_client(calls)
        count_before, sum_before = _histogram_stats("enterprise_ai_embedding_batch_size")

        await embed_texts(["a", "b", "c"], client=client, batch_size=2)

        count_after, sum_after = _histogram_stats("enterprise_ai_embedding_batch_size")
        assert len(calls) == 2
        assert count_after == count_before + 2
        assert sum_after == sum_before + 3  # batch sizes 2 and 1

    @pytest.mark.asyncio
    async def test_empty_input_never_observes(self):
        client = self._make_fake_client([])
        count_before, sum_before = _histogram_stats("enterprise_ai_embedding_batch_size")

        assert await embed_texts([], client=client) == []

        count_after, sum_after = _histogram_stats("enterprise_ai_embedding_batch_size")
        assert count_after == count_before
        assert sum_after == sum_before


class TestRagSearchDuration:
    class _FakeResult:
        def all(self):
            return []

    class _FakeDB:
        def __init__(self):
            self.executed = []

        async def execute(self, stmt):
            self.executed.append(stmt)
            return TestRagSearchDuration._FakeResult()

    @pytest.mark.asyncio
    async def test_success_path_records_duration(self, monkeypatch):
        async def _noop_access(*args, **kwargs):
            return "viewer"

        async def _fake_embedder(texts):
            return [[0.1] * settings.EMBEDDING_DIM]

        monkeypatch.setattr(retrieval_service, "require_kb_access", _noop_access)
        count_before, sum_before = _histogram_stats("enterprise_ai_rag_search_duration_seconds")

        hits = await retrieval_service.search_chunks(
            self._FakeDB(),
            uuid4(),
            uuid4(),
            "query",
            top_k=5,
            embedder=_fake_embedder,
        )

        count_after, sum_after = _histogram_stats("enterprise_ai_rag_search_duration_seconds")
        assert hits == []
        assert count_after == count_before + 1
        assert sum_after > sum_before

    @pytest.mark.asyncio
    async def test_failure_path_still_records_duration(self, monkeypatch):
        async def _noop_access(*args, **kwargs):
            return "viewer"

        async def _broken_embedder(texts):
            raise RuntimeError("provider down")

        monkeypatch.setattr(retrieval_service, "require_kb_access", _noop_access)
        count_before, _ = _histogram_stats("enterprise_ai_rag_search_duration_seconds")

        with pytest.raises(RuntimeError):
            await retrieval_service.search_chunks(
                self._FakeDB(),
                uuid4(),
                uuid4(),
                "query",
                top_k=5,
                embedder=_broken_embedder,
            )

        count_after, _ = _histogram_stats("enterprise_ai_rag_search_duration_seconds")
        assert count_after == count_before + 1
