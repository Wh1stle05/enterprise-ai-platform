"""Prometheus metrics for the Enterprise AI Platform (P3-01 / T3-01).

All platform metrics live on an independent :class:`CollectorRegistry` so the
default registry stays free of third-party noise. HTTP labels are strictly
low-cardinality: ``method``, the matched **route template** and ``status``
only — never raw URLs and never dynamic UUIDs. Unmatched routes are reported
as ``__unmatched__``.
"""

from prometheus_client import CollectorRegistry, Counter, Histogram

REGISTRY = CollectorRegistry()

HTTP_REQUESTS_TOTAL = Counter(
    "enterprise_ai_http_requests_total",
    "Total HTTP requests handled by the enterprise API",
    labelnames=("method", "route", "status"),
    registry=REGISTRY,
)

HTTP_REQUEST_DURATION_SECONDS = Histogram(
    "enterprise_ai_http_request_duration_seconds",
    "HTTP request handling duration in seconds",
    labelnames=("method", "route"),
    registry=REGISTRY,
)

RAG_SEARCH_DURATION_SECONDS = Histogram(
    "enterprise_ai_rag_search_duration_seconds",
    "Duration of a full RAG search (query embedding + vector scan)",
    registry=REGISTRY,
)

EMBEDDING_BATCH_SIZE = Histogram(
    "enterprise_ai_embedding_batch_size",
    "Number of texts in each embedding batch actually sent to the provider",
    buckets=(1, 2, 4, 8, 16, 32, 64, 128, 256, 512),
    registry=REGISTRY,
)

UNMATCHED_ROUTE = "__unmatched__"
METRICS_PATH = "/metrics"


def http_route_label(request) -> str:
    """Return the low-cardinality route template for a request.

    The router stores the matched :class:`fastapi.routing.APIRoute` in
    ``request.scope["route"]`` while dispatching; the template lives on its
    ``.path`` attribute (e.g. ``/api/v1/knowledge-bases/{kb_id}``). Unmatched
    requests (framework 404s, CORS short-circuits) never get one and are
    reported as ``__unmatched__``.

    Never fall back to ``request.url.path`` here: raw paths embed dynamic
    UUIDs and would explode the label cardinality.
    """
    route = request.scope.get("route")
    if route is not None:
        template = getattr(route, "path", None)
        if template:
            return template
    return UNMATCHED_ROUTE


def record_http_request(method: str, route: str, status: int | str, duration: float) -> None:
    """Record one HTTP request against the low-cardinality labels."""
    HTTP_REQUESTS_TOTAL.labels(method=method, route=route, status=str(status)).inc()
    HTTP_REQUEST_DURATION_SECONDS.labels(method=method, route=route).observe(duration)
