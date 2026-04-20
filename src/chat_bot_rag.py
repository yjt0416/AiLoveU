import re
from typing import Dict, List

from config import Config
from src.api_client import DeepseekAPIClient
from src.character_registry import CharacterProfile, CharacterRegistry
from src.custom_character_builder import CustomCharacterBuilder
from src.llm_memory_extractor import LLMMemoryExtractor
from src.memory_engine import MemoryManager


class ChatBot:
    def __init__(self):
        self.api_client = DeepseekAPIClient()
        self.character_registry = CharacterRegistry(Config.CHARACTER_REGISTRY_PATH)
        self.current_character = self.character_registry.get_active_character()
        self.ai_name = self.current_character.name
        self.last_detected_language = "Simplified Chinese"
        self.memory_manager = MemoryManager(
            db_path=Config.MEMORY_DB_PATH,
            short_term_turns=Config.SHORT_TERM_MEMORY_TURNS,
            top_k=Config.RAG_MEMORY_TOP_K,
            namespace=self.current_character.character_id,
        )
        self.memory_extractor = LLMMemoryExtractor(
            api_client=self.api_client,
            model=Config.MEMORY_EXTRACTION_MODEL,
            temperature=Config.MEMORY_EXTRACTION_TEMPERATURE,
        )
        self.custom_character_builder = CustomCharacterBuilder(
            api_client=self.api_client,
            model=Config.CUSTOM_CHARACTER_MODEL,
            temperature=Config.CUSTOM_CHARACTER_TEMPERATURE,
        )
        self.conversation_history: List[Dict[str, str]] = []
        self._ensure_character_greeting()
        self._refresh_history_snapshot()

    def set_ai_name(self, name: str):
        name = (name or "").strip()
        if not name:
            return
        profile = self.character_registry.rename_character(
            self.current_character.character_id,
            name,
        )
        self.current_character = profile
        self.ai_name = profile.name
        self._refresh_history_snapshot()

    def reset_session(self):
        self.memory_manager.start_new_session()
        self._ensure_character_greeting()
        self._refresh_history_snapshot()

    def send_message(self, user_input: str) -> str:
        user_input = (user_input or "").strip()
        if not user_input:
            return ""

        messages = self._build_messages(user_input)
        self.memory_manager.store_turn("user", user_input)

        ai_response = self.api_client.chat(messages)
        self.memory_manager.store_turn("assistant", ai_response)
        extraction = self.memory_extractor.extract(user_input)
        self.memory_manager.upsert_structured_memory(extraction)
        self._refresh_history_snapshot()
        return ai_response

    def create_custom_character(
        self,
        user_notes: str,
        name_hint: str = "",
        tags_hint: str = "",
    ) -> CharacterProfile:
        payload = self.custom_character_builder.build(
            user_notes=user_notes,
            name_hint=name_hint,
            tags_hint=tags_hint,
        )
        profile = self.character_registry.create_custom_character(payload)
        self.switch_character(profile.character_id)
        return self.current_character

    def get_memory_summary(self):
        return self.memory_manager.get_memory_summary()

    def list_characters(self) -> List[CharacterProfile]:
        return self.character_registry.list_characters()

    def get_current_character(self) -> CharacterProfile:
        return self.current_character

    def import_character_card(self, file_path: str) -> CharacterProfile:
        profile = self.character_registry.import_character_card(file_path)
        self.switch_character(profile.character_id)
        return self.current_character

    def switch_character(self, character_id: str) -> CharacterProfile:
        profile = self.character_registry.set_active_character(character_id)
        self.current_character = profile
        self.ai_name = profile.name
        self.memory_manager.set_namespace(profile.character_id, restore_last_session=True)
        self._ensure_character_greeting()
        self._refresh_history_snapshot()
        return profile

    def get_transcript(self, limit: int = 200) -> List[Dict[str, str]]:
        return self.memory_manager.get_transcript(limit=limit)

    def _build_messages(self, user_input: str) -> List[Dict[str, str]]:
        language_instruction = self._build_language_instruction(user_input)
        response_length_instruction = self._build_response_length_instruction(user_input)
        messages: List[Dict[str, str]] = [
            {"role": "system", "content": self.current_character.system_prompt},
            {"role": "system", "content": language_instruction},
            {"role": "system", "content": response_length_instruction},
        ]

        rag_context = self.memory_manager.build_rag_context(user_input)
        if rag_context:
            messages.append({"role": "system", "content": rag_context})

        messages.extend(self.memory_manager.get_recent_messages())
        messages.append({"role": "user", "content": user_input})
        self.conversation_history = messages
        return messages

    def _refresh_history_snapshot(self) -> None:
        self.conversation_history = [
            {"role": "system", "content": self.current_character.system_prompt},
            *self.memory_manager.get_recent_messages(),
        ]

    def _ensure_character_greeting(self) -> None:
        transcript = self.memory_manager.get_transcript(limit=1)
        if transcript:
            return
        first_message = (self.current_character.first_message or "").strip()
        if first_message:
            self.memory_manager.store_turn("assistant", first_message)

    def _build_language_instruction(self, user_input: str) -> str:
        language = self._detect_language(user_input)
        self.last_detected_language = language
        return (
            f"Reply in {language}. "
            "Match the user's latest message language by default. "
            "Keep the character's persona, tone, and relationship setting, but translate your response naturally into that language. "
            "Only switch to another language if the user explicitly asks you to do so."
        )

    def _build_response_length_instruction(self, user_input: str) -> str:
        mode = self._detect_response_length_mode(user_input)
        if mode == "one_sentence":
            return (
                "Answer in exactly one natural sentence. "
                "Keep it in character, but do not add a second sentence unless the user changes the instruction."
            )
        if mode == "concise":
            return (
                "Keep the reply concise but not abrupt. "
                "Usually answer in 2 to 3 sentences, unless the user explicitly asks for more detail."
            )
        if mode == "detailed":
            return (
                "Give a fuller answer. "
                "Usually answer in 6 to 10 sentences or a short structured explanation with at least 3 concrete points, while staying natural and in character."
            )
        return (
            "Give a moderately rich answer by default. "
            "Usually answer in 3 to 5 sentences so the reply feels complete, warm, and useful instead of overly brief. "
            "Do not answer with only one short sentence unless the user explicitly asks for brevity."
        )

    def _detect_response_length_mode(self, text: str) -> str:
        text = (text or "").strip()
        if not text:
            return "balanced"

        lowered = text.lower()
        one_sentence_patterns = (
            "一句话",
            "只用一句话",
            "用一句话",
            "one sentence",
            "single sentence",
        )
        if any(pattern in lowered for pattern in one_sentence_patterns):
            return "one_sentence"

        explicit_brief_patterns = (
            "简短",
            "简单说",
            "一两句",
            "短一点",
            "简短回答",
            "长话短说",
            "briefly",
            "shortly",
            "be concise",
            "keep it short",
        )
        if any(pattern in lowered for pattern in explicit_brief_patterns):
            return "concise"

        explicit_detailed_patterns = (
            "详细",
            "展开",
            "具体",
            "多说一点",
            "详细说说",
            "细讲",
            "分析",
            "分步骤",
            "举例",
            "全面",
            "深入",
            "explain",
            "details",
            "step by step",
            "analyze",
            "analysis",
            "compare",
            "with examples",
        )
        if any(pattern in lowered for pattern in explicit_detailed_patterns):
            return "detailed"

        question_mark_count = text.count("?") + text.count("？")
        comma_count = text.count("，") + text.count(",")
        sentence_length = len(text)

        if question_mark_count >= 2:
            return "detailed"
        if sentence_length >= 60 or comma_count >= 3:
            return "detailed"

        return "balanced"

    def _detect_language(self, text: str) -> str:
        text = (text or "").strip()
        if not text:
            return self.last_detected_language

        if re.search(r"[\u3040-\u30ff]", text):
            return "Japanese"
        if re.search(r"[\uac00-\ud7af]", text):
            return "Korean"
        if re.search(r"[\u0600-\u06ff]", text):
            return "Arabic"
        if re.search(r"[\u0400-\u04ff]", text):
            return "Russian"
        if re.search(r"[\u4e00-\u9fff]", text):
            return "Simplified Chinese"

        latin_letters = re.findall(r"[A-Za-z]", text)
        if latin_letters:
            return "English"

        return self.last_detected_language
