# LLM Chatbot with Key Failover and Response Caching

## 1. Live URLs
- Frontend: _not deployed yet, add URL after deploy_
- Backend: _not deployed yet, add URL after deploy_

Deploy the backend first. Set `VITE_API_URL` in the frontend build to the backend URL, and set `ALLOWED_ORIGINS` on the backend to the frontend URL.

## 2. Run locally

With Docker:
```bash
make up        # creates .env from .env.example if missing, then builds and starts both services
make down
```
Frontend: http://localhost:3000. Backend: http://localhost:8000. Add real keys to `.env` (`LLM_API_KEYS`) before using live models.

Without Docker:
```bash
cd backend && pip install -r requirements.txt
LLM_API_KEYS=k1,k2 DATABASE_URL=sqlite:///./app.db ENABLE_FAILURE_SIMULATION=true \
  uvicorn app.main:create_app --factory --port 8000
cd frontend && npm install && npm run dev      # http://localhost:5173
```
Tests: `make test`.

## 3. Design decisions

**Key fallback.** Keys are tried in order (`key_1`, `key_2`, ...). Any exception from a call (429, quota, 5xx, timeout) moves to the next key, and the failed attempt is counted in `fallback_attempts`. If every key fails, the API returns 503 with `all providers unavailable`. Exceptions never reach the user as a stack trace. A failed request writes nothing to SQLite, so history only holds successful turns. `litellm.completion` is called with `num_retries` at its default of 0, so retries happen only through key rotation.

**Caching.** LiteLLM's built-in cache is enabled in memory. LiteLLM keys entries on model and the full message list, which includes the system prompt and history, so a different message or context never returns a cached reply. Each reply is labelled `LLM_CACHE` or `LIVE_INFERENCE` from LiteLLM's `cache_hit` flag. A cache hit returns the stored reply and usage, with `key_id` null and `fallback_attempts` 0. Requests carrying `X-Simulate-Failure` bypass the cache, so the simulated failover is actually exercised.

**SQLite session storage.** One `messages` table holds the history, and a `sessions` table holds each session's optional system prompt. The database file lives at `DATABASE_URL` (`/data/app.db`) on a named Docker volume, so it survives restarts. The schema is created on startup. Tokens are per request, taken from the provider's usage for that call only.

## 4. Verification

Failover through the test hook (needs `ENABLE_FAILURE_SIMULATION=true`):
```bash
curl -s -X POST localhost:8000/chat -H 'Content-Type: application/json' \
  -H 'X-Simulate-Failure: key_1=429' \
  -d '{"session_id":"demo-1","message":"What is the capital of France?"}'
# metadata.key_id = "key_2", fallback_attempts = 1

curl -s -X POST localhost:8000/chat -H 'Content-Type: application/json' \
  -H 'X-Simulate-Failure: *=429' \
  -d '{"session_id":"demo-1","message":"hello"}'
# HTTP 503 {"detail":"all providers unavailable"}, nothing stored
```

Cache hit: send the same first message in two new sessions. The second reply reports `resolution_source: LLM_CACHE`, `key_id: null`, and the same `reply` text.

Per-message tokens: every assistant bubble in the UI shows its own input and output token counts. The history endpoint returns the same numbers in `metadata`:
```bash
curl -s localhost:8000/sessions/demo-1/messages
```

## 5. Setup Used
Built with an AI coding assistant. The backend is FastAPI, with LiteLLM for provider calls, caching and key handling. The frontend is React with Vite. Docker multi-stage builds are used for both services.

## 6. Bonus features
None beyond the spec. Left out for time: streaming replies, per-model key pools across providers, and a backend test for LiteLLM's cache hit path (the tests mock the provider call).

## Verification status (what was actually run)
- Backend unit and API tests pass (`make test`), including a test that exercises LiteLLM's real cache path offline.
- Frontend builds with `npm run build`.
- Not run here: Docker builds (no Docker in the build environment), a real provider call with live keys, and the deployed URLs. Run `make up` and the curl checks in section 4 to confirm these.
