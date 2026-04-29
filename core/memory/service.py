from __future__ import annotations

import json
import re

from db.database import get_memory, normalize_memory_payload, save_memory


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


def merge_memory(existing: dict, new_memory: dict) -> dict:
    left = normalize_memory_payload(existing)
    right = normalize_memory_payload(new_memory)

    merged_facts = dict(left.get("stable_facts", {}))
    merged_facts.update(right.get("stable_facts", {}))

    def merge_lists(first, second, limit: int) -> list[str]:
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
        "recent_context": merge_lists(left.get("recent_context", []), right.get("recent_context", []), 8),
        "emotional_cues": merge_lists(left.get("emotional_cues", []), right.get("emotional_cues", []), 8),
    }


class MemoryService:
    def __init__(self, bot_id: int, anthropic_client):
        self.bot_id = bot_id
        self.claude = anthropic_client

    def get(self, chat_id: int) -> dict:
        return get_memory(self.bot_id, chat_id)

    def extract(self, chat_id: int, dialog_lines: list[str]):
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
            if new_memory.get("stable_facts") or new_memory.get("recent_context") or new_memory.get("emotional_cues"):
                save_memory(self.bot_id, chat_id, merge_memory(existing, new_memory))
        except Exception:
            pass
