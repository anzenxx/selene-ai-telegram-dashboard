"""
userbot.py — runtime для Telegram-юзербота
"""

import asyncio
import json
import os
import random
import re
import threading
from datetime import datetime
from difflib import SequenceMatcher
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from telethon import TelegramClient, events
from telethon.tl.functions.account import UpdateStatusRequest
import anthropic

from core.prompt_defaults import AGENT_STYLE_PROFILES, WORKSPACE_PROMPT
from db.database import add_log, get_memory, get_last_seen, normalize_memory_payload, save_memory, set_bot_active, update_last_seen

# ── Константы ─────────────────────────────────────────────────────────────────

MAX_PARTS = 4
TYPO_CHANCE = 0.07
TYPO_FIX_CHANCE = 0.35
SURPRISE_CHANCE = 0.04
MAX_HISTORY_MESSAGES = 24
MAX_RECENT_MESSAGES = 8

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
    "ack": [
        "ахах, поняла",
        "засчитано",
        "намек считан",
        "ладно, принято",
    ],
    "tease": [
        "вот это ты выразительно",
        "сурово вообще",
        "ну все, меня оценили",
        "жесткий стикер, если честно",
    ],
    "soft": [
        "ладно, принимается",
        "хорошо, убедил",
        "я поняла посыл",
        "мягко, но колко",
    ],
    "bounce": [
        "ахах, ладно",
        "это было в тему",
        "я оценила",
        "умеешь разговаривать стикерами",
    ],
}

GROUP_MICRO_PAUSE_SEC = 8
GROUP_SHORT_PAUSE_SEC = 30
GROUP_FORCE_CLOSE_SEC = 55
GROUP_MAX_MESSAGES = 10
GROUP_MAX_CHARS = 1800
NIGHT_START = 0
NIGHT_END = 9
NIGHT_SLOW_MULTIPLIER = 1.35
DEFAULT_TZ = "Europe/Kiev"

CONTINUATION_MARKERS = (
    "и",
    "и еще",
    "и ещё",
    "а потом",
    "потом",
    "короче",
    "в общем",
    "прикинь",
    "и тут",
    "но",
    "но потом",
    "ещё",
    "еще",
)

QUESTION_MARKERS = (
    "?",
    "что думаешь",
    "как думаешь",
    "почему",
    "зачем",
    "как тебе",
    "как считаешь",
    "что скажешь",
    "что делать",
)

EMOTION_MARKERS = (
    "блин",
    "капец",
    "ужас",
    "обидно",
    "страшно",
    "рад",
    "рада",
    "грустно",
    "волнительно",
    "переживаю",
    "смешно",
)

REPEATED_OPENERS = (
    "если честно",
    "честно",
    "ну да",
    "ну",
    "ахах",
    "ха",
    "ладно",
    "в целом",
)

# Промпт для извлечения памяти из диалога
MEMORY_EXTRACT_PROMPT = """Ты — система извлечения памяти о собеседнике.
Из диалога ниже извлеки только полезную новую информацию о собеседнике, не о боте.

Верни только валидный JSON строго такого вида:
{
  "stable_facts": {
    "имя": "...",
    "город": "...",
    "учеба": "...",
    "работа": "...",
    "интересы": ["..."]
  },
  "recent_context": [
    "что сейчас происходит у собеседника",
    "о чем он недавно рассказывал"
  ],
  "emotional_cues": [
    "что его сейчас тревожит или радует",
    "какая тема для него чувствительна"
  ]
}

Правила:
- если данных для раздела нет, верни пустой объект или пустой список
- не дублируй уже известные факты
- не выдумывай
- recent_context и emotional_cues должны быть короткими фразами
- recent_context хранит только актуальный недавний контекст, а не вечные факты

Уже известная память:
{existing}

Диалог:
{dialog}"""


# ── Вспомогательные функции ───────────────────────────────────────────────────

def _get_timezone(tz_name: str) -> ZoneInfo:
    """Возвращает ZoneInfo по имени, дефолт если не найден."""
    try:
        return ZoneInfo(tz_name or DEFAULT_TZ)
    except (ZoneInfoNotFoundError, Exception):
        return ZoneInfo(DEFAULT_TZ)


def _is_night(tz: ZoneInfo) -> bool:
    return NIGHT_START <= datetime.now(tz).hour < NIGHT_END


def _delay_for_length(text_len: int) -> float:
    if text_len <= 40:
        return random.uniform(1.0, 3.5)
    if text_len <= 140:
        return random.uniform(3.0, 8.0)
    if text_len <= 320:
        return random.uniform(8.0, 16.0)
    return random.uniform(14.0, 28.0)


