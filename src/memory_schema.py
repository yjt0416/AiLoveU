from __future__ import annotations

import json
from typing import Any, Dict, List

try:
    from jsonschema import Draft7Validator
except ImportError:  # pragma: no cover
    Draft7Validator = None


PROFILE_KEYS = (
    "name",
    "identity",
    "occupation",
    "location",
    "goal",
    "communication_style",
)

MEMORY_TYPES = (
    "preference",
    "dislike",
    "habit",
    "fact",
    "expectation",
)

MEMORY_TYPE_LABELS = {
    "preference": "Preference",
    "dislike": "Dislike",
    "habit": "Habit",
    "fact": "Fact",
    "expectation": "Expectation",
}

PROFILE_LABELS = {
    "name": "Name",
    "identity": "Identity",
    "occupation": "Occupation",
    "location": "Location",
    "goal": "Goal",
    "communication_style": "Style",
}

MEMORY_EXTRACTION_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "profile": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                key: {"type": ["string", "null"], "maxLength": 80}
                for key in PROFILE_KEYS
            },
        },
        "memories": {
            "type": "array",
            "maxItems": 8,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "type": {"type": "string", "enum": list(MEMORY_TYPES)},
                    "content": {"type": "string", "minLength": 2, "maxLength": 160},
                    "importance": {"type": "number", "minimum": 0.0, "maximum": 1.0},
                },
                "required": ["type", "content", "importance"],
            },
        },
    },
    "required": ["profile", "memories"],
}


def schema_as_json() -> str:
    return json.dumps(MEMORY_EXTRACTION_SCHEMA, ensure_ascii=False, indent=2)


def validate_and_normalize_payload(payload: Dict[str, Any] | None) -> Dict[str, Any]:
    if payload is None:
        payload = {}
    if not isinstance(payload, dict):
        raise ValueError("Memory extraction payload must be a JSON object.")

    if Draft7Validator is not None:
        Draft7Validator(MEMORY_EXTRACTION_SCHEMA).validate(payload)

    profile = payload.get("profile") or {}
    memories = payload.get("memories") or []

    if not isinstance(profile, dict):
        raise ValueError("Field 'profile' must be an object.")
    if not isinstance(memories, list):
        raise ValueError("Field 'memories' must be a list.")

    normalized_profile: Dict[str, str] = {}
    for key in PROFILE_KEYS:
        value = profile.get(key)
        if value is None:
            continue
        if not isinstance(value, str):
            raise ValueError(f"Profile field '{key}' must be a string or null.")
        cleaned = value.strip()
        if cleaned:
            normalized_profile[key] = cleaned[:80]

    normalized_memories: List[Dict[str, Any]] = []
    for item in memories:
        if not isinstance(item, dict):
            raise ValueError("Each memory item must be an object.")
        memory_type = str(item.get("type", "")).strip()
        content = str(item.get("content", "")).strip()
        importance = item.get("importance", 0.5)

        if memory_type not in MEMORY_TYPES:
            raise ValueError(f"Unsupported memory type: {memory_type}")
        if len(content) < 2:
            continue
        try:
            importance_value = float(importance)
        except (TypeError, ValueError) as exc:
            raise ValueError("Memory importance must be numeric.") from exc

        normalized_memories.append(
            {
                "type": memory_type,
                "content": content[:160],
                "importance": max(0.0, min(1.0, importance_value)),
            }
        )

    deduped: List[Dict[str, Any]] = []
    seen = set()
    for item in normalized_memories:
        token = (item["type"], item["content"].lower())
        if token in seen:
            continue
        seen.add(token)
        deduped.append(item)

    return {
        "profile": normalized_profile,
        "memories": deduped[:8],
    }
