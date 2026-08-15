# Development

The backend targets Python 3.11 and the frontend targets Node 20.

## Compose startup

```bash
cp backend/.env.example backend/.env
docker compose up -d --build
docker compose ps
curl -fsS http://localhost:8000/health
curl -I http://localhost:3000
```

The backend container runs `alembic upgrade head` before Uvicorn starts. Check migration state with:

```bash
docker compose exec backend alembic current
```

Set `LLM_API_KEY` (or `OPENAI_API_KEY` for Compose), and optionally `LLM_BASE_URL` and `LLM_MODEL`, before sending chat messages. `AUDIT_RETENTION_DAYS` defaults to `90`.
M3 uses `AGENT_MAX_STEPS=6`, `AGENT_MAX_ACTIVE_SECONDS=20`, `TOOL_CONFIRMATION_TTL_SECONDS=300`,
and the server-owned `AGENT_TOOL_WHITELIST`. Waiting for confirmation does not consume active time.

## Gateway 出站配置

Chat、Agent planner 和 RAG Embedding 都通过 OpenAI-compatible 出站端点工作。默认是直连模式；
也可以通过 `LLM_*` / `EMBEDDING_*` 环境变量指向 AI-Gateway 的 `/v1` 入口。

### 直连模式（默认）

只配置 Chat，Embedding 自动回退到同一个 upstream：

```dotenv
LLM_API_KEY=sk-...
LLM_BASE_URL=
LLM_MODEL=gpt-4o-mini
# 留空时回退到 LLM_API_KEY / LLM_BASE_URL
EMBEDDING_API_KEY=
EMBEDDING_BASE_URL=
EMBEDDING_MODEL=text-embedding-3-small
EMBEDDING_DIM=1536
```

### Gateway 模式

Chat 与 Embedding 可以共用同一个 Gateway `/v1` 入口，但使用不同的 logical model。
Embedding 必须指向独立的 embedding provider（不能把 vLLM 聊天 Adapter 当作 embedding upstream）：

```dotenv
LLM_API_KEY=<gateway-service-key>
LLM_BASE_URL=http://ai-gateway:8080/v1
LLM_MODEL=chat/gpt-4o-mini            # Gateway 路由到 OpenAI chat

EMBEDDING_API_KEY=<gateway-service-key>
EMBEDDING_BASE_URL=http://ai-gateway:8080/v1
EMBEDDING_MODEL=embed/text-embedding-3-small   # Gateway 路由到独立 embedding provider
EMBEDDING_DIM=1536
```

注意事项：

- `EMBEDDING_API_KEY` / `EMBEDDING_BASE_URL` 留空时回退到 `LLM_API_KEY` / `LLM_BASE_URL`；
  两者都留空时 embedding 使用 OpenAI SDK 默认端点，且必须配置任意一个 key，否则抛出
  `EmbeddingConfigurationError`。
- Gateway 模式请使用 Gateway 的 service key，不要把用户 JWT token 直接当作 Gateway service key。
- `docker-compose.yml` 中 `EMBEDDING_API_KEY`/`EMBEDDING_BASE_URL` 使用嵌套插值回退到
  `OPENAI_API_KEY`/`LLM_BASE_URL`，与代码内 fallback 行为一致；为空时解析为空字符串而非 literal。
- 当前任务只提供配置切换；Chat/Embedding/Gateway 三服务实际部署由 `ai-inference-platform`
  总仓库负责。

## Observability（P3-01 / T3-01）

服务暴露 Prometheus text-format 指标，供集成监控（见总控仓库 `ai-inference-platform` 的
`deploy/prometheus/prometheus.integration.yml`）抓取。当前 WSL 环境没有 Docker/Grafana/Prometheus，
指标可通过单测与 `curl` 验证，真栈留待 Docker 环境。

### 抓取端点

- `GET /metrics`：无需鉴权，`text/plain; version=0.0.4`。
- `/metrics` 自身不计入 HTTP 指标，避免抓取自反馈噪声。

### 指标清单（独立 CollectorRegistry，前缀 `enterprise_ai_*`）

| 指标 | 类型 | 标签 | 说明 |
| --- | --- | --- | --- |
| `enterprise_ai_http_requests_total` | Counter | `method`, `route`, `status` | HTTP 请求计数 |
| `enterprise_ai_http_request_duration_seconds` | Histogram | `method`, `route` | HTTP 处理耗时 |
| `enterprise_ai_rag_search_duration_seconds` | Histogram | 无 | 完整 RAG 检索耗时（含失败） |
| `enterprise_ai_embedding_batch_size` | Histogram | 无 | 每个实际发送 batch 的文本数 |