def _inject_typo(text: str) -> str:
    words = text.split()
    if not words:
        return text
    candidates = [i for i, w in enumerate(words) if len(w) > 3 and w.isalpha()]
    if not candidates:
        return text
    idx = random.choice(candidates)
    word = list(words[idx])
    keyboard_neighbors = {
        'а': 'ф', 'б': 'в', 'в': 'б', 'г': 'р', 'д': 'е',
        'е': 'д', 'ж': 'з', 'з': 'ж', 'и': 'у', 'к': 'л',
        'л': 'к', 'м': 'н', 'н': 'м', 'о': 'п', 'п': 'о',
        'р': 'г', 'с': 'а', 'т': 'ы', 'у': 'и', 'ф': 'а',
        'х': 'ъ', 'ц': 'ч', 'ч': 'ц', 'ш': 'щ', 'щ': 'ш',
        'ы': 'т', 'э': 'ю', 'ю': 'э', 'я': 'ч',
    }
    char_idx = random.randint(0, len(word) - 1)
    ch = word[char_idx].lower()
    if ch in keyboard_neighbors:
        word[char_idx] = keyboard_neighbors[ch]
    words[idx] = "".join(word)
    return " ".join(words)


def _split_parts(text: str) -> list[str]:
    parts = [p.strip() for p in re.split(r"\s*\|\|\|\s*", text) if p.strip()]
    return parts[:MAX_PARTS] if parts else [text]


def _remove_emoji(text: str) -> str:
    return "".join(
        ch for ch in text
        if ord(ch) < 0x1F300 or ord(ch) > 0x1FAFF
    )


def _trim_list(values: list, limit: int):
    if len(values) > limit:
        del values[:-limit]


def _seconds_since(moment: datetime | None, now: datetime) -> float | None:
    if moment is None:
        return None
    return max(0.0, (now - moment).total_seconds())


def _contains_any(text: str, markers: tuple[str, ...]) -> bool:
    normalized = text.lower()
    return any(marker in normalized for marker in markers)


def _looks_like_question(text: str) -> bool:
    return _contains_any(text, QUESTION_MARKERS)


def _looks_like_continuation(text: str) -> bool:
    normalized = text.lower().strip()
    if not normalized:
        return False
    if normalized.endswith(("...", "…", ",", "-", "—")):
        return True
    return normalized.startswith(CONTINUATION_MARKERS)


def _looks_like_completion(text: str) -> bool:
    normalized = text.lower().strip()
    if not normalized:
        return False
    if _looks_like_question(normalized):
        return True
    return normalized.endswith(("?", ".", "!", "?!")) or normalized.endswith(("что думаешь", "как считаешь", "и всё", "вот"))


def _format_memory_block(memory: dict) -> str:
    memory = normalize_memory_payload(memory)
    stable = memory.get("stable_facts", {})
    recent = memory.get("recent_context", [])
    emotional = memory.get("emotional_cues", [])
    if not stable and not recent and not emotional:
        return ""

    sections = ["\n\n--- Что ты знаешь об этом собеседнике ---"]
    if stable:
        sections.append(
            "Стабильные факты:\n" +
            "\n".join(f"- {key}: {value}" for key, value in stable.items())
        )
    if recent:
        sections.append(
            "Актуальный недавний контекст:\n" +
            "\n".join(f"- {item}" for item in recent)
        )
    if emotional:
        sections.append(
            "Эмоциональные маркеры:\n" +
            "\n".join(f"- {item}" for item in emotional)
        )
    sections.append("--- Используй эту память естественно и не повторяй ее механически ---")
    return "\n".join(sections)


def _build_behavior_block() -> str:
    return """

--- Правила поведения ---
- Отвечай только на актуальный последний пользовательский turn.
- Если пользователь пишет серией коротких сообщений, воспринимай их как одну мысль.
- Не продолжай собственную прошлую реплику, если пользователь уже сдвинул тему.
- Если во входящем turn несколько тем, ответь на доминирующую текущую тему и максимум кратко затронь близкую вторую.
- Не выдавай длинные монологи без явной причины.
- Разделяй ответ на несколько сообщений только если это звучит естественно для живого чата.
- Не используй длинное тире.
- Не пиши несколько абзацев в одном сообщении.
- Эмодзи почти не используй. По умолчанию лучше вообще без них.
- Не вставляй отдельные сообщения вида "..." или многоточие как самостоятельную реплику.
- Если спрашивают о тебе, отвечай как прикладной ассистент в Telegram, а не как анкета или резюме.
- Не перечисляй выдуманные личные факты, возраст, город и интересы.
- Вместо самопрезентации кратко объясни свою рабочую роль и при необходимости верни вопрос к задаче.
- Пиши как полезный собеседник в мессенджере: ясно, естественно и без ощущения канцелярии.
- Избегай буквального повторения своих недавних формулировок и одинаковых заходов в начале сообщения."""


def _build_style_block(style_profile: dict) -> str:
    if not style_profile:
        return ""
    return f"""

--- Стиль этого агента ---
- Тон: {style_profile['tone']}.
- Темп: {style_profile['pacing']}.
- Форма сообщений: {style_profile['message_shape']}.
- Инициативность: {style_profile['initiative']}.
- Чего избегать: {style_profile['forbidden']}."""


def _build_runtime_context_block(runtime: dict) -> str:
    if not runtime:
        return ""
    return f"""

--- Контекст диалога прямо сейчас ---
- Состояние чата: {runtime.get('state', 'warming_up')}.
- Последний определенный intent: {runtime.get('last_intent', 'small_talk')}.
- Уровень openness: {runtime.get('conversation_openness', 0.35):.2f}.
- Последние реплики собеседника: {runtime.get('recent_user_messages', [])[-3:]}.
- Последние твои реплики: {runtime.get('recent_bot_messages', [])[-3:]}.
- Не повторяй дословно свои последние реплики и не используй один и тот же заход несколько сообщений подряд."""


