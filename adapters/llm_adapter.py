import requests
from abc import ABC, abstractmethod

import json

class BaseLLMAdapter(ABC):
    """Abstract base class for LLM adapters."""
    def __init__(self):
        with open('adapters/API.json') as f:
            data = json.load(f)
            self.api_url = data["API_URL"]
            
            if data["API_KEY"] == None:
                pass
            else:
                self.api_key = data["API_KEY"]
            
            self.model_name = data["MODEL_NAME"]

    @abstractmethod
    def request(self, prompt: str, query: str) -> dict:
        """Sends a request to the LLM API and returns the response."""
        pass


class LocalLLMAdapter(BaseLLMAdapter):
    """Adapter for local LLM APIs (e.g., Ollama)."""

    def __init__(self):
        super().__init__()

    def request(self, prompt: str, query: str) -> dict:
        """Sends a request to a local LLM API."""
        payload = {
            "model": self.model_name,
            "prompt": f"{prompt}\n\n{query}",
            "stream": False
        }
        try:
            response = requests.post(self.api_url, json=payload)
            response.raise_for_status()
            result = response.json()
            return {
                "text": result.get("response", ""),
                "raw": result                        
            }
        except requests.exceptions.RequestException as e:
            print(f"An error occurred while calling the local LLM API: {e}")
            return {"error": str(e)}

class OpenAIAdapter(BaseLLMAdapter):
    """Adapter for the OpenAI API."""
    def __init__(self):
        super().__init__()
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
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
            data = response.json()
            #extracting text from the response in json format
            response_text = data["choices"][0]["message"]["content"]
            return {"text" : response_text, "raw" : data}
        except requests.exceptions.RequestException as e:
            print(f"An error occurred while calling the OpenAI API: {e}")
            return {"error": str(e)}

class GeminiAdapter(BaseLLMAdapter):
    """Adapter for the Google Gemini API."""
    def __init__(self):
        super().__init__()
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
            data = response.json()
            #extracting text from the response in json format
            response_text = data["candidates"][0]["content"]["parts"][0]["text"]
            return {"text" : response_text, "raw" : data}
        except requests.exceptions.RequestException as e:
            print(f"An error occurred while calling the Gemini API: {e}")
            error_details = response.json() if response.content else {}
            return {"error": str(e), "details": error_details.get("error", {})}

