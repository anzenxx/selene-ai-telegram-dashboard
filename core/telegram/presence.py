from __future__ import annotations

import asyncio

from telethon.tl.functions.account import UpdateStatusRequest


class TelegramPresenceService:
    def __init__(self, client_getter):
        self._client_getter = client_getter

    @property
    def client(self):
        return self._client_getter()

    async def go_online(self):
        try:
            await self.client(UpdateStatusRequest(offline=False))
        except Exception:
            pass

    async def go_offline(self):
        try:
            await self.client(UpdateStatusRequest(offline=True))
        except Exception:
            pass

    async def go_offline_after(self, delay: float):
        await asyncio.sleep(delay)
        await self.go_offline()

    async def mark_chat_read(self, chat_id: int):
        try:
            await self.client.send_read_acknowledge(chat_id)
        except Exception:
            pass
