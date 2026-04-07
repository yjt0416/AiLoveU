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


def _replace_placeholders(text: str, char_name: str, user_name: str = "用户") -> str:
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
            metadata = {}
            metadata.update(getattr(image, "info", {}) or {})
            metadata.update(getattr(image, "text", {}) or {})

        chara_payload = metadata.get("chara")
        if not chara_payload:
            raise ValueError("PNG 中未找到角色卡元数据，缺少 `chara` 字段。")

        try:
            decoded = base64.b64decode(chara_payload).decode("utf-8")
            payload = json.loads(decoded)
        except Exception as exc:
            raise ValueError("角色卡元数据解析失败，`chara` 不是有效的 base64 JSON。") from exc

        card_data = payload.get("data", payload)
        name = _clean_text(card_data.get("name")) or path.stem
        card_id = CharacterCardParser._slugify(name)

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
        tags = [str(tag).strip() for tag in tags if str(tag).strip()]

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
            tags=tags,
            source_path=str(path),
            avatar_path=str(path),
            raw_payload=payload,
        )

    @staticmethod
    def build_system_prompt(card: CharacterCard) -> str:
        sections: List[str] = [
            f"你现在扮演的角色是：{card.name}。",
            "请始终保持这个角色的人设、语气、关系设定和说话风格。",
            "如果用户请求和角色设定冲突，优先保持角色一致性，并自然地完成回应。",
        ]

        if card.system_prompt:
            sections.append("角色系统设定：\n" + card.system_prompt)
        if card.description:
            sections.append("角色描述：\n" + card.description)
        if card.personality:
            sections.append("角色性格：\n" + card.personality)
        if card.scenario:
            sections.append("场景设定：\n" + card.scenario)
        if card.post_history_instructions:
            sections.append("额外回复要求：\n" + card.post_history_instructions)
        if card.message_example:
            sections.append("对话示例参考：\n" + card.message_example)
        if card.creator_notes:
            sections.append("创作者备注：\n" + card.creator_notes)

        sections.append("回复时不要直接复述这些设定，而是自然地表现出来。")
        return "\n\n".join(item for item in sections if item.strip())

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
    def _slugify(text: str) -> str:
        slug = re.sub(r"[^a-zA-Z0-9\u4e00-\u9fff]+", "-", text.strip()).strip("-").lower()
        return slug or "character"
