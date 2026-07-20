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

## Knowledge Bases (V2 Preview)

All KB endpoints require `Authorization: Bearer <token>` header.

### `GET /knowledge-bases`

List knowledge bases for the current user.

**Response** `200 OK`
```json
[
  {
    "id": "uuid",
    "name": "string",
    "description": "string",
    "document_count": 0,
    "created_at": "datetime (ISO 8601)"
  }
]
```

### `POST /knowledge-bases`

Create a new knowledge base.

**Request Body**
```json
{
  "name": "string (required)",
  "description": "string (default: '')"
}
```

**Response** `201 Created`
```json
{
  "id": "uuid",
  "name": "string",
  "description": "string"
}
```

### `POST /knowledge-bases/{kb_id}/documents`

Upload a document to a knowledge base.

**Request** — `multipart/form-data`
- `file`: The file to upload (any type)

**Response** `201 Created`
```json
{
  "id": "uuid",
  "filename": "string",
  "status": "pending",
  "file_size": 12345
}
```

**Error** `404 Not Found` — Knowledge base not found.

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
| 404 | Resource not found |
| 409 | Conflict — duplicate resource |
| 422 | Validation error — invalid request body |
