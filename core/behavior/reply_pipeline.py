from __future__ import annotations

import random
import re
from difflib import SequenceMatcher


MAX_PARTS = 4


def split_parts(text: str) -> list[str]:
    parts = [p.strip() for p in re.split(r"\s*\|\|\|\s*", text) if p.strip()]
    return parts[:MAX_PARTS] if parts else [text]


def remove_emoji(text: str) -> str:
    return "".join(ch for ch in text if ord(ch) < 0x1F300 or ord(ch) > 0x1FAFF)


def normalize_for_similarity(text: str) -> str:
    compact = re.sub(r"\s+", " ", text.lower()).strip()
    compact = re.sub(r"[^\w\sа-яА-ЯёЁ-]", "", compact)
    return compact


def strip_repeated_opener(text: str, repeated_openers: tuple[str, ...]) -> str:
    stripped = text.strip()
    lowered = stripped.lower()
    for opener in repeated_openers:
        if lowered.startswith(opener + " "):
            remainder = stripped[len(opener):].lstrip(" ,.-")
            if len(remainder) >= 10:
                return remainder[0].upper() + remainder[1:] if remainder and remainder[0].islower() else remainder
    return stripped


class ReplyPipeline:
    def __init__(self, repeated_openers: tuple[str, ...], multipart_chances: dict[str, float]):
        self.repeated_openers = repeated_openers
        self.multipart_chances = multipart_chances

    def dedupe_reply_parts(self, runtime: dict, parts: list[str]) -> list[str]:
        recent = [normalize_for_similarity(item) for item in runtime["recent_bot_messages"][-4:]]
        cleaned_parts = []

        for index, part in enumerate(parts):
            compact = strip_repeated_opener(part, self.repeated_openers)
            normalized = normalize_for_similarity(compact)
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
                previous = normalize_for_similarity(cleaned_parts[-1])
                if previous and SequenceMatcher(None, normalized, previous).ratio() >= 0.92:
                    continue

            cleaned_parts.append(compact)
            recent.append(normalized)
            recent = recent[-4:]

        return cleaned_parts or parts[:1]

    def apply_style_profile(self, config: dict, runtime: dict, parts: list[str], intent: str) -> list[str]:
        max_part_len = 210
        split_bias = 1.0

        profile_name = (config.get("name") or "").upper()
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

    def filter_reply_parts(self, config: dict, runtime: dict, raw_reply: str, intent: str) -> list[str]:
        had_explicit_split = "|||" in raw_reply
        normalized_reply = raw_reply.replace("\r\n", "\n").replace("—", "-").replace("–", "-")
        normalized_reply = remove_emoji(normalized_reply)
        raw_parts = []
        for block in normalized_reply.split("\n\n"):
            block = block.strip()
            if not block:
                continue
            raw_parts.extend(split_parts(block))

        parts = [part.replace("\n", " ").strip() for part in raw_parts if part.strip()]
        if not parts:
            return [normalized_reply.strip()]

        allow_split = random.random() < self.multipart_chances.get(runtime["state"], 0.15)
        if intent in {"question", "presence_check"}:
            allow_split = allow_split and len(parts) <= 2
        if intent == "multi_topic":
            allow_split = False
        if sum(len(part) for part in parts) < 90 and len(parts) <= 2:
            allow_split = False
        if had_explicit_split or len(raw_parts) > 1:
            allow_split = True

        if len(parts) == 1:
            sentence_parts = [chunk.strip() for chunk in re.split(r"(?<=[.!?])\s+", parts[0]) if chunk.strip()]
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
        cleaned_parts = self.apply_style_profile(config, runtime, cleaned_parts[:MAX_PARTS], intent)
        cleaned_parts = self.dedupe_reply_parts(runtime, cleaned_parts)
        return cleaned_parts[:MAX_PARTS]
