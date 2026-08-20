from __future__ import annotations

from collections.abc import Iterable

import numpy as np


class EmptyEmbeddingAdapter:
    def create_embeddings(self, texts: list[str], batch_size: int = 32) -> np.ndarray:
        return np.array([])


class MappingEmbeddingAdapter:
    def __init__(self, mapping: dict[str, list[float]] | None = None):
        self.mapping = mapping or {
            "query": [1.0, 0.0],
            "answer": [1.0, 0.0],
            "doc-1": [1.0, 0.0],
            "doc-2": [0.8, 0.2],
            "doc-3": [0.0, 1.0],
        }

    def create_embeddings(self, texts: list[str], batch_size: int = 32) -> np.ndarray:
        return np.array([self.mapping[text] for text in texts], dtype=float)


class ConstantLLMAdapter:
    def __init__(self, response: dict):
        self.response = response

    def request(self, *args, **kwargs) -> dict:
        return self.response


class SequenceLLMAdapter:
    def __init__(self, responses: Iterable[dict]):
        self.responses = iter(responses)

    def request(self, *args, **kwargs) -> dict:
        return next(self.responses)
