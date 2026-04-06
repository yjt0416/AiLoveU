from typing import List, Dict
from src.api_client import DeepseekAPIClient
from config import Config

class ChatBot:
    def __init__(self):
        self.api_client = DeepseekAPIClient()
        self.ai_name = getattr(Config, "AI_NAME", "AiLoveU")
        self.conversation_history: List[Dict[str, str]] = [
            {"role": "system", "content": 
             Config.personality_prompt.format(ai_name=self.ai_name)}
        ]

    def set_ai_name(self, name: str):
        name = (name or "").strip()
        if not name:
            return
        self.ai_name = name
        # 更新 system prompt，让模型也用新名字自称
        if self.conversation_history and self.conversation_history[0].get("role") == "system":
            self.conversation_history[0]["content"] = Config.personality_prompt.format(ai_name=self.ai_name)
        else:
            self.conversation_history.insert(0, {"role": "system", "content": Config.personality_prompt.format(ai_name=self.ai_name)})
    def send_message(self, user_input: str) -> str:
        self.conversation_history.append({"role": "user", 
                                          "content": user_input})
        ai_response = self.api_client.chat(self.conversation_history)
        self.conversation_history.append({"role": "assistant", 
                                          "content": ai_response})
        return ai_response
    
        
        