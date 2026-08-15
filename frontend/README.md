# Frontend — Enterprise AI Platform

React 18 + TypeScript + Vite + Tailwind CSS 前端应用。

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Framework | React 18, TypeScript |
| Build | Vite 8 |
| Routing | React Router v6 |
| HTTP | Axios (with JWT interceptor) |
| Styling | Tailwind CSS v4 |
| Dev Server | Vite (port 5173, proxy `/api` → `localhost:8000`) |

## Project Structure

```
src/
├── main.tsx                       # Entry point
├── App.tsx                        # Route definitions
├── index.css                      # Tailwind directives + global styles
├── api/                           # API layer
│   ├── client.ts                  # Axios instance + JWT interceptor
│   ├── auth.ts                    # Auth API (register, login, me)
│   └── chat.ts                    # Chat API (conversations, messages)
├── types/                         # TypeScript type definitions
│   ├── auth.ts                    # User, TokenResponse, ...
│   └── chat.ts                    # Conversation, Message, ...
├── context/
│   └── AuthContext.tsx             # Global auth state (user, token, login/logout)
├── hooks/
│   ├── useAuth.ts                 # Consume AuthContext
│   └── useChat.ts                 # Chat state management + API calls
├── components/
│   ├── ProtectedRoute.tsx         # Route guard — redirects to /login
│   ├── ConversationList.tsx       # Sidebar with conversation list
│   └── MessageList.tsx            # Message bubble display
└── pages/
    ├── Login.tsx                  # Sign in form
    ├── Register.tsx               # Sign up form
    └── Chat.tsx                   # Main chat interface
```

## Quick Start

Prerequisites: backend must be running (see [root README](../README.md)).

```bash
# Install dependencies
cd frontend
npm install

# Start dev server (port 5173)
npm run dev
```

Open `http://localhost:5173` in browser.

> Vite dev server proxies `/api/*` requests to `http://localhost:8000` (backend). No CORS issues during development.

## Available Scripts

```bash
npm run dev       # Start dev server with HMR
npm run build     # TypeScript check + production build → dist/
npm run preview   # Serve the production build locally
```

## Routing

| Path | Page | Access |
|------|------|--------|
| `/login` | Sign In | Public |
| `/register` | Create Account | Public |
| `/chat` | Chat (V1) | Authenticated |
| `/chat/:id` | Chat with selected conversation | Authenticated |
| `*` | Redirect to `/chat` | — |

## Extending for V2 / V3

Add new features by following the existing pattern:

1. **Types** → `src/types/<feature>.ts`
2. **API** → `src/api/<feature>.ts`
3. **Hooks** → `src/hooks/use<Feature>.ts`
4. **Pages** → `src/pages/<Feature>.tsx`
5. **Route** → Add to `src/App.tsx`

### Planned structure for future versions

```
src/
├── pages/
│   ├── KnowledgeBase.tsx         # V2: KB management
│   └── AgentConsole.tsx          # V3: Agent configuration
├── api/
│   ├── knowledge.ts              # V2: KB API
│   └── agent.ts                  # V3: Agent API
├── hooks/
│   ├── useKnowledge.ts           # V2
│   └── useAgent.ts               # V3
└── components/
    ├── DocumentUpload.tsx         # V2
    └── ToolList.tsx               # V3
```

## Build Output

```bash
npm run build
# → dist/
#   ├── index.html
#   ├── assets/
#   │   ├── index-xxx.css
#   │   └── index-xxx.js
```

Deploy `dist/` to any static file server (NGINX, S3, etc.) with a fallback rule for SPA routing.

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `VITE_API_BASE` | `/api/v1` | Backend API base URL (override for production) |

For production, set `VITE_API_BASE` to your backend URL and remove the Vite proxy.
