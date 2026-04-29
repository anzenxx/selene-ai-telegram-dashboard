from __future__ import annotations

from datetime import datetime

from db.database import get_last_seen, update_last_seen


GROUP_MICRO_PAUSE_SEC = 8
GROUP_SHORT_PAUSE_SEC = 30
GROUP_FORCE_CLOSE_SEC = 55
GROUP_MAX_MESSAGES = 10
GROUP_MAX_CHARS = 1800
MAX_RECENT_MESSAGES = 8


def trim_list(values: list, limit: int):
    if len(values) > limit:
        del values[:-limit]


def seconds_since(moment: datetime | None, now: datetime) -> float | None:
    if moment is None:
        return None
    return max(0.0, (now - moment).total_seconds())


class ChatRuntimeStore:
    def __init__(self, bot_id: int, looks_like_continuation, looks_like_completion, looks_like_question):
        self.bot_id = bot_id
        self._looks_like_continuation = looks_like_continuation
        self._looks_like_completion = looks_like_completion
        self._looks_like_question = looks_like_question
        self._chat_runtime: dict[int, dict] = {}

    def default_runtime(self) -> dict:
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

    def get(self, chat_id: int) -> dict:
        if chat_id not in self._chat_runtime:
            self._chat_runtime[chat_id] = self.default_runtime()
        return self._chat_runtime[chat_id]

    def new_thought_group(self, opened_at: datetime, message: str, message_id: int | None = None) -> dict:
        return {
            "messages": [{"text": message, "at": opened_at, "message_id": message_id}],
            "started_at": opened_at,
            "last_message_at": opened_at,
            "confidence_complete": 0.0,
        }

    def resolve_state_from_gap(self, runtime: dict, now: datetime, *, incoming: bool) -> str:
        gap = seconds_since(runtime["last_dialogue_at"], now)
        if gap is None and runtime.get("chat_id") is not None:
            gap = seconds_since(get_last_seen(self.bot_id, runtime["chat_id"]), now)
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

    def update_on_incoming(self, chat_id: int, chat_name: str, message: str, received_at: datetime, message_id: int | None = None):
        runtime = self.get(chat_id)
        runtime["chat_id"] = chat_id
        runtime["chat_name"] = chat_name

        user_gap = seconds_since(runtime["last_user_message_at"], received_at)
        if user_gap is None or user_gap > 45 * 60:
            runtime["incoming_streak"] = 1
        else:
            runtime["incoming_streak"] += 1

        runtime["outgoing_streak"] = 0
        runtime["conversation_openness"] = min(1.0, runtime["conversation_openness"] + 0.05)
        runtime["last_user_message_at"] = received_at
        runtime["recent_user_messages"].append(message)
        trim_list(runtime["recent_user_messages"], MAX_RECENT_MESSAGES)
        runtime["state"] = self.resolve_state_from_gap(runtime, received_at, incoming=True)

        group = runtime["thought_group"]
        if group is None:
            runtime["thought_group"] = self.new_thought_group(received_at, message, message_id)
        else:
            group_gap = seconds_since(group["last_message_at"], received_at) or 0.0
            should_merge = (
                group_gap <= GROUP_MICRO_PAUSE_SEC
                or (
                    group_gap <= GROUP_SHORT_PAUSE_SEC
                    and (
                        self._looks_like_continuation(message)
                        or self._looks_like_continuation(group["messages"][-1]["text"])
                        or len(message) < 100
                    )
                )
            )
            if not should_merge and group_gap > GROUP_FORCE_CLOSE_SEC:
                runtime["thought_group"] = self.new_thought_group(received_at, message, message_id)
            else:
                group["messages"].append({"text": message, "at": received_at, "message_id": message_id})
                group["last_message_at"] = received_at
                total_chars = sum(len(item["text"]) for item in group["messages"])
                if self._looks_like_completion(message):
                    group["confidence_complete"] = min(1.0, group["confidence_complete"] + 0.35)
                elif self._looks_like_continuation(message):
                    group["confidence_complete"] = max(0.0, group["confidence_complete"] - 0.15)
                if len(group["messages"]) >= GROUP_MAX_MESSAGES or total_chars >= GROUP_MAX_CHARS:
                    group["confidence_complete"] = 1.0

        update_last_seen(self.bot_id, chat_id)

    def update_on_outgoing(self, chat_id: int, sent_at: datetime):
        runtime = self.get(chat_id)
        runtime["last_bot_message_at"] = sent_at
        runtime["last_dialogue_at"] = sent_at
        runtime["outgoing_streak"] += 1
        runtime["incoming_streak"] = 0
        runtime["conversation_openness"] = min(1.0, runtime["conversation_openness"] + 0.08)
        runtime["state"] = "engaged" if runtime["outgoing_streak"] >= 1 else "warming_up"
        runtime["thought_group"] = None

    def resolve_group_wait(self, chat_id: int) -> float:
        runtime = self.get(chat_id)
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

        if self._looks_like_continuation(last_text):
            base += 2.2
        if self._looks_like_question(last_text):
            base -= 1.0
        if len(group["messages"]) >= 4:
            base += 1.2
        import random
        return max(2.5, min(8.5, base + random.uniform(-0.4, 0.7)))

    def should_close_thought_group(self, chat_id: int, now: datetime) -> bool:
        runtime = self.get(chat_id)
        group = runtime["thought_group"]
        if not group or not group["messages"]:
            return False

        gap = seconds_since(group["last_message_at"], now) or 0.0
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
        if self._looks_like_continuation(last_text):
            required_pause += 3.0
        if self._looks_like_question(last_text) or self._looks_like_completion(last_text):
            required_pause -= 1.4
        if len(group["messages"]) >= 4:
            required_pause += 1.0
        return gap >= max(2.5, required_pause)
