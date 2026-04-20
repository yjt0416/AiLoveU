from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List

from config import Config
from src.character_card import CharacterCard, CharacterCardParser
from src.custom_character_schema import validate_and_normalize_character_payload


@dataclass
class CharacterProfile:
    character_id: str
    name: str
    system_prompt: str
    first_message: str
    avatar_path: str
    source_path: str
    tags: List[str]
    description: str
    personality: str
    scenario: str
    raw_card: Dict[str, Any]
    updated_at: float
    built_in: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class CharacterRegistry:
    def __init__(self, storage_path: str):
        self.storage_path = Path(storage_path)
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        self._data = self._load()
        self._ensure_default_character()

    def list_characters(self) -> List[CharacterProfile]:
        records = [
            CharacterProfile(**item)
            for item in self._data.get("characters", {}).values()
        ]
        records.sort(key=lambda item: item.updated_at, reverse=True)
        return records

    def get_character(self, character_id: str) -> CharacterProfile:
        item = self._data.get("characters", {}).get(character_id)
        if not item:
            raise KeyError(f"Unknown character: {character_id}")
        return CharacterProfile(**item)

    def get_active_character(self) -> CharacterProfile:
        character_id = self._data.get("active_character_id")
        return self.get_character(character_id)

    def set_active_character(self, character_id: str) -> CharacterProfile:
        profile = self.get_character(character_id)
        self._data["active_character_id"] = character_id
        self._save()
        return profile

    def rename_character(self, character_id: str, new_name: str) -> CharacterProfile:
        profile = self.get_character(character_id)
        cleaned_name = (new_name or "").strip()
        if not cleaned_name:
            return profile

        previous_name = profile.name
        profile.name = cleaned_name
        if profile.built_in:
            profile.system_prompt = Config.personality_prompt.format(ai_name=profile.name)
            profile.first_message = f"你好，我是{profile.name}。今天想聊点什么？"
        else:
            profile.system_prompt = profile.system_prompt.replace(previous_name, profile.name)
            profile.first_message = profile.first_message.replace(previous_name, profile.name)
            profile.description = profile.description.replace(previous_name, profile.name)
            profile.personality = profile.personality.replace(previous_name, profile.name)
            profile.scenario = profile.scenario.replace(previous_name, profile.name)
        profile.updated_at = time.time()
        self._data["characters"][character_id] = profile.to_dict()
        self._save()
        return profile

    def import_character_card(self, file_path: str) -> CharacterProfile:
        card = CharacterCardParser.parse_png(file_path)
        return self._store_character_card(card)

    def create_custom_character(self, payload: Dict[str, Any]) -> CharacterProfile:
        normalized = validate_and_normalize_character_payload(payload)
        source_path = f"custom://{time.time_ns()}"
        raw_payload = {
            "spec": "custom-character",
            "spec_version": "1.0",
            "data": {
                "name": normalized["name"],
                "description": normalized["description"],
                "personality": normalized["personality"],
                "scenario": normalized["scenario"],
                "first_mes": normalized["first_message"],
                "mes_example": normalized["message_example"],
                "system_prompt": normalized["system_prompt"],
                "post_history_instructions": normalized["post_history_instructions"],
                "creator_notes": normalized["creator_notes"],
                "tags": normalized["tags"],
            },
        }
        card = CharacterCardParser.from_payload(
            raw_payload,
            source_path=source_path,
            avatar_path="",
        )
        return self._store_character_card(card)

    def _store_character_card(self, card: CharacterCard) -> CharacterProfile:
        base_id = card.card_id
        character_id = base_id
        idx = 2
        while character_id in self._data.get("characters", {}) and (
            self._data["characters"][character_id].get("source_path") != card.source_path
        ):
            character_id = f"{base_id}-{idx}"
            idx += 1

        profile = CharacterProfile(
            character_id=character_id,
            name=card.name,
            system_prompt=CharacterCardParser.build_system_prompt(card),
            first_message=card.first_message,
            avatar_path=card.avatar_path,
            source_path=card.source_path,
            tags=card.tags,
            description=card.description,
            personality=card.personality,
            scenario=card.scenario,
            raw_card=card.raw_payload,
            updated_at=time.time(),
            built_in=False,
        )
        self._data.setdefault("characters", {})[character_id] = profile.to_dict()
        self._data["active_character_id"] = character_id
        self._save()
        return profile

    def _load(self) -> Dict[str, Any]:
        if not self.storage_path.exists():
            return {"active_character_id": None, "characters": {}}
        return json.loads(self.storage_path.read_text(encoding="utf-8"))

    def _save(self) -> None:
        self.storage_path.write_text(
            json.dumps(self._data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _ensure_default_character(self) -> None:
        characters = self._data.setdefault("characters", {})
        default_name = getattr(Config, "AI_NAME", "AiLoveU")
        default_profile = CharacterProfile(
            character_id="default",
            name=default_name,
            system_prompt=Config.personality_prompt.format(ai_name=default_name),
            first_message=f"你好，我是{default_name}。今天想聊点什么？",
            avatar_path="",
            source_path="",
            tags=["default"],
            description="Built-in AI companion.",
            personality="Warm, supportive, and good at listening.",
            scenario="A default AI companion for everyday conversation.",
            raw_card={},
            updated_at=time.time(),
            built_in=True,
        )
        characters["default"] = default_profile.to_dict()

        if not self._data.get("active_character_id"):
            self._data["active_character_id"] = "default"
        self._save()
