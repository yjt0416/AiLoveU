from typing import List, Dict
from src.api_client import DeepseekAPIClient
from config import Config

class ChatBot:
    def __init__(self):
        self.api_client = DeepseekAPIClient()
        self.conversation_history: List[Dict[str, str]] = [
            {"role": "system", "content": 
             Config.personality_prompt}
        ]
    def send_message(self, user_input: str) -> str:
        self.conversation_history.append({"role": "user", 
                                          "content": user_input})
        ai_response = self.api_client.chat(self.conversation_history)
        self.conversation_history.append({"role": "assistant", 
                                          "content": ai_response})
        return ai_response
    
        
        