def _merge_memory(existing: dict, new_memory: dict) -> dict:
    left = normalize_memory_payload(existing)
    right = normalize_memory_payload(new_memory)

    merged_facts = dict(left.get("stable_facts", {}))
    merged_facts.update(right.get("stable_facts", {}))

    def _merge_lists(first, second, limit: int) -> list[str]:
        result = []
        seen = set()
        for item in [*(first or []), *(second or [])]:
            text = str(item).strip()
            if not text:
                continue
            key = text.lower()
            if key in seen:
                continue
            seen.add(key)
            result.append(text)
        return result[-limit:]

    return {
        "stable_facts": merged_facts,
        "recent_context": _merge_lists(left.get("recent_context", []), right.get("recent_context", []), 8),
        "emotional_cues": _merge_lists(left.get("emotional_cues", []), right.get("emotional_cues", []), 8),
    }


def _build_system_prompt(base_prompt: str, facts: dict, style_profile: dict, runtime: dict) -> str:
    return (
        WORKSPACE_PROMPT
        + "\n\n"
        + base_prompt
        + _build_style_block(style_profile)
        + _format_memory_block(facts)
        + _build_runtime_context_block(runtime)
        + _build_behavior_block()
    )


def _build_claude_prompt(base_prompt: str, tz: ZoneInfo) -> str:
    now_local = datetime.now(tz)
    days_ru = [
        "понедельник",
        "вторник",
        "среда",
        "четверг",
        "пятница",
        "суббота",
        "воскресенье",
    ]
    day_name = days_ru[now_local.weekday()]
    time_str = now_local.strftime("%H:%M")
    split_instruction = """

--- Формат ответа ---
Если хочешь написать несколько сообщений подряд, разделяй части символами |||
Максимум 4 части. Каждая часть — короткая и естественная.
Не дроби ответ без необходимости."""
    time_block = (
        "\n\n--- Текущее время ---\n"
        f"Сейчас {time_str}, {day_name}. Учитывай это естественно: ночью можно отвечать чуть короче,"
        " утром — спокойнее, но не проговаривай время без запроса."
    )
    return base_prompt + split_instruction + time_block


def _normalize_for_similarity(text: str) -> str:
    compact = re.sub(r"\s+", " ", text.lower()).strip()
    compact = re.sub(r"[^\w\sа-яА-ЯёЁ-]", "", compact)
    return compact


def _strip_repeated_opener(text: str) -> str:
    stripped = text.strip()
    lowered = stripped.lower()
    for opener in REPEATED_OPENERS:
        if lowered.startswith(opener + " "):
            remainder = stripped[len(opener):].lstrip(" ,.-")
            if len(remainder) >= 10:
                return remainder[0].upper() + remainder[1:] if remainder and remainder[0].islower() else remainder
    return stripped


# ── Основной класс ────────────────────────────────────────────────────────────

