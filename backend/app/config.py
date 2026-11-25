import os
from dataclasses import dataclass, field


def _csv(name: str, default: str = "") -> tuple:
    return tuple(x.strip() for x in os.getenv(name, default).split(",") if x.strip())


@dataclass(frozen=True)
class Settings:
    # ((key_id, api_key), ...). Keys are hidden from repr so they never reach logs.
    keys: tuple = field(default=(), repr=False)
    database_url: str = "sqlite:///./app.db"
    allowed_origins: tuple = ("http://localhost:3000",)
    failure_simulation: bool = False
    model: str = "gemini/gemini-2.0-flash"


def load_settings() -> Settings:
    raw_keys = _csv("LLM_API_KEYS")
    return Settings(
        keys=tuple((f"key_{i}", k) for i, k in enumerate(raw_keys, 1)),
        database_url=os.getenv("DATABASE_URL", "sqlite:///./app.db"),
        allowed_origins=_csv("ALLOWED_ORIGINS", "http://localhost:3000"),
        failure_simulation=os.getenv("ENABLE_FAILURE_SIMULATION", "false").lower() == "true",
        model=os.getenv("LLM_MODEL", "gemini/gemini-2.0-flash"),
    )
