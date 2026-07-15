ROOT=/api/v1

# Health
GET /health
→ 200 {status: "ok"}

# Auth
POST /auth/register        body: {username, email, password}
→ 201 {access_token, user}
POST /auth/login           body: {username, password}
→ 200 {access_token, user}
GET  /auth/me              header: Authorization: Bearer <token>
→ 200 {id, username, email, display_name}

# Chat
GET  /chat/conversations                           header: Bearer
→ 200 [{id, title, message_count, created_at}]
POST /chat/conversations   body: {title}           header: Bearer
→ 201 {id, title, created_at}
GET  /chat/conversations/{id}/messages             header: Bearer
→ 200 [{id, role, content, created_at}]

# Knowledge Bases
GET  /knowledge-bases                              header: Bearer
→ 200 [{id, name, description, document_count, created_at}]
POST /knowledge-bases       body: {name, description}  header: Bearer
→ 201 {id, name, description}
POST /knowledge-bases/{id}/documents  file: multipart  header: Bearer
→ 201 {id, filename, status, file_size}
