"""
agent.py — новая оркестрация поведения бота поверх сервисов.
"""

from __future__ import annotations

import asyncio
import os
import random
import re
import threading
from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from telethon import TelegramClient, events

from core.behavior.reply_pipeline import ReplyPipeline
from core.behavior.timing import TimingPolicy
from core.llm.client import ClaudeConversationService
from core.memory.service import MemoryService
from core.runtime.chat_runtime import ChatRuntimeStore, trim_list
from core.telegram.presence import TelegramPresenceService
from db.database import add_log, set_bot_active


MAX_HISTORY_MESSAGES = 24
MAX_RECENT_MESSAGES = 8
TYPO_CHANCE = 0.07
TYPO_FIX_CHANCE = 0.35
SURPRISE_CHANCE = 0.04

STATE_DELAYS = {
    "new_contact": (180, 720),
    "reopening": (120, 480),
    "warming_up": (35, 150),
    "engaged": (6, 35),
    "cooldown": (90, 360),
    "silent": (480, 1200),
}

IGNORE_CHANCES = {
    "new_contact": 0.10,
    "reopening": 0.08,
    "warming_up": 0.04,
    "engaged": 0.01,
    "cooldown": 0.06,
    "silent": 0.12,
}

MULTIPART_CHANCES = {
    "new_contact": 0.08,
    "reopening": 0.12,
    "warming_up": 0.22,
    "engaged": 0.34,
    "cooldown": 0.16,
    "silent": 0.10,
}

STICKER_REPLY_CHANCES = {
    "new_contact": 0.45,
    "reopening": 0.55,
    "warming_up": 0.70,
    "engaged": 0.85,
    "cooldown": 0.50,
    "silent": 0.30,
}

STICKER_DELAYS = {
    "new_contact": (12, 40),
    "reopening": (20, 90),
    "warming_up": (8, 25),
    "engaged": (3, 12),
    "cooldown": (40, 180),
    "silent": (60, 300),
}

STICKER_REACTIONS = {
    "ack": ["ахах, поняла", "засчитано", "намек считан", "ладно, принято"],
    "tease": ["вот это ты выразительно", "сурово вообще", "ну все, меня оценили", "жесткий стикер, если честно"],
    "soft": ["ладно, принимается", "хорошо, убедил", "я поняла посыл", "мягко, но колко"],
    "bounce": ["ахах, ладно", "это было в тему", "я оценила", "умеешь разговаривать стикерами"],
}

NIGHT_START = 0
NIGHT_END = 9
NIGHT_SLOW_MULTIPLIER = 1.35
DEFAULT_TZ = "Europe/Kiev"

CONTINUATION_MARKERS = (
    "и", "и еще", "и ещё", "а потом", "потом", "короче", "в общем", "прикинь", "и тут", "но", "но потом", "ещё", "еще",
)
QUESTION_MARKERS = ("?", "что думаешь", "как думаешь", "почему", "зачем", "как тебе", "как считаешь", "что скажешь", "что делать")
EMOTION_MARKERS = ("блин", "капец", "ужас", "обидно", "страшно", "рад", "рада", "грустно", "волнительно", "переживаю", "смешно")
REPEATED_OPENERS = ("если честно", "честно", "ну да", "ну", "ахах", "ха", "ладно", "в целом")


def get_timezone(tz_name: str) -> ZoneInfo:
    try:
        return ZoneInfo(tz_name or DEFAULT_TZ)
    except (ZoneInfoNotFoundError, Exception):
        return ZoneInfo(DEFAULT_TZ)


def is_night(tz: ZoneInfo) -> bool:
    return NIGHT_START <= datetime.now(tz).hour < NIGHT_END


def delay_for_length(text_len: int) -> float:
    if text_len <= 40:
        return random.uniform(1.0, 3.5)
    if text_len <= 140:
        return random.uniform(3.0, 8.0)
    if text_len <= 320:
        return random.uniform(8.0, 16.0)
    return random.uniform(14.0, 28.0)


