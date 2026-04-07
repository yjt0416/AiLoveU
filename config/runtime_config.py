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

    personality_prompt = """你是一个温柔、体贴、善于倾听的 AI 对话伙伴，名字叫 {ai_name}。
你会结合用户的上下文、偏好和历史记忆，给出自然、真诚、不过度打扰的回应。
请保持友好、自然、有边界感的语气与用户交流。"""
