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
| Frontend | React (WIP) |
| Deployment | Docker Compose, Kubernetes (V4+) |

## Quick Start

```bash
# 1. Start infrastructure
docker compose up -d postgres redis

# 2. Set your LLM API key
cp .env.example .env
# Edit .env → set OPENAI_API_KEY

# 3. Start backend
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload

# 4. Open docs
open http://localhost:8000/docs
```

Or with Docker Compose (all-in-one):

```bash
docker compose up -d
```

## Roadmap

| Phase | Features | Status |
|-------|----------|--------|
| **V1** | Auth + Chat + History | ✅ Done |
| **V2** | Knowledge Base + PDF Upload + RAG | 🚧 WIP |
| **V3** | Agent + Tool Calling + Docker Compose | 📝 Planned |
| **V4** | Kubernetes + Model Inference + Auto-scaling | 📝 Planned |
| **V5** | Workflow + Approval | 📝 Planned |

## Project Structure

```
enterprise-ai-platform/
├── backend/          # FastAPI application
│   ├── app/
│   │   ├── core/     # Config, DB, security
│   │   ├── models/   # SQLAlchemy ORM models
│   │   ├── api/      # Route handlers
│   │   ├── services/  # Business logic
│   │   └── schemas/   # Pydantic models
│   ├── alembic/      # DB migrations
│   └── tests/
├── frontend/         # React application (WIP)
├── k8s/              # Kubernetes manifests (V4+)
├── docs/             # Architecture & API docs
└── scripts/          # Bootstrap & utility scripts
```

## License

MIT
