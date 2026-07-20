# Enterprise AI Platform — API Reference

Base URL: `/api/v1`

## Curl quick start

```bash
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H 'Content-Type: application/json' \
  -d '{"username":"alice","email":"alice@example.com","password":"secret123"}'

curl -X POST http://localhost:8000/api/v1/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"username":"alice","password":"secret123"}'

TOKEN='paste-access-token'
curl http://localhost:8000/api/v1/auth/me -H "Authorization: Bearer $TOKEN"
curl http://localhost:8000/api/v1/chat/conversations -H "Authorization: Bearer $TOKEN"
curl -X POST http://localhost:8000/api/v1/chat/conversations \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' -d '{}'
curl -X POST http://localhost:8000/api/v1/chat/conversations/CONVERSATION_ID/messages \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' -d '{"content":"Hello"}'
curl http://localhost:8000/api/v1/chat/conversations/CONVERSATION_ID/messages \
  -H "Authorization: Bearer $TOKEN"
curl -X DELETE http://localhost:8000/api/v1/chat/conversations/CONVERSATION_ID \
  -H "Authorization: Bearer $TOKEN"
```

---

## Health

### `GET /health`

Health check endpoint (available at root, no auth required).

**Response** `200 OK`
```json
{
  "status": "ok",
  "version": "0.1.0"
}
```

---

## Auth

All auth endpoints accept `Content-Type: application/json`.

### `POST /auth/register`

Create a new user account.

**Request Body**
```json
{
  "username": "string (3-64 chars, required)",
  "email": "string (valid email, required)",
  "password": "string (6-128 chars, required)"
}
```

**Response** `201 Created`
```json
{
  "access_token": "string (JWT)",
  "token_type": "bearer",
  "user": {
    "id": "uuid",
    "username": "string",
    "email": "string",
    "display_name": "string | null",
    "is_superuser": false,
    "created_at": "datetime (ISO 8601)"
  }
}
```

**Error** `409 Conflict` — Username or email already exists.

### `POST /auth/login`

Authenticate with username and password.

**Request Body**
```json
{
  "username": "string (required)",
  "password": "string (required)"
}
```

**Response** `200 OK`
```json
{
  "access_token": "string (JWT)",
  "token_type": "bearer",
  "user": { "...same as register..." }
}
```

**Error** `401 Unauthorized` — Invalid credentials.

### `GET /auth/me`

Get the currently authenticated user's profile.

**Headers**
```
Authorization: Bearer <token>
```

**Response** `200 OK`
```json
{
  "id": "uuid",
  "username": "string",
  "email": "string",
  "role": "user | admin | viewer",
  "display_name": "string | null",
  "is_superuser": false,
  "created_at": "datetime (ISO 8601)"
}
```

**Errors**:
- `401 Unauthorized` — Invalid or expired token.
- `404 Not Found` — User not found.

---

## Chat

All chat endpoints require `Authorization: Bearer <token>` header.

### `GET /chat/conversations`

List conversations for the current user, newest first.

**Query Parameters**
| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `limit` | int | 50 | Max items to return |
| `offset` | int | 0 | Number of items to skip |

**Response** `200 OK`
```json
[
  {
    "id": "uuid",
    "title": "string",
    "message_count": 0,
    "created_at": "datetime (ISO 8601)"
  }
]
```

### `POST /chat/conversations`

Create a new conversation.

**Request Body**
```json
{
  "title": "string (max 256 chars, default: 'New Conversation')"
}
```

**Response** `201 Created`
```json
{
  "id": "uuid",
  "title": "string",
  "created_at": "datetime (ISO 8601)"
}
```

### `GET /chat/conversations/{conversation_id}/messages`

Get all messages in a conversation (only messages belonging to the current user).

**Path Parameters**
| Param | Type | Description |
|-------|------|-------------|
| `conversation_id` | uuid | ID of the conversation |

**Response** `200 OK**
```json
[
  {
    "id": "uuid",
    "role": "user | assistant | system",
    "content": "string",
    "created_at": "datetime (ISO 8601)"
  }
]
```

Returns empty array `[]` if the conversation doesn't exist or has no messages.

### `DELETE /chat/conversations/{conversation_id}`

Delete an owned conversation. Users with the `viewer` role receive `403`; a conversation owned by another user returns `404`.

**Response** `204 No Content`

### `POST /chat/conversations/{conversation_id}/messages`

Send one user turn and receive the persisted user and assistant messages. The last 20 messages are supplied to the configured OpenAI-compatible model.

**Request Body**
```json
{"content": "Hello"}
```

**Response** `201 Created`
```json
{
  "messages": [
    {"id": "uuid", "role": "user", "content": "Hello", "created_at": "datetime"},
    {"id": "uuid", "role": "assistant", "content": "Hi", "created_at": "datetime"}
  ]
}
```

`503` means `LLM_API_KEY` is not configured. `502` means the provider request failed.

## Roles, audit, and discovery

JWTs authenticate users, but authorization reads the current `role` from the database. Missing or invalid credentials return `401`. A valid `viewer` credential may read profile, conversation, and message history, but write operations return `403`. `admin` and `user` may create, send, and delete their own conversations.

Audit records are redacted recursively for keys matching `password`, `secret`, `token`, `api_key`, and `Authorization`. Set `AUDIT_RETENTION_DAYS` (default `90`) to control retention; expired records are purged during application startup. Audit persistence is fail-open and never includes bearer tokens.

Interactive documentation is available at `GET /docs`; the machine-readable contract is at `GET /openapi.json`.

---

## Knowledge Bases (M2)

All knowledge-base endpoints require `Authorization: Bearer <token>`. Resource
authorization is ACL-based: `viewer` can read/search/ask, `editor` can upload,
and only `owner` can change ACLs or delete a knowledge base. Inaccessible IDs
return `404`.

### Knowledge-base CRUD

```bash
curl -X POST http://localhost:8000/api/v1/knowledge-bases \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"name":"HR Policies","description":"Company policy documents"}'

