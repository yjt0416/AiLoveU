from __future__ import annotations

import json
import re
from typing import Any, Dict, List

from src.api_client import DeepseekAPIClient
from src.custom_character_schema import (
    schema_as_json,
    validate_and_normalize_character_payload,
)


CUSTOM_CHARACTER_SYSTEM_PROMPT = """You convert free-form role design notes into a structured AI companion character profile.

Rules:
- Return JSON only.
- Follow the provided JSON Schema exactly.
- Create a coherent character for conversational roleplay / AI companion use.
- Preserve the user's requested role, relationship dynamic, tone, scenario, and opening style.
- Keep each field concise but vivid.
- If some fields are missing, infer sensible defaults instead of leaving them blank.
- Keep tags short lowercase keywords.
"""


class CustomCharacterBuilder:
    def __init__(self, api_client: DeepseekAPIClient, model: str, temperature: float = 0.2):
        self.api_client = api_client
        self.model = model
        self.temperature = temperature

    def build(
        self,
        user_notes: str,
        name_hint: str = "",
        tags_hint: str = "",
    ) -> Dict[str, Any]:
        notes = (user_notes or "").strip()
        if not notes:
            raise ValueError("Character notes cannot be empty.")

        fallback = self._fallback_payload(notes, name_hint=name_hint, tags_hint=tags_hint)
        messages = [
            {"role": "system", "content": CUSTOM_CHARACTER_SYSTEM_PROMPT},
            {"role": "system", "content": f"JSON Schema:\n{schema_as_json()}"},
            {
                "role": "user",
                "content": (
                    "Create one character JSON object from these notes.\n\n"
                    f"Name hint: {name_hint or '(none)'}\n"
                    f"Tags hint: {tags_hint or '(none)'}\n"
                    f"User notes:\n{notes}\n\n"
                    "Return JSON only."
                ),
            },
        ]

        try:
            raw = self.api_client.chat(
                messages,
                temperature=self.temperature,
                model=self.model,
            )
            payload = self._parse_json(raw)
            return validate_and_normalize_character_payload(payload, defaults=fallback)
        except Exception:
            return fallback

    def _parse_json(self, raw_text: str) -> Dict[str, Any]:
        raw_text = (raw_text or "").strip()
        if not raw_text:
            raise ValueError("Empty character builder response.")

        fenced = re.search(r"```(?:json)?\s*(\{.*\})\s*```", raw_text, re.DOTALL)
        if fenced:
            raw_text = fenced.group(1)
        else:
            start = raw_text.find("{")
            end = raw_text.rfind("}")
            if start != -1 and end != -1 and end > start:
                raw_text = raw_text[start : end + 1]

        return json.loads(raw_text)

    def _fallback_payload(self, notes: str, name_hint: str = "", tags_hint: str = "") -> Dict[str, Any]:
        clean_notes = " ".join(notes.split())
        inferred_name = (name_hint or "").strip() or self._guess_name(clean_notes) or "Custom Companion"
        tags = self._parse_tags(tags_hint)
        if not tags:
            tags = ["custom"]

        summary = clean_notes[:400]
        payload = {
            "name": inferred_name,
            "description": summary or "A custom AI companion character.",
            "personality": summary or "Warm, responsive, and in-character.",
            "scenario": "This character chats with the user as a personalized AI companion.",
            "first_message": f"你好，我是{inferred_name}。很高兴认识你，你想聊些什么？",
            "message_example": "",
            "system_prompt": "",
            "post_history_instructions": "",
            "creator_notes": summary,
            "tags": tags,
        }
        return validate_and_normalize_character_payload(payload)

    def _guess_name(self, notes: str) -> str:
        patterns = (
            r"(?:名字叫|叫做|名叫|角色名是)\s*([A-Za-z0-9_\-\u4e00-\u9fff]{2,30})",
            r"(?:name is|named)\s*[:：]?\s*([A-Za-z0-9_\-\u4e00-\u9fff]{2,30})",
        )
        for pattern in patterns:
            match = re.search(pattern, notes, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        return ""

    def _parse_tags(self, value: str) -> List[str]:
        if not value:
            return []
        tags: List[str] = []
        seen = set()
        for item in value.replace("，", ",").split(","):
            cleaned = item.strip().lower()
            if not cleaned or cleaned in seen:
                continue
            seen.add(cleaned)
            tags.append(cleaned[:24])
            if len(tags) >= 8:
                break
        return tags
