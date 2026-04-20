import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"


class Config:
    API_KEY = os.getenv("API_KEY")
    API_URL = os.getenv("API_URL", "https://api.deepseek.com/v1/chat/completions")
    DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
    TEMPERATURE = float(os.getenv("TEMPERATURE", "0.8"))

    AI_NAME = os.getenv("AI_NAME", "AiLoveU")
    MEMORY_DB_PATH = os.getenv("MEMORY_DB_PATH", str(DATA_DIR / "aipartner_memory.db"))
    CHARACTER_REGISTRY_PATH = os.getenv("CHARACTER_REGISTRY_PATH", str(DATA_DIR / "characters.json"))
    SHORT_TERM_MEMORY_TURNS = int(os.getenv("SHORT_TERM_MEMORY_TURNS", "8"))
    RAG_MEMORY_TOP_K = int(os.getenv("RAG_MEMORY_TOP_K", "4"))
    MEMORY_EXTRACTION_MODEL = os.getenv("MEMORY_EXTRACTION_MODEL", DEEPSEEK_MODEL)
    MEMORY_EXTRACTION_TEMPERATURE = float(os.getenv("MEMORY_EXTRACTION_TEMPERATURE", "0.1"))
    CUSTOM_CHARACTER_MODEL = os.getenv("CUSTOM_CHARACTER_MODEL", DEEPSEEK_MODEL)
    CUSTOM_CHARACTER_TEMPERATURE = float(os.getenv("CUSTOM_CHARACTER_TEMPERATURE", "0.2"))

    personality_prompt = (
        "You are a warm, thoughtful, and emotionally intelligent AI companion named {ai_name}. "
        "Combine the user's recent context, preferences, and remembered history to answer naturally. "
        "Be friendly, sincere, and supportive, while keeping healthy boundaries and a conversational tone."
    )