curl http://localhost:8000/api/v1/knowledge-bases \
  -H "Authorization: Bearer $TOKEN"

curl http://localhost:8000/api/v1/knowledge-bases/$KB_ID \
  -H "Authorization: Bearer $TOKEN"

curl -X DELETE http://localhost:8000/api/v1/knowledge-bases/$KB_ID \
  -H "Authorization: Bearer $TOKEN"
```

`POST` returns `201` and creates an owner ACL entry. `GET` returns
`id`, `name`, `description`, `access_level`, `document_count`, `created_at`,
and `updated_at`. `DELETE` returns `204` and removes source files and metadata.

### ACL

```bash
curl http://localhost:8000/api/v1/knowledge-bases/$KB_ID/acl \
  -H "Authorization: Bearer $TOKEN"

curl -X PUT http://localhost:8000/api/v1/knowledge-bases/$KB_ID/acl/$USER_ID \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"access_level":"viewer"}'

curl -X DELETE http://localhost:8000/api/v1/knowledge-bases/$KB_ID/acl/$USER_ID \
  -H "Authorization: Bearer $TOKEN"
```

ACL levels are `owner`, `editor`, and `viewer`. Listing and mutation return
entries containing `subject_id`, `username`, `access_level`, and `created_at`.
Only an owner can mutate ACLs; an owner cannot remove or downgrade their own
owner entry. ACL mutation returns `200`; deletion returns `204`.

### Upload and document status

Supported formats are `.pdf`, `.docx`, `.xlsx`, and `.md`.

```bash
curl -X POST http://localhost:8000/api/v1/knowledge-bases/$KB_ID/documents \
  -H "Authorization: Bearer $TOKEN" \
  -F 'file=@backend/tests/fixtures/sample.md;type=text/markdown'

curl http://localhost:8000/api/v1/knowledge-bases/$KB_ID/documents/$DOCUMENT_ID \
  -H "Authorization: Bearer $TOKEN"
```

Upload returns `202` with `status: "pending"`, checksum, storage URI,
parser/embedding provenance, and timestamps. The worker transitions the
document through `pending -> processing -> ready` or `failed`.

```json
{
  "id":"uuid", "knowledge_base_id":"uuid", "filename":"sample.md",
  "file_type":"text/markdown", "file_size":123, "storage_uri":"local://...",
  "checksum":"sha256", "parser_version":"m2-1",
  "embedding_model":"text-embedding-3-small", "embedding_dim":1536,
  "status":"ready", "chunk_count":2, "error_message":null,
  "created_at":"datetime", "processed_at":"datetime"
}
```

### Search

```bash
curl -X POST http://localhost:8000/api/v1/knowledge-bases/$KB_ID/search \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"query":"How much annual leave?","top_k":5}'
```

Search returns ready-document hits with `chunk_id`, `document_id`, `filename`,
`chunk_index`, `content`, `source_locator`, and cosine `score`.

### Ask with citations

```bash
curl -X POST http://localhost:8000/api/v1/knowledge-bases/$KB_ID/ask \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"question":"How much annual leave?","top_k":5}'
```

**Response** `200 OK`
```json
{
  "answer":"Employees receive five days of annual leave [S1].",
  "no_evidence":false,
  "citations":[{
    "label":"[S1]", "chunk_id":"uuid", "document_id":"uuid",
    "filename":"sample.md", "source_locator":"document",
    "chunk_index":0, "score":0.95
  }]
}
```

When no retrieved evidence meets `RETRIEVAL_MIN_SCORE`, the response is
`no_evidence: true`, `citations: []`, and the exact answer:
`No sufficient evidence found. Please add relevant documents or contact an administrator.`

---

## Error Format

All errors return a JSON body:

```json
{
  "detail": "string — description of the error"
}
```

| Status | Meaning |
|--------|---------|
| 401 | Unauthorized — invalid or missing token |
| 403 | Forbidden — global role or ACL level is insufficient |
| 404 | Resource not found, including an inaccessible knowledge base/document |
| 409 | Conflict — duplicate document checksum or invalid owner ACL change |
| 413 | Upload exceeds `MAX_UPLOAD_SIZE_MB` |
| 415 | Upload extension is not `.pdf`, `.docx`, `.xlsx`, or `.md` |
| 422 | Validation error — malformed UUID, request body, or empty upload |
| 502 | LLM/provider failure or invalid citation contract |
| 503 | LLM/embedding configuration or task queue is unavailable |