### 标签约束

- `route` 只使用低基数路由模板（如 `/api/v1/knowledge-bases/{kb_id}`），取自
  `request.scope["route"].path`；禁止使用带 UUID 的原始 URL path。
- 未匹配路由（框架 404、CORS 短路）统一为 `__unmatched__`。
- 中间件异常路径以尽力而为的 `status="500"` 记录后重新抛出，绝不吞异常。
- Embedding 每个实际发送的 batch observe 一次 batch size；空输入不 observe。
- `search_chunks` 用 `try/finally` 记录完整检索耗时，失败同样记录。

本地验证：

```bash
curl -s localhost:8000/metrics | grep enterprise_ai
pytest tests/test_metrics.py -q
```

## Local checks

```bash
cd backend
pytest
cd ../frontend
npm ci
npm run dev
```

The local backend uses the configured `DATABASE_URL`; the test suite replaces it with an in-memory SQLite database. Frontend development runs on Vite and proxies API requests according to `vite.config.ts`.

## Troubleshooting

```bash
docker compose logs backend
docker compose logs postgres
docker compose ps
cd backend && alembic current
```

If chat returns `503`, configure `LLM_API_KEY` and restart the backend. If migrations fail, verify PostgreSQL is healthy with `docker compose ps` and inspect the backend logs.

## M2 Knowledge Workflow

Run the worker locally from the backend directory after starting PostgreSQL and
Redis:

```bash
cd backend
celery -A app.worker.celery_app worker --loglevel=INFO --concurrency=2
```

The worker reads the same `DATABASE_URL`, `REDIS_URL`, `LLM_API_KEY`,
`LLM_BASE_URL`, `EMBEDDING_API_KEY`, `EMBEDDING_BASE_URL`, `EMBEDDING_MODEL`,
`EMBEDDING_DIM`, and `UPLOAD_DIR` settings
as the API. The supported upload formats are PDF (`.pdf`), Word (`.docx`),
Excel (`.xlsx`), and Markdown (`.md`).

Upload is durable before the Celery task is dispatched. Document processing
follows `pending -> processing -> ready` or `failed`; failures retain a
redacted error message and are retried up to three times by Celery. Poll the
document status endpoint while it is pending or processing.

Source files are stored under `UPLOAD_DIR/<knowledge-base-uuid>/` using UUID
filenames and `local://` URIs. Knowledge-base deletion removes the source
directory. If a task or container is interrupted, inspect failed documents and
remove only orphaned UUID directories under `UPLOAD_DIR`; do not delete the
shared upload volume while the API or worker is running.

Run the PostgreSQL/pgvector integration test with:

```bash
TEST_POSTGRES_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/enterprise_ai \
  pytest -m postgres tests/test_pgvector_integration.py -q
```

The retrieval evaluation CLI consumes JSONL rows with `question`,
`knowledge_base_id`, `expected_chunk_ids`, and optional `top_k`. Replace the
sample UUIDs in `evaluation/m2_sample.jsonl` with IDs from an ingested test
knowledge base, then run:

```bash
python scripts/evaluate_retrieval.py \
  --dataset evaluation/m2_sample.jsonl --top-k 5 \
  --output evaluation/results.json
```

## M3 Tool Workflow

Tools are registered with `ToolDefinition` in `backend/app/tools` and composed by
`build_default_registry()`. Each definition supplies a JSON Schema, `side_effect` (`read` or
`write`), an async handler, and an impact formatter. Add a tool to the server configuration and
registry together; clients cannot add tools through the API.

Run the key-free M3 tests locally:

```bash
cd backend
pytest tests/test_m3_flow.py tests/test_agent_loop.py tests/test_agent_api.py -q
ruff check app tests
alembic check
```

Manual smoke test: create or select an accessible knowledge base and ask the chat client to
check its expense policy, then submit `300 CNY` for supplies with receipt `R-100`. Activity should
show `knowledge_search` succeeded and `submit_expense` pending. Deny once to verify no expense ID,
then repeat and confirm to receive an `EXP-` result. Audit rows can be inspected with:

```sql
SELECT action_type, tool_used, created_at FROM audit_logs
WHERE action_type LIKE 'tool_call_%' ORDER BY created_at;
```

Use `--min-recall` and `--min-citation-coverage` to make CI fail below agreed
quality thresholds. For worker troubleshooting, check `docker compose ps`,
`docker compose logs worker --tail=50`, Redis health, and that the worker and
backend mount the same `uploads` volume. A `503` upload response means the
broker dispatch failed; a `failed` document with a provider error means the
worker exhausted its retries.
