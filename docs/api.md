# Enterprise AI Platform — API Reference

Base URL: `/api/v1`

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
