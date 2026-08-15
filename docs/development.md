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

