import litellm

from app import llm  # importing sets up litellm.cache (in-memory)


def test_real_litellm_cache_hit_returns_same_reply_and_usage():
    # Uses LiteLLM's real cache with mock_response, so no network is needed.
    msgs = [{"role": "system", "content": "S"},
            {"role": "user", "content": "cache-test: capital of France?"}]
    kw = dict(model="gpt-4o-mini", messages=msgs, api_key="x",
              mock_response="The capital of France is Paris.", cache={"no-cache": False})
    first = litellm.completion(**kw)
    second = litellm.completion(**kw)
    hit = lambda r: bool((getattr(r, "_hidden_params", None) or {}).get("cache_hit"))
    assert not hit(first)
    assert hit(second)
    assert first.choices[0].message.content == second.choices[0].message.content
    assert first.usage.prompt_tokens == second.usage.prompt_tokens
