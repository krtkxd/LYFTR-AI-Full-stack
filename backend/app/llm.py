import logging
from dataclasses import dataclass
from typing import Optional

import litellm
from litellm import Cache

log = logging.getLogger("chatbot.llm")
litellm.set_verbose = False
litellm.cache = Cache(type="local")  # LiteLLM built-in in-memory response cache

VALID_STATUSES = {429, 500, 502, 503}


class AllProvidersFailed(Exception):
    pass


@dataclass
class LLMResult:
    reply: str
    source: str            # LIVE_INFERENCE or LLM_CACHE
    model: str
    input_tokens: int
    output_tokens: int
    key_id: Optional[str]  # None on cache hit
    fallback_attempts: int


def parse_simulation(header: Optional[str]) -> dict:
    """'key_1=429,key_2=500' or '*=429' -> {'key_1': 429, ...}. Bad pairs are ignored."""
    forced = {}
    for part in (header or "").split(","):
        if "=" not in part:
            continue
        key, status = (p.strip() for p in part.split("=", 1))
        if key and status.isdigit() and int(status) in VALID_STATUSES:
            forced[key] = int(status)
    return forced


def complete(messages: list[dict], keys: tuple, model: str, simulate: Optional[dict] = None) -> LLMResult:
    simulate = simulate or {}
    use_cache = not simulate  # simulated requests skip the cache so failover is really exercised
    attempts = 0
    for key_id, api_key in keys:
        forced = simulate.get(key_id, simulate.get("*"))
        if forced is not None:
            log.warning("simulated HTTP %s on %s", forced, key_id)
            attempts += 1
            continue
        try:
            resp = litellm.completion(
                model=model,
                messages=messages,
                api_key=api_key,
                cache={"no-cache": not use_cache},
                timeout=30,
            )
            reply = (resp.choices[0].message.content or "").strip()
            if not reply:
                raise ValueError("empty reply")
            hit = bool((getattr(resp, "_hidden_params", None) or {}).get("cache_hit"))
            return LLMResult(
                reply=reply,
                source="LLM_CACHE" if hit else "LIVE_INFERENCE",
                model=model,
                input_tokens=resp.usage.prompt_tokens,
                output_tokens=resp.usage.completion_tokens,
                key_id=None if hit else key_id,
                fallback_attempts=0 if hit else attempts,
            )
        except Exception as exc:  # 429, quota, 5xx, timeouts: fail over to the next key
            attempts += 1
            log.warning("%s failed: status=%s type=%s", key_id,
                        getattr(exc, "status_code", None), type(exc).__name__)
    raise AllProvidersFailed()
