import json
from datetime import datetime

from .base import get_connection


def empty_memory() -> dict:
    return {
        "stable_facts": {},
        "recent_context": [],
        "emotional_cues": [],
    }


def dedupe_strings(values, limit: int):
    result = []
    seen = set()
    for value in values:
        if value is None:
            continue
        text = str(value).strip()
        if not text:
            continue
        key = text.lower()
        if key in seen:
            continue
        seen.add(key)
        result.append(text)
    return result[-limit:]


def normalize_memory_payload(payload) -> dict:
    base = empty_memory()
    if not isinstance(payload, dict):
        return base

    has_layered_keys = any(key in payload for key in ("stable_facts", "recent_context", "emotional_cues"))
    if not has_layered_keys:
        base["stable_facts"] = {
            str(key): value for key, value in payload.items()
            if value not in (None, "", [], {})
        }
        return base

    stable = payload.get("stable_facts", {})
    if isinstance(stable, dict):
        base["stable_facts"] = {
            str(key): value for key, value in stable.items()
            if value not in (None, "", [], {})
        }

    base["recent_context"] = dedupe_strings(payload.get("recent_context", []), 8)
    base["emotional_cues"] = dedupe_strings(payload.get("emotional_cues", []), 8)
    return base


def init_memory_schema():
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS memories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            bot_id INTEGER NOT NULL,
            chat_id TEXT NOT NULL,
            facts TEXT DEFAULT '{}',
            updated_at TEXT DEFAULT (datetime('now')),
            UNIQUE(bot_id, chat_id),
            FOREIGN KEY (bot_id) REFERENCES bots(id) ON DELETE CASCADE
        )
        """
    )
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS last_seen (
            bot_id INTEGER NOT NULL,
            chat_id TEXT NOT NULL,
            last_message_at TEXT NOT NULL,
            PRIMARY KEY (bot_id, chat_id),
            FOREIGN KEY (bot_id) REFERENCES bots(id) ON DELETE CASCADE
        )
        """
    )
    conn.commit()
    conn.close()


def get_memory(bot_id: int, chat_id: int) -> dict:
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT facts FROM memories WHERE bot_id = ? AND chat_id = ?", (bot_id, str(chat_id)))
    row = c.fetchone()
    conn.close()
    if row:
        try:
            return normalize_memory_payload(json.loads(row["facts"]))
        except Exception:
            return empty_memory()
    return empty_memory()


def save_memory(bot_id: int, chat_id: int, facts: dict):
    normalized = normalize_memory_payload(facts)
    conn = get_connection()
    conn.execute(
        """
        INSERT INTO memories (bot_id, chat_id, facts, updated_at)
        VALUES (?, ?, ?, datetime('now'))
        ON CONFLICT(bot_id, chat_id) DO UPDATE SET
            facts = excluded.facts,
            updated_at = excluded.updated_at
        """,
        (bot_id, str(chat_id), json.dumps(normalized, ensure_ascii=False)),
    )
    conn.commit()
    conn.close()


def get_last_seen(bot_id: int, chat_id: int) -> datetime | None:
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT last_message_at FROM last_seen WHERE bot_id = ? AND chat_id = ?", (bot_id, str(chat_id)))
    row = c.fetchone()
    conn.close()
    if row:
        try:
            return datetime.fromisoformat(row["last_message_at"])
        except Exception:
            return None
    return None


def update_last_seen(bot_id: int, chat_id: int):
    conn = get_connection()
    conn.execute(
        """
        INSERT INTO last_seen (bot_id, chat_id, last_message_at)
        VALUES (?, ?, datetime('now'))
        ON CONFLICT(bot_id, chat_id) DO UPDATE SET
            last_message_at = excluded.last_message_at
        """,
        (bot_id, str(chat_id)),
    )
    conn.commit()
    conn.close()
