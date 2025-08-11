from abc import ABC, abstractmethod
import numpy as np
import requests


class BaseEmbeddingAdapter(ABC):
    """Abstract base class for text embedding model adapters."""

    def __init__(self, api_url: str, model_name: str):
        self.api_url = api_url
        self.model_name = model_name

    @abstractmethod
    def create_embeddings(self, texts: list[str], batch_size: int = 32) -> np.ndarray:
        """
        Creates embeddings for a list of texts.

        Args:
            texts: A list of strings to be embedded.
            batch_size: The number of texts to process in a single batch.

        Returns:
            A numpy array of shape (n_texts, embedding_dim) containing the embeddings.
        """
        pass


class LocalEmbeddingAdapter(BaseEmbeddingAdapter):
    """Adapter for local embedding model.
    Note that the API request format(url, payload, etc) implemented here is for ollama only.
    You may have to check the exact requirement."""

    def __init__(self, api_url, model_name):
        url = f"http://{api_url}/api/embeddings"
        super().__init__(url, model_name)

    def create_embeddings(self, texts: list[str], batch_size: int = 32) -> np.ndarray:
        all_embeddings = []
        for i in range(0, len(texts), batch_size):
            batch_texts = texts[i:i + batch_size]
            for text in batch_texts:
                payload = {
                    "model": self.model_name,
                    "prompt": text
                }
                try:
                    response = requests.post(self.api_url, json=payload)
                    response.raise_for_status()
                    result = response.json()
                    all_embeddings.append(result["embedding"])
                except requests.exceptions.RequestException as e:
                    print(f"An error occurred while calling the local embedding API: {e}")
                    return np.array([])

        return np.array(all_embeddings)


class OpenAIEmbeddingAdapter(BaseEmbeddingAdapter):
    """Adapter for the OpenAI embedding API."""

    def __init__(self, api_key: str, model_name: str = "text-embedding-ada-002",
                 api_url: str = "https://api.openai.com/v1/embeddings"):
        super().__init__(api_url, model_name)
        if not api_key:
            raise ValueError("API key is required for OpenAIEmbeddingAdapter.")
        self.api_key = api_key
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

    def create_embeddings(self, texts: list[str], batch_size: int = 32) -> np.ndarray:
        all_embeddings = []
        for i in range(0, len(texts), batch_size):
            batch_texts = texts[i:i + batch_size]
            payload = {
                "input": batch_texts,
                "model": self.model_name
            }
            try:
                response = requests.post(self.api_url, headers=self.headers, json=payload)
                response.raise_for_status()
                embeddings = response.json()["data"]
                all_embeddings.extend([embedding["embedding"] for embedding in embeddings])
            except requests.exceptions.RequestException as e:
                print(f"An error occurred while calling the OpenAI embedding API: {e}")
                return np.array([])
        return np.array(all_embeddings)


class GeminiEmbeddingAdapter(BaseEmbeddingAdapter):
    """Adapter for the Google Gemini embedding API."""

    def __init__(self, api_key: str, model_name: str = "embedding-001", api_version: str = "v1beta"):
        if not api_key:
            raise ValueError("API key is required for GeminiEmbeddingAdapter.")
        api_url = f"https://generativelanguage.googleapis.com/{api_version}/models/{model_name}:batchEmbedContents"
        super().__init__(api_url, model_name)
        self.api_key = api_key
        self.headers = {
            "Content-Type": "application/json"
        }

    def create_embeddings(self, texts: list[str], batch_size: int = 100) -> np.ndarray:
        if batch_size > 100:
            print("Warning: Gemini API has a limit of 100 documents per request. Batch size will be capped at 100.")
            batch_size = 100

        all_embeddings = []
        for i in range(0, len(texts), batch_size):
            batch_texts = texts[i:i + batch_size]
            payload = {
                "requests": [{
                    "model": f"models/{self.model_name}",
                    "content": {
                        "parts": [{"text": text}]
                    }
                } for text in batch_texts]
            }
            params = {"key": self.api_key}
            try:
                response = requests.post(self.api_url, headers=self.headers, params=params, json=payload)
                response.raise_for_status()
                embeddings = response.json()["embeddings"]
                all_embeddings.extend([embedding["values"] for embedding in embeddings])
            except requests.exceptions.RequestException as e:
                print(f"An error occurred while calling the Gemini embedding API: {e}")
                return np.array([])
        return np.array(all_embeddings)
