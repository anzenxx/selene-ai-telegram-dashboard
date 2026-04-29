from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from .skeleton import WORKSPACE_PROMPT


def format_memory_block(memory: dict) -> str:
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


def build_style_block(style_profile: dict) -> str:
    if not style_profile:
        return ""
    return f"""

--- Стиль этого агента ---
- Тон: {style_profile['tone']}.
- Темп: {style_profile['pacing']}.
- Форма сообщений: {style_profile['message_shape']}.
- Инициативность: {style_profile['initiative']}.
- Чего избегать: {style_profile['forbidden']}."""


def build_runtime_context_block(runtime: dict) -> str:
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


def build_behavior_block() -> str:
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


def build_system_prompt(base_prompt: str, facts: dict, style_profile: dict, runtime: dict) -> str:
    return (
        WORKSPACE_PROMPT
        + "\n\n"
        + base_prompt
        + build_style_block(style_profile)
        + format_memory_block(facts)
        + build_runtime_context_block(runtime)
        + build_behavior_block()
    )


def build_claude_prompt(base_prompt: str, tz: ZoneInfo) -> str:
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
