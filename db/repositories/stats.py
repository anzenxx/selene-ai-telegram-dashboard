from datetime import datetime

from .base import get_connection


def init_stats_schema():
    conn = get_connection()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS stats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            bot_id INTEGER NOT NULL,
            date TEXT NOT NULL,
            messages_count INTEGER DEFAULT 0,
            tokens_total INTEGER DEFAULT 0,
            FOREIGN KEY (bot_id) REFERENCES bots(id) ON DELETE CASCADE
        )
        """
    )
    conn.commit()
    conn.close()


def update_stats(bot_id, tokens):
    today = datetime.now().strftime("%Y-%m-%d")
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT id FROM stats WHERE bot_id = ? AND date = ?", (bot_id, today))
    row = c.fetchone()
    if row:
        conn.execute(
            """
            UPDATE stats SET messages_count = messages_count + 1,
                             tokens_total = tokens_total + ?
            WHERE bot_id = ? AND date = ?
            """,
            (tokens, bot_id, today),
        )
    else:
        conn.execute(
            """
            INSERT INTO stats (bot_id, date, messages_count, tokens_total)
            VALUES (?, ?, 1, ?)
            """,
            (bot_id, today, tokens),
        )
    conn.commit()
    conn.close()


def get_stats(bot_id):
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        """
        SELECT date, messages_count, tokens_total
        FROM stats WHERE bot_id = ?
        ORDER BY date DESC LIMIT 7
        """,
        (bot_id,),
    )
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return rows


def get_total_stats(bot_id):
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        """
        SELECT COALESCE(SUM(messages_count),0) as total_msgs,
               COALESCE(SUM(tokens_total),0)   as total_tokens
        FROM stats WHERE bot_id = ?
        """,
        (bot_id,),
    )
    row = dict(c.fetchone())
    conn.close()
    return row
