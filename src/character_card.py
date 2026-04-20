from __future__ import annotations

import base64
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List

from PIL import Image


def _clean_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _replace_placeholders(text: str, char_name: str, user_name: str = "user") -> str:
    return (
        text.replace("{{char}}", char_name)
        .replace("{{user}}", user_name)
        .replace("<START>", "")
        .strip()
    )


@dataclass
class CharacterCard:
    card_id: str
    name: str
    description: str
    personality: str
    scenario: str
    first_message: str
    message_example: str
    system_prompt: str
    post_history_instructions: str
    creator_notes: str
    tags: List[str]
    source_path: str
    avatar_path: str
    raw_payload: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class CharacterCardParser:
    @staticmethod
    def parse_png(file_path: str) -> CharacterCard:
        path = Path(file_path).resolve()
        with Image.open(path) as image:
            metadata: Dict[str, Any] = {}
            metadata.update(getattr(image, "info", {}) or {})
            metadata.update(getattr(image, "text", {}) or {})

        chara_payload = metadata.get("chara")
        if not chara_payload:
            raise ValueError("PNG metadata does not contain a `chara` field.")

        try:
            decoded = base64.b64decode(chara_payload).decode("utf-8")
            payload = json.loads(decoded)
        except Exception as exc:
            raise ValueError("Failed to decode `chara` metadata from the PNG card.") from exc

        return CharacterCardParser.from_payload(
            payload,
            source_path=str(path),
            avatar_path=str(path),
        )

    @staticmethod
    def from_payload(
        payload: Dict[str, Any],
        source_path: str = "",
        avatar_path: str = "",
    ) -> CharacterCard:
        raw_payload = payload if isinstance(payload, dict) else {}
        card_data = raw_payload.get("data", raw_payload)

        name = _clean_text(card_data.get("name")) or "Custom Companion"
        card_id = CharacterCardParser.slugify(name)
        description = _replace_placeholders(_clean_text(card_data.get("description")), name)
        personality = _replace_placeholders(_clean_text(card_data.get("personality")), name)
        scenario = _replace_placeholders(_clean_text(card_data.get("scenario")), name)
        first_message = _replace_placeholders(_clean_text(card_data.get("first_mes")), name)
        message_example = _replace_placeholders(_clean_text(card_data.get("mes_example")), name)
        system_prompt = _replace_placeholders(_clean_text(card_data.get("system_prompt")), name)
        post_history_instructions = _replace_placeholders(
            _clean_text(card_data.get("post_history_instructions")),
            name,
        )
        creator_notes = _replace_placeholders(_clean_text(card_data.get("creator_notes")), name)

        tags = card_data.get("tags") or []
        if not isinstance(tags, list):
            tags = [str(tags)]

        normalized_tags: List[str] = []
        seen = set()
        for tag in tags:
            cleaned = str(tag).strip()
            token = cleaned.lower()
            if not cleaned or token in seen:
                continue
            seen.add(token)
            normalized_tags.append(cleaned)

        return CharacterCard(
            card_id=card_id,
            name=name,
            description=description,
            personality=personality,
            scenario=scenario,
            first_message=first_message,
            message_example=message_example,
            system_prompt=system_prompt,
            post_history_instructions=post_history_instructions,
            creator_notes=creator_notes,
            tags=normalized_tags,
            source_path=source_path,
            avatar_path=avatar_path,
            raw_payload=raw_payload,
        )

    @staticmethod
    def build_system_prompt(card: CharacterCard) -> str:
        sections: List[str] = [
            f"You are roleplaying as {card.name}.",
            "Stay fully consistent with this character's persona, relationship dynamic, emotional tone, and speaking style.",
            "Do not repeat the profile verbatim. Express it naturally through conversation.",
        ]

        if card.system_prompt:
            sections.append("Core system prompt:\n" + card.system_prompt)
        if card.description:
            sections.append("Character description:\n" + card.description)
        if card.personality:
            sections.append("Personality:\n" + card.personality)
        if card.scenario:
            sections.append("Scenario:\n" + card.scenario)
        if card.post_history_instructions:
            sections.append("Extra reply instructions:\n" + card.post_history_instructions)
        if card.message_example:
            sections.append("Reference dialogue examples:\n" + card.message_example)
        if card.creator_notes:
            sections.append("Creator notes:\n" + card.creator_notes)

        return "\n\n".join(section for section in sections if section.strip())

    @staticmethod
    def preview(card: CharacterCard) -> Dict[str, Any]:
        return {
            "name": card.name,
            "description": card.description[:300],
            "personality": card.personality[:200],
            "scenario": card.scenario[:200],
            "first_message": card.first_message[:200],
            "system_prompt": card.system_prompt[:200],
            "tags": card.tags,
        }

    @staticmethod
    def slugify(text: str) -> str:
        slug = re.sub(r"[^a-zA-Z0-9\u4e00-\u9fff]+", "-", text.strip()).strip("-").lower()
        return slug or "character"

    _slugify = slugify
