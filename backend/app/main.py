import json
import logging
import time
from typing import Optional

from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator

from .config import Settings, load_settings
from .db import Store
from .llm import AllProvidersFailed, complete, parse_simulation

DEFAULT_SYSTEM_PROMPT = "You are a helpful, concise assistant."
log = logging.getLogger("chatbot")


class ChatIn(BaseModel):
    session_id: str = Field(min_length=1, max_length=128)
    message: str
    system_prompt: Optional[str] = None

    @field_validator("session_id")
    @classmethod
    def _sid(cls, v: str) -> str:
        v = v.strip()
        if not 1 <= len(v) <= 128:
            raise ValueError("session_id must be 1-128 characters")
        return v

    @field_validator("message")
    @classmethod
    def _msg(cls, v: str) -> str:
        v = v.strip()
        if not 1 <= len(v) <= 4000:
            raise ValueError("message must be 1-4000 characters after trimming")
        return v


def create_app(settings: Optional[Settings] = None, store: Optional[Store] = None) -> FastAPI:
    settings = settings or load_settings()
    store = store or Store(settings.database_url)

    app = FastAPI(title="LLM Chatbot API")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.allowed_origins),
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(Exception)
    async def unhandled(_request, exc):
        log.exception("unhandled error: %s", type(exc).__name__)
        return JSONResponse(status_code=500, content={"detail": "internal server error"})

    @app.get("/health")
    def health():
        if not settings.keys:
            raise HTTPException(status_code=503, detail="no API keys configured")
        try:
            store.ping()
        except Exception:
            raise HTTPException(status_code=503, detail="database unavailable")
        return {"status": "ok", "keys_configured": len(settings.keys), "cache_enabled": True}

    @app.post("/chat")
    def chat(body: ChatIn, x_simulate_failure: Optional[str] = Header(default=None)):
        simulate = parse_simulation(x_simulate_failure) if settings.failure_simulation else {}
        sid = body.session_id
        system = body.system_prompt or store.system_prompt(sid) or DEFAULT_SYSTEM_PROMPT
        messages = [
            {"role": "system", "content": system},
            *store.history(sid),
            {"role": "user", "content": body.message},
        ]

        started = time.perf_counter()
        try:
            result = complete(messages, settings.keys, settings.model, simulate)
        except AllProvidersFailed:
            raise HTTPException(status_code=503, detail="all providers unavailable")
        latency_ms = round((time.perf_counter() - started) * 1000)

        meta = {
            "resolution_source": result.source,
            "model": result.model,
            "latency_ms": latency_ms,
            "input_tokens": result.input_tokens,
            "output_tokens": result.output_tokens,
            "key_id": result.key_id,
            "fallback_attempts": result.fallback_attempts,
        }
        store.append_turn(sid, body.message, result.reply, meta, body.system_prompt)
        return {"session_id": sid, "reply": result.reply, "metadata": meta}

    @app.get("/sessions/{session_id}/messages")
    def session_messages(session_id: str):
        if not store.session_exists(session_id):
            raise HTTPException(status_code=404, detail="session not found")
        out = []
        for row in store.messages(session_id):
            item = {"role": row["role"], "content": row["content"]}
            if row["metadata"]:
                item["metadata"] = json.loads(row["metadata"])
            out.append(item)
        return {"session_id": session_id, "messages": out}

    return app
