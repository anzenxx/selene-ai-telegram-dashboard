from .base import get_connection


def init_bots_schema():
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS bots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            emoji TEXT DEFAULT '🤖',
            api_id TEXT NOT NULL,
            api_hash TEXT NOT NULL,
            phone TEXT NOT NULL,
            anthropic_key TEXT NOT NULL,
            claude_model TEXT DEFAULT 'claude-haiku-4-5',
            system_prompt TEXT DEFAULT '',
            trigger_prefix TEXT DEFAULT '.ai',
            max_tokens INTEGER DEFAULT 512,
            timezone TEXT DEFAULT 'Europe/Kiev',
            is_active INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now'))
        )
        """
    )
    try:
        c.execute("ALTER TABLE bots ADD COLUMN timezone TEXT DEFAULT 'Europe/Kiev'")
        conn.commit()
    except Exception:
        pass
    conn.commit()
    conn.close()


def add_bot(name, emoji, api_id, api_hash, phone, anthropic_key, claude_model, system_prompt, trigger_prefix, max_tokens, timezone="Europe/Kiev"):
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        """
        INSERT INTO bots (name, emoji, api_id, api_hash, phone, anthropic_key,
                          claude_model, system_prompt, trigger_prefix, max_tokens,
                          timezone)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (name, emoji, api_id, api_hash, phone, anthropic_key, claude_model, system_prompt, trigger_prefix, max_tokens, timezone),
    )
    bot_id = c.lastrowid
    conn.commit()
    conn.close()
    return bot_id


def get_all_bots():
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM bots ORDER BY id")
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return rows


def get_bot(bot_id):
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM bots WHERE id = ?", (bot_id,))
    row = c.fetchone()
    conn.close()
    return dict(row) if row else None


def update_bot(bot_id, **kwargs):
    if not kwargs:
        return
    fields = ", ".join(f"{k} = ?" for k in kwargs)
    values = list(kwargs.values()) + [bot_id]
    conn = get_connection()
    conn.execute(f"UPDATE bots SET {fields} WHERE id = ?", values)
    conn.commit()
    conn.close()


def delete_bot(bot_id):
    conn = get_connection()
    conn.execute("DELETE FROM bots WHERE id = ?", (bot_id,))
    conn.commit()
    conn.close()


def set_bot_active(bot_id, active: bool):
    conn = get_connection()
    conn.execute("UPDATE bots SET is_active = ? WHERE id = ?", (1 if active else 0, bot_id))
    conn.commit()
    conn.close()
