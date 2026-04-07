from __future__ import annotations

import json
import re
from typing import Any, Dict

from src.api_client import DeepseekAPIClient
from src.memory_schema import schema_as_json, validate_and_normalize_payload


EXTRACTION_SYSTEM_PROMPT = """You extract durable user memory from a single user utterance.

Rules:
- Return JSON only.
- Follow the provided JSON Schema exactly.
- Extract only information that is useful for future personalization.
- Prefer stable facts, preferences, habits, goals, identity, and communication preferences.
- Ignore transient chit-chat unless the user explicitly asks the assistant to remember it.
- Keep memory content short, concrete, and written in the user's original language.
- If nothing should be stored, return {"profile": {}, "memories": []}.
"""


class LLMMemoryExtractor:
    def __init__(self, api_client: DeepseekAPIClient, model: str, temperature: float = 0.1):
        self.api_client = api_client
        self.model = model
        self.temperature = temperature

    def extract(self, user_input: str) -> Dict[str, Any]:
        text = (user_input or "").strip()
        if not text:
            return {"profile": {}, "memories": []}

        messages = [
            {"role": "system", "content": EXTRACTION_SYSTEM_PROMPT},
            {
                "role": "system",
                "content": f"JSON Schema:\n{schema_as_json()}",
            },
            {
                "role": "user",
                "content": f"User utterance:\n{text}\n\nReturn only one JSON object.",
            },
        ]

        try:
            raw = self.api_client.chat(
                messages,
                temperature=self.temperature,
                model=self.model,
            )
            payload = self._parse_json(raw)
            return validate_and_normalize_payload(payload)
        except Exception:
            return {"profile": {}, "memories": []}

    def _parse_json(self, raw_text: str) -> Dict[str, Any]:
        raw_text = (raw_text or "").strip()
        if not raw_text:
            return {"profile": {}, "memories": []}

        fenced = re.search(r"```(?:json)?\s*(\{.*\})\s*```", raw_text, re.DOTALL)
        if fenced:
            raw_text = fenced.group(1)
        else:
            start = raw_text.find("{")
            end = raw_text.rfind("}")
            if start != -1 and end != -1 and end > start:
                raw_text = raw_text[start : end + 1]

        return json.loads(raw_text)
