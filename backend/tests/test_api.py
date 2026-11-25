import types

import pytest
from fastapi.testclient import TestClient

from app import llm
from app.config import Settings
from app.db import Store
from app.main import create_app


class ProviderError(Exception):
    def __init__(self, status):
        super().__init__(f"HTTP {status}")
        self.status_code = status


def _resp(text="The capital of France is Paris."):
    return types.SimpleNamespace(
        choices=[types.SimpleNamespace(message=types.SimpleNamespace(content=text))],
        usage=types.SimpleNamespace(prompt_tokens=42, completion_tokens=9),
        _hidden_params={},
    )


def make_client(monkeypatch, bad=(), simulate=False):
    seen = []

    def fake_completion(model, messages, api_key, **kwargs):
        seen.append(api_key)
        if api_key in bad:
            raise ProviderError(429)
        return _resp()

    monkeypatch.setattr(llm.litellm, "completion", fake_completion)
    settings = Settings(keys=(("key_1", "k1"), ("key_2", "k2")), failure_simulation=simulate)
    return TestClient(create_app(settings, Store(":memory:"))), seen


def chat(c, sid="s-1", msg="What is the capital of France?", headers=None):
    return c.post("/chat", json={"session_id": sid, "message": msg}, headers=headers or {})


def test_health(monkeypatch):
    c, _ = make_client(monkeypatch)
    r = c.get("/health")
    assert r.status_code == 200
    assert r.json()["keys_configured"] == 2


def test_failover_to_second_key_on_429(monkeypatch):
    c, seen = make_client(monkeypatch, bad={"k1"})
    r = chat(c)
    assert r.status_code == 200
    assert r.json()["metadata"]["key_id"] == "key_2"
    assert r.json()["metadata"]["fallback_attempts"] == 1
    assert seen == ["k1", "k2"]


def test_validation_returns_422(monkeypatch):
    c, _ = make_client(monkeypatch)
    assert chat(c, msg="   ").status_code == 422
    assert chat(c, msg="x" * 4001).status_code == 422


def test_history_is_per_session(monkeypatch):
    c, _ = make_client(monkeypatch)
    chat(c, sid="a", msg="hi")
    chat(c, sid="a", msg="again")
    msgs = c.get("/sessions/a/messages").json()["messages"]
    assert [m["role"] for m in msgs] == ["user", "assistant", "user", "assistant"]
    assert c.get("/sessions/b/messages").status_code == 404


def test_simulated_failover(monkeypatch):
    c, _ = make_client(monkeypatch, simulate=True)
    r = chat(c, headers={"X-Simulate-Failure": "key_1=429"})
    assert r.status_code == 200
    assert r.json()["metadata"]["key_id"] == "key_2"


def test_all_keys_fail_gives_503_and_stores_nothing(monkeypatch):
    c, _ = make_client(monkeypatch, simulate=True)
    r = chat(c, sid="z", headers={"X-Simulate-Failure": "*=429"})
    assert r.status_code == 503
    assert r.json()["detail"] == "all providers unavailable"
    assert c.get("/sessions/z/messages").status_code == 404


def test_simulation_ignored_when_disabled(monkeypatch):
    c, _ = make_client(monkeypatch, simulate=False)
    r = chat(c, headers={"X-Simulate-Failure": "key_1=429"})
    assert r.json()["metadata"]["key_id"] == "key_1"
