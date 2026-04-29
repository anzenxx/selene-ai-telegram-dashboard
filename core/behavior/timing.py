from __future__ import annotations

import random
from datetime import datetime

from core.runtime.chat_runtime import seconds_since


class TimingPolicy:
    def __init__(
        self,
        state_delays: dict[str, tuple[int, int]],
        ignore_chances: dict[str, float],
        sticker_reply_chances: dict[str, float],
        sticker_delays: dict[str, tuple[int, int]],
        night_slow_multiplier: float,
        is_night,
        delay_for_length,
    ):
        self.state_delays = state_delays
        self.ignore_chances = ignore_chances
        self.sticker_reply_chances = sticker_reply_chances
        self.sticker_delays = sticker_delays
        self.night_slow_multiplier = night_slow_multiplier
        self.is_night = is_night
        self.delay_for_length = delay_for_length

    def should_ignore(self, runtime: dict, intent: str) -> bool:
        chance = self.ignore_chances.get(runtime["state"], 0.05)
        if intent in {"question", "emotion"}:
            chance *= 0.25
        if runtime["state"] == "engaged":
            chance *= 0.3
        if runtime["conversation_openness"] > 0.7:
            chance *= 0.6
        if runtime["last_bot_message_at"] is None:
            chance *= 0.6
        return random.random() < chance

    def resolve_response_delay(self, runtime: dict, tz, intent: str, response_length: int) -> float:
        minimum, maximum = self.state_delays.get(runtime["state"], (45, 120))
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

        delay += self.delay_for_length(response_length) * 0.5
        if self.is_night(tz):
            delay *= self.night_slow_multiplier
        return max(2.0, delay)

    def should_reply_to_sticker(self, runtime: dict) -> bool:
        chance = self.sticker_reply_chances.get(runtime["state"], 0.4)
        last_bot_gap = seconds_since(runtime["last_bot_message_at"], datetime.now())
        if last_bot_gap is not None and last_bot_gap < 60:
            chance *= 0.5
        if runtime["conversation_openness"] > 0.7:
            chance *= 1.1
        if runtime["state"] == "silent":
            chance *= 0.9
        return random.random() < min(0.95, chance)

    def resolve_sticker_delay(self, runtime: dict, tz) -> float:
        minimum, maximum = self.sticker_delays.get(runtime["state"], (10, 40))
        delay = random.uniform(minimum, maximum)
        if self.is_night(tz):
            delay *= 1.15
        return max(2.0, delay)
