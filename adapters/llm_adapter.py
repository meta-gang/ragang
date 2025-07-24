import requests
import os
from abc import ABC, abstractmethod

class BaseLLMAdapter(ABC):
    """Abstract base class for LLM adapters."""
    def __init__(self, model_name: str, api_url: str):
        self.model_name = model_name
        self.api_url = api_url

    @abstractmethod
    def request(self, prompt: str, query: str) -> dict:
        """Sends a request to the LLM API and returns the response."""
        pass

class LocalLLMAdapter(BaseLLMAdapter):
    """Adapter for local LLM APIs (e.g., Ollama)."""
    def request(self, prompt: str, query: str) -> dict:
        """Sends a request to a local LLM API."""
        payload = {
            "model": self.model_name,
            "prompt": f"{prompt}\n\n{query}" # A common format for local models
        }
        try:
            response = requests.post(self.api_url, json=payload)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"An error occurred while calling the local LLM API: {e}")
            return {"error": str(e)}

class OpenAIAdapter(BaseLLMAdapter):
    """Adapter for the OpenAI API."""
    def __init__(self, model_name: str, api_key: str, api_url: str = "https://api.openai.com/v1/chat/completions"):
        super().__init__(model_name, api_url)
        if not api_key:
            raise ValueError("API key is required for OpenAIAdapter")
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }

    def request(self, prompt: str, query: str) -> dict:
        """Sends a request to the OpenAI API."""
        payload = {
            "model": self.model_name,
            "messages": [
                {"role": "system", "content": prompt},
                {"role": "user", "content": query}
            ]
        }
        try:
            response = requests.post(self.api_url, headers=self.headers, json=payload)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"An error occurred while calling the OpenAI API: {e}")
            return {"error": str(e)}

class GeminiAdapter(BaseLLMAdapter):
    """Adapter for the Google Gemini API."""
    def __init__(self, model_name: str, api_key: str, api_version: str = "v1beta"):
        if not api_key:
            raise ValueError("API key is required for GeminiAdapter")
        # The model name is part of the URL for Gemini
        api_url = f"https://generativelanguage.googleapis.com/{api_version}/models/{model_name}:generateContent"
        super().__init__(model_name, api_url)
        self.api_key = api_key
        self.headers = {
            "Content-Type": "application/json"
        }

    def request(self, prompt: str, query: str) -> dict:
        """Sends a request to the Gemini API."""
        full_prompt = f"{prompt}\n\n{query}"
        payload = {
            "contents": [{
                "parts": [{
                    "text": full_prompt
                }]
            }]
        }
        params = {"key": self.api_key}
        try:
            response = requests.post(self.api_url, headers=self.headers, params=params, json=payload)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"An error occurred while calling the Gemini API: {e}")
            error_details = response.json() if response.content else {}
            return {"error": str(e), "details": error_details.get("error", {})}