def inject_typo(text: str) -> str:
    words = text.split()
    if not words:
        return text
    candidates = [i for i, w in enumerate(words) if len(w) > 3 and w.isalpha()]
    if not candidates:
        return text
    idx = random.choice(candidates)
    word = list(words[idx])
    keyboard_neighbors = {
        "а": "ф", "б": "в", "в": "б", "г": "р", "д": "е", "е": "д", "ж": "з", "з": "ж", "и": "у",
        "к": "л", "л": "к", "м": "н", "н": "м", "о": "п", "п": "о", "р": "г", "с": "а", "т": "ы",
        "у": "и", "ф": "а", "х": "ъ", "ц": "ч", "ч": "ц", "ш": "щ", "щ": "ш", "ы": "т", "э": "ю",
        "ю": "э", "я": "ч",
    }
    char_idx = random.randint(0, len(word) - 1)
    ch = word[char_idx].lower()
    if ch in keyboard_neighbors:
        word[char_idx] = keyboard_neighbors[ch]
    words[idx] = "".join(word)
    return " ".join(words)


def contains_any(text: str, markers: tuple[str, ...]) -> bool:
    normalized = text.lower()
    return any(marker in normalized for marker in markers)


def looks_like_question(text: str) -> bool:
    return contains_any(text, QUESTION_MARKERS)


def looks_like_continuation(text: str) -> bool:
    normalized = text.lower().strip()
    if not normalized:
        return False
    if normalized.endswith(("...", "…", ",", "-", "—")):
        return True
    return normalized.startswith(CONTINUATION_MARKERS)


def looks_like_completion(text: str) -> bool:
    normalized = text.lower().strip()
    if not normalized:
        return False
    if looks_like_question(normalized):
        return True
    return normalized.endswith(("?", ".", "!", "?!")) or normalized.endswith(("что думаешь", "как считаешь", "и всё", "вот"))