class UserBot:
    def __init__(self, bot_config: dict, log_callback=None, state_callback=None):
        self.config = bot_config
        self.bot_id = bot_config["id"]
        self.log_cb = log_callback
        self.state_cb = state_callback
        self.client = None
        self.claude = anthropic.Anthropic(api_key=bot_config["anthropic_key"])
        self.history: dict[int, list[dict]] = {}
        self.running = False
        self._loop = None
        self._thread    = None
        self.start_time = None
        self.tz = _get_timezone(bot_config.get("timezone", DEFAULT_TZ))
        self._debounce_tokens: dict[int, object] = {}
        self._chat_runtime: dict[int, dict] = {}
        self._style_profile = AGENT_STYLE_PROFILES.get((bot_config.get("name") or "").upper(), {})

    # ── Логирование ───────────────────────────────────────────────────────────

    def _log(self, chat_id, chat_name, direction, message, tokens=0):
        add_log(self.bot_id, chat_id, chat_name, direction, message, tokens)
        if self.log_cb:
            self.log_cb(self.bot_id, {
                "timestamp": datetime.now().strftime("%H:%M:%S"),
                "chat_name": chat_name or str(chat_id),
                "direction": direction,
                "message":   message,
                "tokens":    tokens,
            })

    def _emit_state(self, state: str, message: str | None = None):
        if self.state_cb:
            self.state_cb(self.bot_id, state, {"message": message} if message else {})

    def _default_runtime(self) -> dict:
        return {
            "chat_id": None,
            "chat_name": None,
            "state": "new_contact",
            "last_user_message_at": None,
            "last_bot_message_at": None,
            "last_dialogue_at": None,
            "incoming_streak": 0,
            "outgoing_streak": 0,
            "conversation_openness": 0.35,
            "recent_user_messages": [],
            "recent_bot_messages": [],
            "thought_group": None,
            "last_intent": "small_talk",
        }

    def _get_chat_runtime_state(self, chat_id: int) -> dict:
        if chat_id not in self._chat_runtime:
            self._chat_runtime[chat_id] = self._default_runtime()
        return self._chat_runtime[chat_id]

    def _new_thought_group(self, opened_at: datetime, message: str, message_id: int | None = None) -> dict:
        return {
            "messages": [{"text": message, "at": opened_at, "message_id": message_id}],
            "started_at": opened_at,
            "last_message_at": opened_at,
            "confidence_complete": 0.0,
        }

    def _resolve_state_from_gap(self, runtime: dict, now: datetime, *, incoming: bool) -> str:
        gap = _seconds_since(runtime["last_dialogue_at"], now)
        if gap is None and runtime.get("chat_id") is not None:
            gap = _seconds_since(get_last_seen(self.bot_id, runtime["chat_id"]), now)
        if gap is None:
            return "new_contact"
        if gap >= 24 * 3600:
            return "silent" if not incoming else "reopening"
        if gap >= 4 * 3600:
            return "reopening"
        if gap >= 90 * 60:
            return "cooldown"
        if runtime["incoming_streak"] >= 3:
            return "engaged"
        if runtime["outgoing_streak"] >= 1 and gap <= 20 * 60:
            return "engaged"
        if gap <= 2 * 3600:
            return "warming_up"
        return "cooldown"

    def _update_state_on_incoming(self, chat_id: int, chat_name: str, message: str, received_at: datetime, message_id: int | None = None):
        runtime = self._get_chat_runtime_state(chat_id)
        runtime["chat_id"] = chat_id
        runtime["chat_name"] = chat_name

        user_gap = _seconds_since(runtime["last_user_message_at"], received_at)
        if user_gap is None or user_gap > 45 * 60:
            runtime["incoming_streak"] = 1
        else:
            runtime["incoming_streak"] += 1

        runtime["outgoing_streak"] = 0
        runtime["conversation_openness"] = min(1.0, runtime["conversation_openness"] + 0.05)
        runtime["last_user_message_at"] = received_at
        runtime["recent_user_messages"].append(message)
        _trim_list(runtime["recent_user_messages"], MAX_RECENT_MESSAGES)
        runtime["state"] = self._resolve_state_from_gap(runtime, received_at, incoming=True)

        group = runtime["thought_group"]
        if group is None:
            runtime["thought_group"] = self._new_thought_group(received_at, message, message_id)
        else:
            group_gap = _seconds_since(group["last_message_at"], received_at) or 0.0
            should_merge = (
                group_gap <= GROUP_MICRO_PAUSE_SEC
                or (
                    group_gap <= GROUP_SHORT_PAUSE_SEC
                    and (
                        _looks_like_continuation(message)
                        or _looks_like_continuation(group["messages"][-1]["text"])
                        or len(message) < 100
                    )
                )
            )
            if not should_merge and group_gap > GROUP_FORCE_CLOSE_SEC:
                runtime["thought_group"] = self._new_thought_group(received_at, message, message_id)
            else:
                group["messages"].append({"text": message, "at": received_at, "message_id": message_id})
                group["last_message_at"] = received_at
                total_chars = sum(len(item["text"]) for item in group["messages"])
                if _looks_like_completion(message):
                    group["confidence_complete"] = min(1.0, group["confidence_complete"] + 0.35)
                elif _looks_like_continuation(message):
                    group["confidence_complete"] = max(0.0, group["confidence_complete"] - 0.15)
                if len(group["messages"]) >= GROUP_MAX_MESSAGES or total_chars >= GROUP_MAX_CHARS:
                    group["confidence_complete"] = 1.0

        update_last_seen(self.bot_id, chat_id)

    def _update_state_on_outgoing(self, chat_id: int, sent_at: datetime):
        runtime = self._get_chat_runtime_state(chat_id)
        runtime["last_bot_message_at"] = sent_at
        runtime["last_dialogue_at"] = sent_at
        runtime["outgoing_streak"] += 1
        runtime["incoming_streak"] = 0
        runtime["conversation_openness"] = min(1.0, runtime["conversation_openness"] + 0.08)
        runtime["state"] = "engaged" if runtime["outgoing_streak"] >= 1 else "warming_up"
        runtime["thought_group"] = None

    # ── Онлайн-статус ─────────────────────────────────────────────────────────

    async def _go_online(self):
        try:
            await self.client(UpdateStatusRequest(offline=False))
        except Exception:
            pass

    async def _go_offline(self):
        try:
            await self.client(UpdateStatusRequest(offline=True))
        except Exception:
            pass

    async def _go_offline_after(self, delay: float):
        await asyncio.sleep(delay)
        await self._go_offline()

    async def _mark_chat_read(self, chat_id: int):
        try:
            await self.client.send_read_acknowledge(chat_id)
        except Exception:
            pass

    # ── Claude API ────────────────────────────────────────────────────────────

    def _resolve_reply_intent(self, grouped_user_turn: str, thought_group: dict) -> str:
        message_count = len(thought_group["messages"])
        question_count = sum(1 for item in thought_group["messages"] if _looks_like_question(item["text"]))
        total_length = sum(len(item["text"]) for item in thought_group["messages"])

        if question_count >= 2 or (question_count >= 1 and message_count >= 4 and total_length > 240):
            return "multi_topic"
        if question_count >= 1:
            return "question"
        if _contains_any(grouped_user_turn, EMOTION_MARKERS):
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

    def _ask_claude(self, chat_id: int, user_text: str) -> tuple[str, int]:
        memory = get_memory(self.bot_id, chat_id)
        runtime = self._get_chat_runtime_state(chat_id)
        base = _build_system_prompt(self.config["system_prompt"], memory, self._style_profile, runtime)
        prompt = _build_claude_prompt(base, self.tz)

        history = self.history.setdefault(chat_id, [])
        history.append({"role": "user", "content": user_text})
        if len(history) > MAX_HISTORY_MESSAGES:
            history[:] = history[-MAX_HISTORY_MESSAGES:]

        response = self.claude.messages.create(
            model=self.config["claude_model"],
            max_tokens=self.config["max_tokens"],
            system=prompt,
            messages=history,
        )

        reply = response.content[0].text
        tokens = response.usage.input_tokens + response.usage.output_tokens
        history.append({"role": "assistant", "content": reply})
        if len(history) > MAX_HISTORY_MESSAGES:
            history[:] = history[-MAX_HISTORY_MESSAGES:]
        return reply, tokens

    def _extract_memory(self, chat_id: int, dialog_lines: list[str]):
        try:
            existing = get_memory(self.bot_id, chat_id)
            dialog = "\n".join(dialog_lines[-10:])
            prompt = MEMORY_EXTRACT_PROMPT.format(existing=existing, dialog=dialog)
            response = self.claude.messages.create(
                model="claude-haiku-4-5",
                max_tokens=300,
                messages=[{"role": "user", "content": prompt}],
            )
            raw = response.content[0].text.strip()
            raw = re.sub(r"^```[a-z]*\n?", "", raw)
            raw = re.sub(r"\n?```$", "", raw)
            new_memory = normalize_memory_payload(json.loads(raw))
            if (
                new_memory.get("stable_facts")
                or new_memory.get("recent_context")
                or new_memory.get("emotional_cues")
            ):
                merged = _merge_memory(existing, new_memory)
                save_memory(self.bot_id, chat_id, merged)
        except Exception:
            pass

    # ── Имитация печати ───────────────────────────────────────────────────────

    async def _simulate_typing(self, chat_id: int, text: str, state: str, intent: str):
        total_typing = _delay_for_length(len(text))
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

    # ── Отправка с опечатками ─────────────────────────────────────────────────

    async def _send_with_typo(self, chat_id: int, text: str, reply_to: int | None = None):
        has_typo = random.random() < TYPO_CHANCE and len(text) > 14

        if has_typo:
            typo_text = _inject_typo(text)
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

    def _resolve_group_wait(self, chat_id: int) -> float:
        runtime = self._get_chat_runtime_state(chat_id)
        group = runtime["thought_group"]
        if not group or not group["messages"]:
            return 4.0

        last_text = group["messages"][-1]["text"]
        base = {
            "new_contact": 4.8,
            "reopening": 4.3,
            "warming_up": 3.8,
            "engaged": 3.2,
            "cooldown": 4.5,
            "silent": 5.3,
        }.get(runtime["state"], 4.0)

        if _looks_like_continuation(last_text):
            base += 2.2
        if _looks_like_question(last_text):
            base -= 1.0
        if len(group["messages"]) >= 4:
            base += 1.2
        return max(2.5, min(8.5, base + random.uniform(-0.4, 0.7)))

    def _should_close_thought_group(self, chat_id: int, now: datetime) -> bool:
        runtime = self._get_chat_runtime_state(chat_id)
        group = runtime["thought_group"]
        if not group or not group["messages"]:
            return False

        gap = _seconds_since(group["last_message_at"], now) or 0.0
        last_text = group["messages"][-1]["text"]
        total_chars = sum(len(item["text"]) for item in group["messages"])

        if len(group["messages"]) >= GROUP_MAX_MESSAGES or total_chars >= GROUP_MAX_CHARS:
            return True
        if gap >= GROUP_FORCE_CLOSE_SEC:
            return True

        required_pause = 5.5
        if runtime["state"] in {"new_contact", "reopening", "silent"}:
            required_pause = 4.5
        if runtime["state"] == "engaged":
            required_pause = 6.5
        if _looks_like_continuation(last_text):
            required_pause += 3.0
        if _looks_like_question(last_text) or _looks_like_completion(last_text):
            required_pause -= 1.4
        if len(group["messages"]) >= 4:
            required_pause += 1.0
        return gap >= max(2.5, required_pause)

    def _schedule_response_check(self, chat_id: int):
        token = object()
        self._debounce_tokens[chat_id] = token
        delay = self._resolve_group_wait(chat_id)
        loop = self._loop or asyncio.get_event_loop()

        async def _fire(my_token):
            await asyncio.sleep(delay)
            if self._debounce_tokens.get(chat_id) is not my_token:
                return
            if not self._should_close_thought_group(chat_id, datetime.now()):
                self._schedule_response_check(chat_id)
                return
            runtime = self._get_chat_runtime_state(chat_id)
            await self._respond(chat_id, runtime["chat_name"] or str(chat_id))

        loop.create_task(_fire(token))

    def _should_ignore(self, chat_id: int, intent: str) -> bool:
        runtime = self._get_chat_runtime_state(chat_id)
        chance = IGNORE_CHANCES.get(runtime["state"], 0.05)
        if intent in {"question", "emotion"}:
            chance *= 0.25
        if runtime["state"] == "engaged":
            chance *= 0.3
        if runtime["conversation_openness"] > 0.7:
            chance *= 0.6
        if runtime["last_bot_message_at"] is None:
            chance *= 0.6
        return random.random() < chance

    def _resolve_response_delay(self, chat_id: int, intent: str, response_length: int) -> float:
        runtime = self._get_chat_runtime_state(chat_id)
        minimum, maximum = STATE_DELAYS.get(runtime["state"], (45, 120))
        delay = random.uniform(minimum, maximum)

        if intent == "question":
            delay *= 0.65
        elif intent == "emotion":
            delay *= 0.78
        elif intent == "presence_check":
            delay *= 0.58
        elif intent == "story":
            delay *= 1.1
        elif intent == "multi_topic":
            delay *= 0.9

        delay += _delay_for_length(response_length) * 0.5
        if _is_night(self.tz):
            delay *= NIGHT_SLOW_MULTIPLIER
        return max(2.0, delay)

    def _should_reply_to_sticker(self, chat_id: int) -> bool:
        runtime = self._get_chat_runtime_state(chat_id)
        chance = STICKER_REPLY_CHANCES.get(runtime["state"], 0.4)
        last_bot_gap = _seconds_since(runtime["last_bot_message_at"], datetime.now())
        if last_bot_gap is not None and last_bot_gap < 60:
            chance *= 0.5
        if runtime["conversation_openness"] > 0.7:
            chance *= 1.1
        if runtime["state"] == "silent":
            chance *= 0.9
        return random.random() < min(0.95, chance)

    def _resolve_sticker_delay(self, chat_id: int) -> float:
        runtime = self._get_chat_runtime_state(chat_id)
        minimum, maximum = STICKER_DELAYS.get(runtime["state"], (10, 40))
        delay = random.uniform(minimum, maximum)
        if _is_night(self.tz):
            delay *= 1.15
        return max(2.0, delay)

    def _build_sticker_reaction(self, chat_id: int) -> list[str]:
        runtime = self._get_chat_runtime_state(chat_id)
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

    def _dedupe_reply_parts(self, chat_id: int, parts: list[str]) -> list[str]:
        runtime = self._get_chat_runtime_state(chat_id)
        recent = [_normalize_for_similarity(item) for item in runtime["recent_bot_messages"][-4:]]
        cleaned_parts = []

        for index, part in enumerate(parts):
            compact = _strip_repeated_opener(part)
            normalized = _normalize_for_similarity(compact)
            if not normalized:
                continue

            too_similar = any(
                SequenceMatcher(None, normalized, prev).ratio() >= 0.88
                for prev in recent
                if prev
            )
            if too_similar and len(parts) > 1:
                continue

            if index > 0 and cleaned_parts:
                previous = _normalize_for_similarity(cleaned_parts[-1])
                if previous and SequenceMatcher(None, normalized, previous).ratio() >= 0.92:
                    continue

            cleaned_parts.append(compact)
            recent.append(normalized)
            recent = recent[-4:]

        return cleaned_parts or parts[:1]

    def _apply_style_profile(self, chat_id: int, parts: list[str], intent: str) -> list[str]:
        runtime = self._get_chat_runtime_state(chat_id)
        max_part_len = 210
        split_bias = 1.0

        profile_name = (self.config.get("name") or "").upper()
        if profile_name in {"SUPPORT", "RESEARCH"}:
            max_part_len = 180
            split_bias = 0.85
        elif profile_name in {"COMMUNITY", "WRITER"}:
            max_part_len = 220
            split_bias = 1.15
        elif profile_name == "OPS":
            max_part_len = 190
            split_bias = 0.95

        if intent in {"presence_check", "question"}:
            max_part_len = min(max_part_len, 170)
        if runtime["state"] == "engaged":
            split_bias *= 1.1

        styled_parts = []
        for part in parts:
            compact = re.sub(r"\s{2,}", " ", part).strip()
            if len(compact) > max_part_len and random.random() < split_bias:
                split_candidate = re.split(r"(?<=[.!?])\s+", compact, maxsplit=1)
                if len(split_candidate) == 2 and all(piece.strip() for piece in split_candidate):
                    styled_parts.extend(piece.strip() for piece in split_candidate)
                    continue
            styled_parts.append(compact)

        return styled_parts[:MAX_PARTS]

    def _filter_reply_parts(self, raw_reply: str, chat_id: int, intent: str) -> list[str]:
        runtime = self._get_chat_runtime_state(chat_id)
        had_explicit_split = "|||" in raw_reply
        normalized_reply = raw_reply.replace("\r\n", "\n").replace("—", "-").replace("–", "-")
        normalized_reply = _remove_emoji(normalized_reply)
        raw_parts = []
        for block in normalized_reply.split("\n\n"):
            block = block.strip()
            if not block:
                continue
            raw_parts.extend(_split_parts(block))

        parts = [part.replace("\n", " ").strip() for part in raw_parts if part.strip()]
        if not parts:
            return [normalized_reply.strip()]

        allow_split = random.random() < MULTIPART_CHANCES.get(runtime["state"], 0.15)
        if intent in {"question", "presence_check"}:
            allow_split = allow_split and len(parts) <= 2
        if intent == "multi_topic":
            allow_split = False
        if sum(len(part) for part in parts) < 90 and len(parts) <= 2:
            allow_split = False
        if had_explicit_split or len(raw_parts) > 1:
            allow_split = True

        if len(parts) == 1:
            sentence_parts = [
                chunk.strip()
                for chunk in re.split(r"(?<=[.!?])\s+", parts[0])
                if chunk.strip()
            ]
            if len(sentence_parts) >= 2 and sum(len(chunk) for chunk in sentence_parts[:2]) < 240:
                parts = sentence_parts
                allow_split = True

        if not allow_split:
            merged = " ".join(part.strip() for part in parts if part.strip())
            merged = re.sub(r"\s{2,}", " ", merged).strip(" -")
            return [merged]

        cleaned_parts = []
        for part in parts[:MAX_PARTS]:
            compact = re.sub(r"\s{2,}", " ", part).strip(" -")
            if compact:
                cleaned_parts.append(compact)
        cleaned_parts = self._apply_style_profile(chat_id, cleaned_parts[:MAX_PARTS], intent)
        cleaned_parts = self._dedupe_reply_parts(chat_id, cleaned_parts)
        return cleaned_parts[:MAX_PARTS]

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

        if intent == "multi_topic":
            question_targets = [item for item in valid_targets if _looks_like_question(item["text"])]
            if question_targets:
                return question_targets[-1]["message_id"]
        if intent == "question":
            question_targets = [item for item in valid_targets if _looks_like_question(item["text"])]
            if question_targets:
                return question_targets[-1]["message_id"]
        return valid_targets[-1]["message_id"]

    # ── Основная логика ответа ────────────────────────────────────────────────

    async def _respond(self, chat_id: int, chat_name: str):
        runtime = self._get_chat_runtime_state(chat_id)
        thought_group = runtime["thought_group"]
        if not thought_group or not thought_group["messages"]:
            return

        intent = self._resolve_reply_intent("\n".join(item["text"] for item in thought_group["messages"]), thought_group)
        runtime["last_intent"] = intent
        user_text = self._build_grouped_user_turn(thought_group, intent, runtime["state"])

        self._log(chat_id, chat_name, "in", user_text)
        if self._should_ignore(chat_id, intent):
            self._log(chat_id, chat_name, "info", f"🙈 Intentionally holding back in state {runtime['state']}")
            runtime["thought_group"] = None
            runtime["last_dialogue_at"] = datetime.now()
            await self._go_offline()
            return

        await self._go_offline()
        delay = self._resolve_response_delay(chat_id, intent, sum(len(item["text"]) for item in thought_group["messages"]))
        self._log(chat_id, chat_name, "info", f"⏳ {runtime['state']} / {intent}, ждём {int(delay)} сек")
        await asyncio.sleep(delay)

        if not self.running:
            return
        if runtime["thought_group"] is not thought_group:
            return
        try:
            reply, tokens = await asyncio.get_event_loop().run_in_executor(None, self._ask_claude, chat_id, user_text)
        except Exception as exc:
            self._log(chat_id, chat_name, "out", f"[Ошибка Claude: {exc}]")
            return

        parts = self._filter_reply_parts(reply, chat_id, intent)
        reply_target = self._select_reply_target(thought_group, intent, runtime["state"])
        await self._go_online()
        await self._mark_chat_read(chat_id)
        await asyncio.sleep(random.uniform(0.6, 1.8))

        if runtime["state"] not in {"engaged", "warming_up"} and random.random() < 0.05:
            filler = random.choice(["хм", "мм"])
            await self._send_with_typo(chat_id, filler)
            await asyncio.sleep(random.uniform(0.8, 1.8))

        for i, part in enumerate(parts):
            if random.random() < SURPRISE_CHANCE:
                await asyncio.sleep(random.uniform(0.2, 1.5))

            await self._simulate_typing(chat_id, part, runtime["state"], intent)
            await self._send_with_typo(chat_id, part, reply_to=reply_target if i == 0 else None)
            self._log(chat_id, chat_name, "out", part, tokens if i == 0 else 0)
            tokens = 0
            runtime["recent_bot_messages"].append(part)
            _trim_list(runtime["recent_bot_messages"], MAX_RECENT_MESSAGES)

            if i < len(parts) - 1:
                await asyncio.sleep(random.uniform(0.8, 3.5))

        sent_at = datetime.now()
        self._update_state_on_outgoing(chat_id, sent_at)
        asyncio.ensure_future(self._go_offline_after(random.uniform(25, 75)))

        dialog_lines = [
            "собеседник: " + " | ".join(item["text"] for item in thought_group["messages"]),
            "бот: " + " ".join(parts),
        ]
        asyncio.ensure_future(
            asyncio.get_event_loop().run_in_executor(None, self._extract_memory, chat_id, dialog_lines)
        )

    async def _handle_sticker_turn(self, chat_id: int, chat_name: str):
        runtime = self._get_chat_runtime_state(chat_id)
        received_at = datetime.now()
        runtime["chat_id"] = chat_id
        runtime["chat_name"] = chat_name
        runtime["incoming_streak"] = runtime.get("incoming_streak", 0) + 1
        runtime["outgoing_streak"] = 0
        runtime["conversation_openness"] = min(1.0, runtime["conversation_openness"] + 0.03)
        runtime["last_user_message_at"] = received_at
        runtime["last_intent"] = "sticker"
        runtime["state"] = self._resolve_state_from_gap(runtime, received_at, incoming=True)
        update_last_seen(self.bot_id, chat_id)

        if not self._should_reply_to_sticker(chat_id):
            return

        delay = self._resolve_sticker_delay(chat_id)
        self._log(chat_id, chat_name, "info", f"🪄 sticker / {runtime['state']}, ждём {int(delay)} сек")
        await asyncio.sleep(delay)

        if not self.running:
            return

        await self._go_online()
        await self._mark_chat_read(chat_id)
        await asyncio.sleep(random.uniform(0.4, 1.2))

        parts = self._build_sticker_reaction(chat_id)
        for index, part in enumerate(parts):
            await self._simulate_typing(chat_id, part, runtime["state"], "presence_check")
            await self._send_with_typo(chat_id, part)
            self._log(chat_id, chat_name, "out", part, 0)
            runtime["recent_bot_messages"].append(part)
            _trim_list(runtime["recent_bot_messages"], MAX_RECENT_MESSAGES)
            if index < len(parts) - 1:
                await asyncio.sleep(random.uniform(0.6, 1.4))

        self._update_state_on_outgoing(chat_id, datetime.now())
        asyncio.ensure_future(self._go_offline_after(random.uniform(20, 55)))

    # ── Debounce ──────────────────────────────────────────────────────────────

    async def _debounce_handler(self, chat_id: int, chat_name: str, message: str, message_id: int | None = None):
        received_at = datetime.now()
        self._update_state_on_incoming(chat_id, chat_name, message, received_at, message_id)
        self._schedule_response_check(chat_id)

    # ── Telegram handlers ─────────────────────────────────────────────────────

    async def _setup_handlers(self):
        raw_prefix = self.config["trigger_prefix"].strip()
        no_prefix  = raw_prefix == ""

        if no_prefix:
            @self.client.on(events.NewMessage(incoming=True,
                                               func=lambda e: e.is_private))
            async def on_message(event):
                user_text = (event.raw_text or "").strip()
                chat      = await event.get_chat()
                chat_name = (getattr(chat, "title", None)
                             or getattr(chat, "first_name", None)
                             or str(event.chat_id))
                if getattr(event, "sticker", False) and not user_text:
                    await self._handle_sticker_turn(event.chat_id, chat_name)
                    return
                if not user_text:
                    return
                await self._debounce_handler(event.chat_id, chat_name, user_text, event.id)
        else:
            prefix  = re.escape(raw_prefix)
            pattern = re.compile(rf"^{prefix}\s+(.*)", re.S | re.DOTALL)

            @self.client.on(events.NewMessage(pattern=pattern))
            async def on_message(event):
                if not event.out:
                    return
                user_text = event.pattern_match.group(1).strip()
                if not user_text:
                    return
                chat      = await event.get_chat()
                chat_name = (getattr(chat, "title", None)
                             or getattr(chat, "first_name", None)
                             or str(event.chat_id))
                await event.edit("⏳")
                try:
                    reply, tokens = await asyncio.get_event_loop().run_in_executor(
                        None, self._ask_claude, event.chat_id, user_text
                    )
                    parts = self._filter_reply_parts(reply, event.chat_id, "question")
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
                except Exception as e:
                    await event.edit(f"[Ошибка: {e}]")

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    async def _run(self):
        cfg = self.config
        base_dir     = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        sessions_dir = os.path.join(base_dir, "sessions")
        os.makedirs(sessions_dir, exist_ok=True)
        session_file = os.path.join(sessions_dir, f"bot_{self.bot_id}")

        self.client = TelegramClient(
            session_file,
            int(cfg["api_id"]),
            cfg["api_hash"],
        )

        session_path = session_file + ".session"
        if not os.path.exists(session_path) or os.path.getsize(session_path) == 0:
            raise RuntimeError(
                f"Сессия не найдена: {session_path}\n"
                "Сначала запустите  python create_session.py  и войдите в аккаунт."
            )

        await self.client.connect()
        if not await self.client.is_user_authorized():
            raise RuntimeError(
                "Сессия есть, но авторизация не прошла.\n"
                "Удалите файл сессии и запустите  python create_session.py  заново."
            )

        await self._setup_handlers()
        self.running    = True
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

        def _thread_target():
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

        self._thread = threading.Thread(target=_thread_target, daemon=True)
        self._thread.start()

    def stop(self):
        if not self.running:
            return
        self.running = False
        set_bot_active(self.bot_id, False)

        async def _disconnect():
            await self._go_offline()
            if self.client and self.client.is_connected():
                await self.client.disconnect()

        if self._loop and self._loop.is_running():
            asyncio.run_coroutine_threadsafe(_disconnect(), self._loop)

        self._log(None, "СИСТЕМА", "info", f"⛔ {self.config['name']} остановлен")

    def get_uptime(self) -> str:
        if not self.running or not self.start_time:
            return "—"
        delta = datetime.now() - self.start_time
        h, rem = divmod(int(delta.total_seconds()), 3600)
        m, s   = divmod(rem, 60)
        return f"{h:02d}:{m:02d}:{s:02d}"
