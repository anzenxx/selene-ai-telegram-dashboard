from db.repositories import (
    DB_PATH,
    add_bot,
    clear_logs,
    delete_bot,
    empty_memory as _empty_memory,
    get_all_bots,
    get_bot,
    get_connection,
    get_last_seen,
    get_memory,
    get_stats,
    get_total_stats,
    init_bots_schema,
    init_logs_schema,
    init_memory_schema,
    init_stats_schema,
    normalize_memory_payload,
    save_memory,
    set_bot_active,
    update_bot,
    update_last_seen,
    update_stats,
)
from db.repositories.logs import add_log as _repo_add_log, get_logs


def init_db():
    init_bots_schema()
    init_logs_schema()
    init_stats_schema()
    init_memory_schema()


def add_log(bot_id, chat_id, chat_name, direction, message, tokens_used=0):
    _repo_add_log(bot_id, chat_id, chat_name, direction, message, tokens_used)
    update_stats(bot_id, tokens_used)
