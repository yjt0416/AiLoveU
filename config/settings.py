import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    API_KEY = os.getenv("API_KEY")
    API_URL = os.getenv("API_URL")
    DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL")
    try:
        TEMPERATURE = float(os.getenv("TEMPERATURE"))
    except Exception:
        raise

    AI_NAME = os.getenv("AI_NAME", "AiLoveU")

    personality_prompt= """你是一个温柔、体贴的AI对话助手，名叫{ai_name}。
你善于倾听，给予温暖、共情的回应。
请用友好、自然的语气与用户交流。"""
