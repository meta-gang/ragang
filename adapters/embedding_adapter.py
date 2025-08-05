from abc import ABC, abstractmethod
import numpy as np
import requests

import json

class BaseEmbeddingAdapter(ABC):
    """Abstract base class for text embedding model adapters."""
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
    """Adapter for local embedding model.
    Note that the API request format(url, payload, etc) implemented here is for ollama only.
    You may have to check the exact requirement."""

    def __init__(self):
        super().__init__()

    def create_embeddings(self, texts: list[str]) -> np.ndarray:
        embeddings = []
        for text in texts:
            payload = {
                "model": self.model_name,
                "prompt": text
            }
            try:
                response = requests.post(self.api_url, json=payload)
                response.raise_for_status()
                result = response.json()
                embeddings.append(result["embedding"])
            except requests.exceptions.RequestException as e:
                print(f"An error occurred while calling the local embedding API: {e}")
                return np.array([])

        return np.array([embeddings])


class OpenAIEmbeddingAdapter(BaseEmbeddingAdapter):
    """Adapter for the OpenAI embedding API."""
    def __init__(self):
        super().__init__()
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
    def __init__(self):
        super().__init__()
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


if __name__ == '__main__':
    LocalEmbeddingAdapter()