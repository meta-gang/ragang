import requests
from abc import ABC, abstractmethod
import json
import numpy as np

class BaseAdapter(ABC):
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