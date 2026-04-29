from core.agent import UserBot
from db.database import get_all_bots, get_bot


class BotManager:
    """Manages multiple UserBot instances."""

    def __init__(self, log_callback=None, state_callback=None):
        self.bots: dict[int, UserBot] = {}
        self.log_cb = log_callback
        self.state_cb = state_callback

    def set_log_callback(self, cb):
        self.log_cb = cb
        for bot in self.bots.values():
            bot.log_cb = cb

    def set_state_callback(self, cb):
        self.state_cb = cb
        for bot in self.bots.values():
            bot.state_cb = cb

    def load_bots(self):
        """Load all bots from DB (does not start them)."""
        for cfg in get_all_bots():
            if cfg["id"] not in self.bots:
                self.bots[cfg["id"]] = UserBot(cfg, self.log_cb, self.state_cb)

    def refresh_bot(self, bot_id: int):
        """Reload config for a single bot (does not restart if running)."""
        cfg = get_bot(bot_id)
        if not cfg:
            return
        if bot_id in self.bots:
            self.bots[bot_id].config = cfg
            self.bots[bot_id].log_cb = self.log_cb
            self.bots[bot_id].state_cb = self.state_cb
        else:
            self.bots[bot_id] = UserBot(cfg, self.log_cb, self.state_cb)

    def start_bot(self, bot_id: int):
        if bot_id not in self.bots:
            self.refresh_bot(bot_id)
        self.bots[bot_id].start()

    def stop_bot(self, bot_id: int):
        if bot_id in self.bots:
            self.bots[bot_id].stop()

    def remove_bot(self, bot_id: int):
        if bot_id in self.bots:
            self.bots[bot_id].stop()
            del self.bots[bot_id]

    def is_running(self, bot_id: int) -> bool:
        return self.bots.get(bot_id, None) is not None and self.bots[bot_id].running

    def get_uptime(self, bot_id: int) -> str:
        bot = self.bots.get(bot_id)
        return bot.get_uptime() if bot else "—"

    def stop_all(self):
        for bot in self.bots.values():
            bot.stop()
