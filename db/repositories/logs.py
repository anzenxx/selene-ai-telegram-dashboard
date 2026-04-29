from .base import get_connection


def init_logs_schema():
    conn = get_connection()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            bot_id INTEGER NOT NULL,
            chat_id TEXT,
            chat_name TEXT,
            direction TEXT,
            message TEXT NOT NULL,
            tokens_used INTEGER DEFAULT 0,
            timestamp TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (bot_id) REFERENCES bots(id) ON DELETE CASCADE
        )
        """
    )
    conn.commit()
    conn.close()


def add_log(bot_id, chat_id, chat_name, direction, message, tokens_used=0):
    conn = get_connection()
    conn.execute(
        """
        INSERT INTO logs (bot_id, chat_id, chat_name, direction, message, tokens_used)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (bot_id, str(chat_id), chat_name, direction, message, tokens_used),
    )
    conn.commit()
    conn.close()


def get_logs(bot_id, limit=200):
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        """
        SELECT * FROM logs WHERE bot_id = ?
        ORDER BY id DESC LIMIT ?
        """,
        (bot_id, limit),
    )
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return list(reversed(rows))


def clear_logs(bot_id):
    conn = get_connection()
    conn.execute("DELETE FROM logs WHERE bot_id = ?", (bot_id,))
    conn.commit()
    conn.close()
