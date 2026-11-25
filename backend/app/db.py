import json
import os
import sqlite3
import threading
from datetime import datetime, timezone

SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
  session_id TEXT PRIMARY KEY,
  system_prompt TEXT,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS messages (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  session_id TEXT NOT NULL,
  role TEXT NOT NULL,
  content TEXT NOT NULL,
  metadata TEXT,
  created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id, id);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sqlite_path(url: str) -> str:
    # sqlite:////data/app.db -> /data/app.db
    return url[len("sqlite:///"):] if url.startswith("sqlite:///") else url


class Store:
    def __init__(self, database_url: str):
        path = sqlite_path(database_url)
        if path != ":memory:":
            os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(SCHEMA)
        self._lock = threading.Lock()

    def ping(self) -> None:
        with self._lock:
            self._conn.execute("SELECT 1").fetchone()

    def history(self, sid: str) -> list[dict]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT role, content FROM messages WHERE session_id=? ORDER BY id", (sid,)
            ).fetchall()
        return [{"role": r["role"], "content": r["content"]} for r in rows]

    def messages(self, sid: str) -> list[sqlite3.Row]:
        with self._lock:
            return self._conn.execute(
                "SELECT role, content, metadata FROM messages WHERE session_id=? ORDER BY id", (sid,)
            ).fetchall()

    def system_prompt(self, sid: str) -> str | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT system_prompt FROM sessions WHERE session_id=?", (sid,)
            ).fetchone()
        return row["system_prompt"] if row else None

    def session_exists(self, sid: str) -> bool:
        with self._lock:
            return self._conn.execute(
                "SELECT 1 FROM sessions WHERE session_id=?", (sid,)
            ).fetchone() is not None

    def append_turn(self, sid, user_text, reply, metadata, system_prompt=None) -> None:
        """Store one successful exchange atomically. Failed requests never reach this."""
        now = _now()
        with self._lock, self._conn:
            self._conn.execute(
                "INSERT INTO sessions(session_id, system_prompt, created_at) VALUES(?,?,?) "
                "ON CONFLICT(session_id) DO UPDATE SET "
                "system_prompt=COALESCE(excluded.system_prompt, sessions.system_prompt)",
                (sid, system_prompt, now),
            )
            self._conn.execute(
                "INSERT INTO messages(session_id, role, content, metadata, created_at) VALUES(?,?,?,?,?)",
                (sid, "user", user_text, None, now),
            )
            self._conn.execute(
                "INSERT INTO messages(session_id, role, content, metadata, created_at) VALUES(?,?,?,?,?)",
                (sid, "assistant", reply, json.dumps(metadata), now),
            )
