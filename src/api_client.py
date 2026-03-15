import requests
from typing import Dict, Any
from config import Config

class DeepseekAPIClient:
    def __init__(self):
        self.api_key = Config.API_KEY
        self.api_url = Config.API_URL
        self.model = Config.DEEPSEEK_MODEL
        self.temperature = Config.TEMPERATURE
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
    def chat(self, messages: list) -> str:
        data = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature
        }

        try:
            response = requests.post(
                self.api_url,headers=self.headers,json=data
            )
            response.raise_for_status()
            result = response.json()
            return result["choices"][0]["message"]["content"]
        except requests.exceptions.RequestException as e:
            raise Exception(f"API请求失败: {e}")

            