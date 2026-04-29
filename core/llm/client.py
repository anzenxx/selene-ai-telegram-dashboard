from __future__ import annotations

import anthropic

from core.prompts import AGENT_STYLE_PROFILES, build_claude_prompt, build_system_prompt


class ClaudeConversationService:
    def __init__(self, bot_config: dict, tz):
        self.config = bot_config
        self.tz = tz
        self.client = anthropic.Anthropic(api_key=bot_config["anthropic_key"])
        self.history: dict[int, list[dict]] = {}
        self.style_profile = AGENT_STYLE_PROFILES.get((bot_config.get("name") or "").upper(), {})

    def ask(self, chat_id: int, user_text: str, runtime: dict, memory: dict, max_history_messages: int) -> tuple[str, int]:
        base = build_system_prompt(self.config["system_prompt"], memory, self.style_profile, runtime)
        prompt = build_claude_prompt(base, self.tz)

        history = self.history.setdefault(chat_id, [])
        history.append({"role": "user", "content": user_text})
        if len(history) > max_history_messages:
            history[:] = history[-max_history_messages:]

        response = self.client.messages.create(
            model=self.config["claude_model"],
            max_tokens=self.config["max_tokens"],
            system=prompt,
            messages=history,
        )

        reply = response.content[0].text
        tokens = response.usage.input_tokens + response.usage.output_tokens
        history.append({"role": "assistant", "content": reply})
        if len(history) > max_history_messages:
            history[:] = history[-max_history_messages:]
        return reply, tokens
