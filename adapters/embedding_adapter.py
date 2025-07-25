from abc import ABC, abstractmethod
import numpy as np
import requests

class BaseEmbeddingAdapter(ABC):
    """Abstract base class for text embedding model adapters."""
    def __init__(self, api_url: str, model_name: str):
        self.api_url = api_url
        self.model_name = model_name


    @abstractmethod
    def create_embeddings(self, texts: list[str]) -> np.ndarray:
        """
        Creates embeddings for a list of texts.

        Args:
            texts: A list of strings to be embedded.

        Returns:
            A numpy array of shape (n_texts, embedding_dim) containing the embeddings.
        """
        pass

class LocalEmbeddingAdapter(BaseEmbeddingAdapter):
    """Adapter for local embedding models."""

    def create_embeddings(self, texts: list[str]) -> np.ndarray:
        payload = {
            "model": self.model_name,
            "input": texts
        }
        try:
            response = requests.post(self.api_url, json=payload)
            response.raise_for_status()
            embeddings = response.json()["data"]
            return np.array([embedding["embedding"] for embedding in embeddings])   #실제 로컬 API 포맷에 따라 변경 필요
        except requests.exceptions.RequestException as e:
            print(f"An error occurred while calling the local embedding API: {e}")
            return np.array([])

class OpenAIEmbeddingAdapter(BaseEmbeddingAdapter):
    """Adapter for the OpenAI embedding API."""
    def __init__(self, api_key: str, model_name: str = "text-embedding-ada-002", api_url: str = "https://api.openai.com/v1/embeddings"):
        super().__init__(api_url, model_name)
        if not api_key:
            raise ValueError("API key is required for OpenAIEmbeddingAdapter.")
        self.api_key = api_key
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

    def create_embeddings(self, texts: list[str]) -> np.ndarray:
        payload = {
            "input": texts,
            "model": self.model_name
        }
        try:
            response = requests.post(self.api_url, headers=self.headers, json=payload)
            response.raise_for_status()
            embeddings = response.json()["data"]
            return np.array([embedding["embedding"] for embedding in embeddings])
        except requests.exceptions.RequestException as e:
            print(f"An error occurred while calling the OpenAI embedding API: {e}")
            return np.array([])

class GeminiEmbeddingAdapter(BaseEmbeddingAdapter):
    """Adapter for the Google Gemini embedding API."""
    def __init__(self, api_key: str, model_name: str = "embedding-001", api_version: str = "v1beta"):
        if not api_key:
            raise ValueError("API key is required for GeminiEmbeddingAdapter.")
        self.api_key = api_key
        self.model_name = model_name
        self.api_url = f"https://generativelanguage.googleapis.com/{api_version}/models/{self.model_name}:batchEmbedContents"
        self.headers = {
            "Content-Type": "application/json"
        }

    def create_embeddings(self, texts: list[str]) -> np.ndarray:
        payload = {
            "requests": [{
                "model": f"models/{self.model_name}",
                "content": {
                    "parts": [{"text": text}]
                }
            } for text in texts]
        }
        params = {"key": self.api_key}
        try:
            response = requests.post(self.api_url, headers=self.headers, params=params, json=payload)
            response.raise_for_status()
            embeddings = response.json()["embeddings"]
            return np.array([embedding["values"] for embedding in embeddings])
        except requests.exceptions.RequestException as e:
            print(f"An error occurred while calling the Gemini embedding API: {e}")
            return np.array([])