class UserBot:
    def __init__(self, bot_config: dict, log_callback=None, state_callback=None):
        self.config = bot_config
        self.bot_id = bot_config["id"]
        self.log_cb = log_callback
        self.state_cb = state_callback
        self.client = None
        self.running = False
        self._loop = None
        self._thread = None
        self.start_time = None
        self.tz = get_timezone(bot_config.get("timezone", DEFAULT_TZ))
        self._debounce_tokens: dict[int, object] = {}

        self.runtime = ChatRuntimeStore(self.bot_id, looks_like_continuation, looks_like_completion, looks_like_question)
        self.llm = ClaudeConversationService(bot_config, self.tz)
        self.memory = MemoryService(self.bot_id, self.llm.client)
        self.reply_pipeline = ReplyPipeline(REPEATED_OPENERS, MULTIPART_CHANCES)
        self.timing = TimingPolicy(
            STATE_DELAYS,
            IGNORE_CHANCES,
            STICKER_REPLY_CHANCES,
            STICKER_DELAYS,
            NIGHT_SLOW_MULTIPLIER,
            is_night,
            delay_for_length,
        )
        self.presence = TelegramPresenceService(lambda: self.client)

    def _log(self, chat_id, chat_name, direction, message, tokens=0):
        add_log(self.bot_id, chat_id, chat_name, direction, message, tokens)
        if self.log_cb:
            self.log_cb(self.bot_id, {"timestamp": datetime.now().strftime("%H:%M:%S"), "chat_name": chat_name or str(chat_id), "direction": direction, "message": message, "tokens": tokens})

    def _emit_state(self, state: str, message: str | None = None):
        if self.state_cb:
            self.state_cb(self.bot_id, state, {"message": message} if message else {})

    def _resolve_reply_intent(self, grouped_user_turn: str, thought_group: dict) -> str:
        message_count = len(thought_group["messages"])
        question_count = sum(1 for item in thought_group["messages"] if looks_like_question(item["text"]))
        total_length = sum(len(item["text"]) for item in thought_group["messages"])

        if question_count >= 2 or (question_count >= 1 and message_count >= 4 and total_length > 240):
            return "multi_topic"
        if question_count >= 1:
            return "question"
        if contains_any(grouped_user_turn, EMOTION_MARKERS):
            return "emotion"
        if message_count >= 4 or total_length > 260:
            return "story"
        if total_length < 40:
            return "presence_check"
        return "small_talk"

    def _build_grouped_user_turn(self, thought_group: dict, intent: str, state: str) -> str:
        lines = [item["text"] for item in thought_group["messages"]]
        dominant_rule = {
            "question": "Respond directly to the question first.",
            "emotion": "Respond to the emotion before giving any practical follow-up.",
            "story": "Acknowledge the story and respond to the most recent meaningful point.",
            "presence_check": "Keep the reply light and concise.",
            "multi_topic": "Answer the dominant current thread and avoid scattering across old topics.",
            "small_talk": "Keep it natural, concise, and chat-like.",
        }[intent]
        return (
            f"Conversation state: {state}\n"
            f"Detected user intent: {intent}\n"
            "These messages belong to one continuous user turn.\n"
            f"{dominant_rule}\n\n"
            "User turn:\n"
            + "\n".join(f"- {line}" for line in lines)
        )

    async def _simulate_typing(self, chat_id: int, text: str, state: str, intent: str):
        total_typing = delay_for_length(len(text))
        if state == "engaged":
            total_typing *= 0.8
        if intent == "question":
            total_typing *= 0.85
        if len(text) < 30:
            total_typing = min(total_typing, 2.5)
        total_typing = min(total_typing, 12.0)

        elapsed = 0.0
        while elapsed < total_typing:
            chunk = min(random.uniform(1.6, 3.8), total_typing - elapsed)
            async with self.client.action(chat_id, "typing"):
                await asyncio.sleep(chunk)
            elapsed += chunk
            if elapsed < total_typing and random.random() < 0.18:
                pause = min(random.uniform(0.4, 1.4), total_typing - elapsed)
                await asyncio.sleep(pause)
                elapsed += pause

    async def _send_with_typo(self, chat_id: int, text: str, reply_to: int | None = None):
        has_typo = random.random() < TYPO_CHANCE and len(text) > 14
        if has_typo:
            typo_text = inject_typo(text)
            await self.client.send_message(chat_id, typo_text, reply_to=reply_to)
            if random.random() < TYPO_FIX_CHANCE:
                await asyncio.sleep(random.uniform(1.8, 4.2))
                orig_words = text.split()
                typo_words = typo_text.split()
                fixed_word = None
                for original, typo in zip(orig_words, typo_words):
                    if original != typo:
                        fixed_word = original
                        break
                if fixed_word:
                    await self.client.send_message(chat_id, f"{fixed_word}*")
        else:
            await self.client.send_message(chat_id, text, reply_to=reply_to)

    def _select_reply_target(self, thought_group: dict, intent: str, state: str) -> int | None:
        messages = thought_group.get("messages", [])
        valid_targets = [item for item in messages if item.get("message_id")]
        if not valid_targets:
            return None

        base_chance = 0.0
        if intent == "multi_topic":
            base_chance = 0.72
        elif intent == "question" and len(valid_targets) >= 2:
            base_chance = 0.42
        elif intent == "story" and len(valid_targets) >= 4:
            base_chance = 0.26
        if state == "engaged":
            base_chance *= 1.12
        if len(valid_targets) == 1:
            base_chance *= 0.45
        if random.random() >= base_chance:
            return None

        if intent in {"multi_topic", "question"}:
            question_targets = [item for item in valid_targets if looks_like_question(item["text"])]
            if question_targets:
                return question_targets[-1]["message_id"]
        return valid_targets[-1]["message_id"]

    def _build_sticker_reaction(self, chat_id: int) -> list[str]:
        runtime = self.runtime.get(chat_id)
        if runtime["state"] == "engaged":
            pool = "tease" if random.random() < 0.55 else "bounce"
        elif runtime["state"] in {"new_contact", "reopening", "silent"}:
            pool = "soft" if random.random() < 0.45 else "ack"
        else:
            pool = "ack" if random.random() < 0.5 else "bounce"
        first = random.choice(STICKER_REACTIONS[pool])
        parts = [first]
        if runtime["state"] == "engaged" and random.random() < 0.25:
            second_pool = "bounce" if pool != "bounce" else "ack"
            second = random.choice(STICKER_REACTIONS[second_pool])
            if second != first:
                parts.append(second)
        return parts[:2]

    def _schedule_response_check(self, chat_id: int):
        token = object()
        self._debounce_tokens[chat_id] = token
        delay = self.runtime.resolve_group_wait(chat_id)
        loop = self._loop or asyncio.get_event_loop()

        async def fire(my_token):
            await asyncio.sleep(delay)
            if self._debounce_tokens.get(chat_id) is not my_token:
                return
            if not self.runtime.should_close_thought_group(chat_id, datetime.now()):
                self._schedule_response_check(chat_id)
                return
            runtime = self.runtime.get(chat_id)
            await self._respond(chat_id, runtime["chat_name"] or str(chat_id))

        loop.create_task(fire(token))

    async def _respond(self, chat_id: int, chat_name: str):
        runtime = self.runtime.get(chat_id)
        thought_group = runtime["thought_group"]
        if not thought_group or not thought_group["messages"]:
            return

        intent = self._resolve_reply_intent("\n".join(item["text"] for item in thought_group["messages"]), thought_group)
        runtime["last_intent"] = intent
        user_text = self._build_grouped_user_turn(thought_group, intent, runtime["state"])

        self._log(chat_id, chat_name, "in", user_text)
        if self.timing.should_ignore(runtime, intent):
            self._log(chat_id, chat_name, "info", f"🙈 Intentionally holding back in state {runtime['state']}")
            runtime["thought_group"] = None
            runtime["last_dialogue_at"] = datetime.now()
            await self.presence.go_offline()
            return

        await self.presence.go_offline()
        delay = self.timing.resolve_response_delay(runtime, self.tz, intent, sum(len(item["text"]) for item in thought_group["messages"]))
        self._log(chat_id, chat_name, "info", f"⏳ {runtime['state']} / {intent}, ждём {int(delay)} сек")
        await asyncio.sleep(delay)

        if not self.running or runtime["thought_group"] is not thought_group:
            return

        try:
            reply, tokens = await asyncio.get_event_loop().run_in_executor(None, lambda: self.llm.ask(chat_id, user_text, runtime, self.memory.get(chat_id), MAX_HISTORY_MESSAGES))
        except Exception as exc:
            self._log(chat_id, chat_name, "out", f"[Ошибка Claude: {exc}]")
            return

        parts = self.reply_pipeline.filter_reply_parts(self.config, runtime, reply, intent)
        reply_target = self._select_reply_target(thought_group, intent, runtime["state"])
        await self.presence.go_online()
        await self.presence.mark_chat_read(chat_id)
        await asyncio.sleep(random.uniform(0.6, 1.8))

        if runtime["state"] not in {"engaged", "warming_up"} and random.random() < 0.05:
            filler = random.choice(["хм", "мм"])
            await self._send_with_typo(chat_id, filler)
            await asyncio.sleep(random.uniform(0.8, 1.8))

        current_tokens = tokens
        for index, part in enumerate(parts):
            if random.random() < SURPRISE_CHANCE:
                await asyncio.sleep(random.uniform(0.2, 1.5))
            await self._simulate_typing(chat_id, part, runtime["state"], intent)
            await self._send_with_typo(chat_id, part, reply_to=reply_target if index == 0 else None)
            self._log(chat_id, chat_name, "out", part, current_tokens if index == 0 else 0)
            current_tokens = 0
            runtime["recent_bot_messages"].append(part)
            trim_list(runtime["recent_bot_messages"], MAX_RECENT_MESSAGES)
            if index < len(parts) - 1:
                await asyncio.sleep(random.uniform(0.8, 3.5))

        self.runtime.update_on_outgoing(chat_id, datetime.now())
        asyncio.ensure_future(self.presence.go_offline_after(random.uniform(25, 75)))
        dialog_lines = [
            "собеседник: " + " | ".join(item["text"] for item in thought_group["messages"]),
            "бот: " + " ".join(parts),
        ]
        asyncio.ensure_future(asyncio.get_event_loop().run_in_executor(None, self.memory.extract, chat_id, dialog_lines))

    async def _handle_sticker_turn(self, chat_id: int, chat_name: str):
        runtime = self.runtime.get(chat_id)
        received_at = datetime.now()
        runtime["chat_id"] = chat_id
        runtime["chat_name"] = chat_name
        runtime["incoming_streak"] = runtime.get("incoming_streak", 0) + 1
        runtime["outgoing_streak"] = 0
        runtime["conversation_openness"] = min(1.0, runtime["conversation_openness"] + 0.03)
        runtime["last_user_message_at"] = received_at
        runtime["last_intent"] = "sticker"
        runtime["state"] = self.runtime.resolve_state_from_gap(runtime, received_at, incoming=True)

        if not self.timing.should_reply_to_sticker(runtime):
            return

        delay = self.timing.resolve_sticker_delay(runtime, self.tz)
        self._log(chat_id, chat_name, "info", f"🪄 sticker / {runtime['state']}, ждём {int(delay)} сек")
        await asyncio.sleep(delay)
        if not self.running:
            return

        await self.presence.go_online()
        await self.presence.mark_chat_read(chat_id)
        await asyncio.sleep(random.uniform(0.4, 1.2))

        parts = self._build_sticker_reaction(chat_id)
        for index, part in enumerate(parts):
            await self._simulate_typing(chat_id, part, runtime["state"], "presence_check")
            await self._send_with_typo(chat_id, part)
            self._log(chat_id, chat_name, "out", part, 0)
            runtime["recent_bot_messages"].append(part)
            trim_list(runtime["recent_bot_messages"], MAX_RECENT_MESSAGES)
            if index < len(parts) - 1:
                await asyncio.sleep(random.uniform(0.6, 1.4))

        self.runtime.update_on_outgoing(chat_id, datetime.now())
        asyncio.ensure_future(self.presence.go_offline_after(random.uniform(20, 55)))

    async def _debounce_handler(self, chat_id: int, chat_name: str, message: str, message_id: int | None = None):
        self.runtime.update_on_incoming(chat_id, chat_name, message, datetime.now(), message_id)
        self._schedule_response_check(chat_id)

    async def _setup_handlers(self):
        raw_prefix = self.config["trigger_prefix"].strip()
        no_prefix = raw_prefix == ""

        if no_prefix:
            @self.client.on(events.NewMessage(incoming=True, func=lambda e: e.is_private))
            async def on_message(event):
                user_text = (event.raw_text or "").strip()
                chat = await event.get_chat()
                chat_name = getattr(chat, "title", None) or getattr(chat, "first_name", None) or str(event.chat_id)
                if getattr(event, "sticker", False) and not user_text:
                    await self._handle_sticker_turn(event.chat_id, chat_name)
                    return
                if not user_text:
                    return
                await self._debounce_handler(event.chat_id, chat_name, user_text, event.id)
        else:
            prefix = re.escape(raw_prefix)
            pattern = re.compile(rf"^{prefix}\s+(.*)", re.S | re.DOTALL)

            @self.client.on(events.NewMessage(pattern=pattern))
            async def on_message(event):
                if not event.out:
                    return
                user_text = event.pattern_match.group(1).strip()
                if not user_text:
                    return
                chat = await event.get_chat()
                chat_name = getattr(chat, "title", None) or getattr(chat, "first_name", None) or str(event.chat_id)
                await event.edit("⏳")
                try:
                    reply, tokens = await asyncio.get_event_loop().run_in_executor(None, lambda: self.llm.ask(event.chat_id, user_text, self.runtime.get(event.chat_id), self.memory.get(event.chat_id), MAX_HISTORY_MESSAGES))
                    parts = self.reply_pipeline.filter_reply_parts(self.config, self.runtime.get(event.chat_id), reply, "question")
                    if parts:
                        await event.edit(parts[0])
                        self._log(event.chat_id, chat_name, "out", parts[0], tokens)
                        for part in parts[1:]:
                            await asyncio.sleep(random.uniform(0.8, 2.2))
                            await self._send_with_typo(event.chat_id, part)
                            self._log(event.chat_id, chat_name, "out", part, 0)
                    else:
                        await event.edit(reply)
                        self._log(event.chat_id, chat_name, "out", reply, tokens)
                except Exception as exc:
                    await event.edit(f"[Ошибка: {exc}]")

    async def _run(self):
        cfg = self.config
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        sessions_dir = os.path.join(base_dir, "sessions")
        os.makedirs(sessions_dir, exist_ok=True)
        session_file = os.path.join(sessions_dir, f"bot_{self.bot_id}")

        self.client = TelegramClient(session_file, int(cfg["api_id"]), cfg["api_hash"])
        session_path = session_file + ".session"
        if not os.path.exists(session_path) or os.path.getsize(session_path) == 0:
            raise RuntimeError(f"Сессия не найдена: {session_path}\nСначала запустите  python create_session.py  и войдите в аккаунт.")

        await self.client.connect()
        if not await self.client.is_user_authorized():
            raise RuntimeError("Сессия есть, но авторизация не прошла.\nУдалите файл сессии и запустите  python create_session.py  заново.")

        await self._setup_handlers()
        self.running = True
        self.start_time = datetime.now()
        set_bot_active(self.bot_id, True)
        self._emit_state("running")
        self._log(None, "СИСТЕМА", "info", f"✅ {cfg['name']} запущен")
        await self.client.run_until_disconnected()

    def start(self):
        if self.running:
            return
        self.running = True
        self.start_time = datetime.now()
        set_bot_active(self.bot_id, True)
        self._emit_state("starting")
        self._loop = asyncio.new_event_loop()

        def thread_target():
            asyncio.set_event_loop(self._loop)
            failure_message = None
            try:
                self._loop.run_until_complete(self._run())
            except Exception as exc:
                failure_message = str(exc)
                self._log(None, "СИСТЕМА", "error", f"❌ {self.config['name']} failed to start: {exc}")
            finally:
                self.running = False
                self.start_time = None
                set_bot_active(self.bot_id, False)
                self._emit_state("error" if failure_message else "stopped", failure_message)

        self._thread = threading.Thread(target=thread_target, daemon=True)
        self._thread.start()

    def stop(self):
        if not self.running:
            return
        self.running = False
        set_bot_active(self.bot_id, False)

        async def disconnect():
            await self.presence.go_offline()
            if self.client and self.client.is_connected():
                await self.client.disconnect()

        if self._loop and self._loop.is_running():
            asyncio.run_coroutine_threadsafe(disconnect(), self._loop)

        self._log(None, "СИСТЕМА", "info", f"⛔ {self.config['name']} остановлен")

    def get_uptime(self) -> str:
        if not self.running or not self.start_time:
            return "—"
        delta = datetime.now() - self.start_time
        hours, rem = divmod(int(delta.total_seconds()), 3600)
        minutes, seconds = divmod(rem, 60)
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
