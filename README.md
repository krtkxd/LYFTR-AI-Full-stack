# LYFTR-AI-Full-stack
LLM chatbot with multi-key failover and response caching. FastAPI and LiteLLM backend, React frontend, SQLite session history. Fails over between API keys on 429, quota, or 5xx errors, caches replies, and reports per-request tokens and latency.
