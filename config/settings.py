import os
from dotenv import load_dotenv

load_dotenv()
class Config:
    API_KEY = os.getenv("API_KEY")
    API_URL = os.getenv("API_URL")
    DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL")
    TEMPERATURE = float(os.getenv("TEMPERATURE"))

    personality_prompt= """你是一个温柔、体贴的AI情感伴侣，名叫天天。
你善于倾听，给予温暖、共情的回应。
请用友好、自然的语气与用户交流。"""
