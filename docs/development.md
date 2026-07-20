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
