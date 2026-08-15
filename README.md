# Enterprise AI Platform

> 企业级 AI Agent 平台 — 支持知识库管理、RAG 检索、Agent Tool Calling、工作流编排。  
> 从零搭建，面向校招面试的工程实践项目。

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                    Frontend (React)                  │
│          Chat UI · Knowledge Base Manager           │
└──────────────────────┬──────────────────────────────┘
                       │ HTTP (REST)
┌──────────────────────▼──────────────────────────────┐
│                 Backend API (FastAPI)                │
│   Auth · Chat · Knowledge Base · Agent · Workflow   │
└────┬──────────┬──────────┬──────────┬────────────────┘
     │          │          │          │
┌────▼───┐ ┌───▼────┐ ┌───▼────┐ ┌──▼──────────────┐
│Postgre │ │ pgvec  │ │ Redis  │ │  LLM API        │
│ SQL    │ │ tor    │ │ Cache  │ │  OpenAI/Qwen/DS  │
└────────┘ └────────┘ └────────┘ └─────────────────┘
```

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.11+, FastAPI, SQLAlchemy (async) |
| Database | PostgreSQL 17 + pgvector |
| Cache | Redis 7 |
| Auth | JWT (python-jose + bcrypt) |
| LLM | OpenAI / DeepSeek / Qwen API |
| Frontend | Vite + React 18 + TypeScript + Tailwind CSS |
| Deployment | Docker Compose, Kubernetes (V4+) |

## Quick Start

### Backend

```bash
# 1. Start infrastructure
docker compose up -d postgres redis

# 2. Set your LLM API key
cp backend/.env.example backend/.env
# Edit backend/.env → set OPENAI_API_KEY

# 3. Start backend
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload

# 4. Open API docs
open http://localhost:8000/docs
```

### Frontend

```bash
# In a separate terminal
cd frontend
npm install
npm run dev
# Open http://localhost:5173
```

> Vite dev server proxies `/api/*` to `http://localhost:8000`.

### All-in-one (Docker Compose)

```bash
docker compose up -d
```

## Roadmap

| Phase | Features | Status |
|-------|----------|--------|
| **V1** | Auth + Chat + History | ✅ Done |
| **V2** | Knowledge Base + PDF/Word/Excel/Markdown Upload + ACL RAG | ✅ Done |
| **V3** | Agent + Tool Calling + Docker Compose | ✅ Done |
| **V4** | Kubernetes + Model Inference + Auto-scaling | 📝 Planned |
| **V5** | Workflow + Approval | 📝 Planned |

## Project Structure

```
enterprise-ai-platform/
├── backend/              # FastAPI application
│   ├── app/
│   │   ├── core/         # Config, DB, security
│   │   ├── models/       # SQLAlchemy ORM models
│   │   ├── api/v1/       # Route handlers
│   │   ├── services/     # Business logic
│   │   └── schemas/      # Pydantic models
│   ├── alembic/          # DB migrations
│   └── tests/
├── frontend/             # React + Vite application
│   ├── src/
│   │   ├── api/          # HTTP client + endpoint modules
│   │   ├── components/   # Reusable UI components
│   │   ├── context/      # React context providers
│   │   ├── hooks/        # Custom hooks
│   │   ├── pages/        # Route pages
│   │   └── types/        # TypeScript type definitions
│   └── index.html
├── .github/workflows/    # CI/CD pipelines
├── k8s/                  # Kubernetes manifests (V4+)
├── docs/                 # Architecture & API docs
└── scripts/              # Bootstrap & utility scripts
```

## License

MIT
