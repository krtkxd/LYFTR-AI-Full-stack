# LLM Chatbot with Key Failover and Response Caching

A full-stack chatbot built with React, FastAPI, LiteLLM and SQLite. It keeps multi-turn conversations per session, fails over between API keys when a provider returns 429, quota or 5xx errors, caches replies, and reports the source, model, latency and token usage of every reply.

## 1. Live URLs

- Frontend: `TBD`
- Backend: `TBD`

## 2. Run locally

### With Docker (recommended)

```bash
make up      # creates .env from .env.example if missing, then builds and starts both services
make down    # stops the stack
```

- Frontend: http://localhost:3000
- Backend: http://localhost:8000

Add at least two real keys to `LLM_API_KEYS` in `.env` before using live models.

### Without Docker

```bash
# Backend
cd backend
pip install -r requirements.txt
LLM_API_KEYS=key1,key2 \
DATABASE_URL=sqlite:///./app.db \
ALLOWED_ORIGINS=http://localhost:5173 \
ENABLE_FAILURE_SIMULATION=true \
uvicorn app.main:create_app --factory --port 8000

# Frontend (separate terminal)
cd frontend
npm install
npm run dev   # http://localhost:5173
```

`ALLOWED_ORIGINS` must include the frontend's origin, or the browser will block requests.

### Tests

```bash
make test
```

## 3. Design decisions

### Key fallback

Keys are tried in order (`key_1`, `key_2`, ...). Any failure from a call (429, quota, 5xx or timeout) moves the request to the next key, and each failed attempt is counted in `fallback_attempts`. If every key fails, the API returns `503 {"detail": "all providers unavailable"}`, and the failed request is not saved to history. Users never see a stack trace. Retries happen only by rotating keys, so a rate-limited key is not retried in place.

### Caching

LiteLLM's built-in in-memory cache is enabled. Its cache key covers the model and the full message list (system prompt, history and new message), so a different message or context never gets a stale reply. Each reply is labelled `LLM_CACHE` or `LIVE_INFERENCE` from LiteLLM's cache-hit flag. A cache hit returns the stored reply and usage, with `key_id: null` and `fallback_attempts: 0`. Requests carrying `X-Simulate-Failure` skip the cache so that the simulated failover really runs.

### SQLite session storage

Two tables hold the data: `messages` for conversation history and `sessions` for each session's optional system prompt. The database lives at `DATABASE_URL` (`/data/app.db` in Docker) on a named volume, so history survives container restarts. The schema is created on startup. Each exchange is written in a single transaction, and only after a successful reply.

### Token usage

Token counts come from the provider's usage for each individual call. They are never a running total across the conversation.

## 4. Verification

### Failover through the test hook

The hook needs `ENABLE_FAILURE_SIMULATION=true`.

```bash
# One key fails: the reply should come from key_2 with fallback_attempts = 1
curl -s -X POST localhost:8000/chat \
  -H 'Content-Type: application/json' \
  -H 'X-Simulate-Failure: key_1=429' \
  -d '{"session_id":"demo-1","message":"What is the capital of France?"}'

# Every key fails: expect HTTP 503 and nothing added to history
curl -s -X POST localhost:8000/chat \
  -H 'Content-Type: application/json' \
  -H 'X-Simulate-Failure: *=429' \
  -d '{"session_id":"demo-2","message":"hello"}'
```

### Cache hit

Send the same first message in two new sessions. The second reply reports `resolution_source: LLM_CACHE`, `key_id: null`, and the same reply text.

### Per-message tokens

The UI shows input and output tokens under each reply. The history endpoint returns them too:

```bash
curl -s localhost:8000/sessions/demo-1/messages
```

## 5. Setup used

- **Editor and tools:** built with an AI coding assistant.
- **Backend:** Python 3.11, FastAPI, LiteLLM, Pydantic, SQLite.
- **Frontend:** React 18, Vite.
- **Deployment:** Docker multi-stage builds, Docker Compose, Makefile.

## 6. Bonus features

Beyond the brief: a session system prompt field, and a backend test that runs LiteLLM's real cache path offline. Not included, for time: streaming replies and key pools spanning multiple providers.

## Project layout

```
backend/    FastAPI app (app/), tests (tests/), Dockerfile
frontend/   React + Vite app (src/), Dockerfile (nginx)
docker-compose.yml, Makefile, .env.example
```
