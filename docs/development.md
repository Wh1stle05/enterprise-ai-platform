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
`LLM_BASE_URL`, `EMBEDDING_MODEL`, `EMBEDDING_DIM`, and `UPLOAD_DIR` settings
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
