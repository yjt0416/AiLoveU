from __future__ import annotations

import json
from typing import Any, Dict, List

try:
    from jsonschema import Draft7Validator
except ImportError:  # pragma: no cover
    Draft7Validator = None


CHARACTER_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "name": {"type": "string", "minLength": 1, "maxLength": 60},
        "description": {"type": "string", "maxLength": 600},
        "personality": {"type": "string", "maxLength": 600},
        "scenario": {"type": "string", "maxLength": 600},
        "first_message": {"type": "string", "maxLength": 300},
        "message_example": {"type": "string", "maxLength": 600},
        "system_prompt": {"type": "string", "maxLength": 1200},
        "post_history_instructions": {"type": "string", "maxLength": 400},
        "creator_notes": {"type": "string", "maxLength": 400},
        "tags": {
            "type": "array",
            "maxItems": 8,
            "items": {"type": "string", "minLength": 1, "maxLength": 24},
        },
    },
    "required": [
        "name",
        "description",
        "personality",
        "scenario",
        "first_message",
        "message_example",
        "system_prompt",
        "post_history_instructions",
        "creator_notes",
        "tags",
    ],
}


def schema_as_json() -> str:
    return json.dumps(CHARACTER_SCHEMA, ensure_ascii=False, indent=2)


def validate_and_normalize_character_payload(
    payload: Dict[str, Any] | None,
    defaults: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    if payload is None:
        payload = {}
    if defaults is None:
        defaults = {}
    if not isinstance(payload, dict):
        raise ValueError("Character payload must be a JSON object.")

    merged = {**defaults, **payload}

    name = _normalize_text(merged.get("name"), 60) or "Custom Companion"
    description = _normalize_text(merged.get("description"), 600)
    personality = _normalize_text(merged.get("personality"), 600)
    scenario = _normalize_text(merged.get("scenario"), 600)
    first_message = _normalize_text(merged.get("first_message"), 300)
    message_example = _normalize_text(merged.get("message_example"), 600)
    system_prompt = _normalize_text(merged.get("system_prompt"), 1200)
    post_history_instructions = _normalize_text(merged.get("post_history_instructions"), 400)
    creator_notes = _normalize_text(merged.get("creator_notes"), 400)
    tags = _normalize_tags(merged.get("tags"))

    if not description:
        description = creator_notes or personality or "A custom companion character created by the user."
    if not personality:
        personality = creator_notes or description
    if not scenario:
        scenario = "This character chats with the user as a long-term AI companion."
    if not first_message:
        first_message = f"你好，我是{name}。很高兴认识你，你想聊些什么？"
    if not tags:
        tags = ["custom"]

    normalized = {
        "name": name,
        "description": description,
        "personality": personality,
        "scenario": scenario,
        "first_message": first_message,
        "message_example": message_example,
        "system_prompt": system_prompt,
        "post_history_instructions": post_history_instructions,
        "creator_notes": creator_notes,
        "tags": tags,
    }

    if Draft7Validator is not None:
        Draft7Validator(CHARACTER_SCHEMA).validate(normalized)

    return normalized


def _normalize_text(value: Any, max_length: int) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    return text[:max_length]


def _normalize_tags(value: Any) -> List[str]:
    raw_tags: List[str]
    if value is None:
        raw_tags = []
    elif isinstance(value, list):
        raw_tags = [str(item) for item in value]
    else:
        raw_tags = [item.strip() for item in str(value).replace("，", ",").split(",")]

    normalized: List[str] = []
    seen = set()
    for tag in raw_tags:
        cleaned = str(tag).strip().lower()
        if not cleaned:
            continue
        cleaned = cleaned[:24]
        if cleaned in seen:
            continue
        seen.add(cleaned)
        normalized.append(cleaned)
        if len(normalized) >= 8:
            break
    return normalized
