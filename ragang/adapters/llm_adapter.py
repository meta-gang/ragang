from abc import ABC, abstractmethod
import requests
import asyncio
import httpx


def _safe_request_error(error: BaseException) -> dict:
    """Return bounded failure metadata without URL query strings or response bodies."""
    result = {"error": type(error).__name__}
    response = getattr(error, "response", None)
    status_code = getattr(response, "status_code", None)
    if isinstance(status_code, int):
        result["status_code"] = status_code
    return result


class BaseLLMAdapter(ABC):
    """Abstract base class for LLM adapters."""

    def __init__(self, api_url: str, model_name: str):
        self.api_url = api_url
        self.model_name = model_name
        
    @abstractmethod
    def request(self, prompt: str, query: str):
        """Sends a request to the LLM API and returns the response."""
        pass

    @abstractmethod
    async def request_async(self, client: httpx.AsyncClient, prompt: str, query: str) -> dict:
        """Sends an asynchronous request to the LLM API and returns the response."""
        pass

    async def request_async_batch(self, prompts: list[str], queries: list[str], max_workers: int = 10) -> list[dict]:
        """
        Sends a batch of requests concurrently using asyncio.gather, with a semaphore to limit concurrency.

        Args:
            prompts: A list of prompts.
            queries: A list of queries.
            max_workers: The maximum number of concurrent requests.
        """
        if len(prompts) != len(queries):
            raise ValueError("Prompts and queries lists must have the same length.")
        if isinstance(max_workers, bool) or not isinstance(max_workers, int) or max_workers <= 0:
            raise ValueError("max_workers must be a positive integer")

        semaphore = asyncio.Semaphore(max_workers)

        async def run_with_semaphore(client: httpx.AsyncClient, prompt: str, query: str):
            async with semaphore:
                return await self.request_async(client, prompt, query)

        async with httpx.AsyncClient() as client:
            tasks = []
            for prompt, query in zip(prompts, queries):
                tasks.append(run_with_semaphore(client, prompt, query))
            results = await asyncio.gather(*tasks, return_exceptions=True)
        return results
    

class OllamaLocalLLMAdapter(BaseLLMAdapter):
    """Adapter for Ollama local LLM API."""

    def __init__(self, api_url, model_name):
        url = f"http://{api_url}/api/generate"
        super().__init__(url, model_name)

    def request(self, prompt: str, query: str) -> dict:
        """Sends a request to a local LLM API."""
        payload = {
            "model": self.model_name,
            "prompt": f"{prompt}\n\n{query}",
            "stream": False
        }
        try:
            response = requests.post(self.api_url, json=payload, timeout=30.0)
            response.raise_for_status()
            result = response.json()
            return {
                "text": result.get("response", ""),
                "raw": result
            }
        except requests.exceptions.RequestException as e:
            return _safe_request_error(e)

    async def request_async(self, client: httpx.AsyncClient, prompt: str, query: str) -> dict:
        """Sends a request to Ollama local LLM API."""
        payload = {
            "model": self.model_name,
            "prompt": f"{prompt}\n\n{query}",
            "stream": False
        }
        try:
            response = await client.post(self.api_url, json=payload, timeout=30.0)
            response.raise_for_status()
            result = response.json()
            return {
                "text": result.get("response", ""),
                "raw": result
            }
        except (httpx.HTTPStatusError, httpx.RequestError) as e:
            return _safe_request_error(e)


class OpenAIAdapter(BaseLLMAdapter):
    """Adapter for the OpenAI API."""

    def __init__(self, model_name: str, api_key: str, api_url: str = "https://api.openai.com/v1/chat/completions"):
        super().__init__(api_url, model_name)
        if not api_key:
            raise ValueError("API key is required for OpenAIAdapter.")
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
            response = requests.post(self.api_url, headers=self.headers, json=payload, timeout=30.0)
            response.raise_for_status()
            data = response.json()
            # extracting text from the response in json format
            response_text = data["choices"][0]["message"]["content"]
            return {"text": response_text, "raw": data}
        except requests.exceptions.RequestException as e:
            return _safe_request_error(e)
        
    async def request_async(self, client: httpx.AsyncClient, prompt: str, query: str) -> dict:
        """Sends a request to the OpenAI API."""
        payload = {
            "model": self.model_name,
            "messages": [
                {"role": "system", "content": prompt},
                {"role": "user", "content": query}
            ]
        }
        try:
            response = await client.post(self.api_url, headers=self.headers, json=payload, timeout=30.0)
            response.raise_for_status()
            data = response.json()
            # extracting text from the response in json format
            response_text = data["choices"][0]["message"]["content"]
            return {"text": response_text, "raw": data}
        except (httpx.HTTPStatusError, httpx.RequestError) as e:
            return _safe_request_error(e)


class GeminiAdapter(BaseLLMAdapter):
    """Adapter for the Google Gemini API."""

    def __init__(self, model_name: str, api_key: str, api_version: str = "v1beta"):
        if not api_key:
            raise ValueError("API key is required for GeminiAdapter.")
        # The model name is part of the URL for Gemini
        api_url = f"https://generativelanguage.googleapis.com/{api_version}/models/{model_name}:generateContent"
        super().__init__(api_url, model_name)
        self.api_key = api_key
        self.headers = {
            "Content-Type": "application/json"
        }
        self.params = {"key": self.api_key}
    
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
            response = requests.post(
                self.api_url,
                headers=self.headers,
                params=params,
                json=payload,
                timeout=30.0,
            )
            response.raise_for_status()
            data = response.json()
            # extracting text from the response in json format
            response_text = data["candidates"][0]["content"]["parts"][0]["text"]
            return {"text": response_text, "raw": data}
        except requests.exceptions.RequestException as e:
            return _safe_request_error(e)
    
    async def request_async(self, client: httpx.AsyncClient, prompt: str, query: str) -> dict:
        """Sends an asynchronous request to the Gemini API."""
        full_prompt = f"{prompt}\n\n{query}"
        payload = {
            "contents": [{
                "parts": [{"text": full_prompt}]
            }]
        }
        try:
            response = await client.post(self.api_url, headers=self.headers, params=self.params, json=payload, timeout=30.0)
            response.raise_for_status()
            data = response.json()
            response_text = data.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")
            return {"text": response_text, "raw": data}
        except (httpx.HTTPStatusError, httpx.RequestError) as e:
            return _safe_request_error(e)
