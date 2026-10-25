"""Local sample adapters: flow loading never mutates an existing database.

The offline profile is an extractive wiring demonstration, not a model-quality
benchmark. The ollama profile contacts only a loopback model server.
"""
import os
from pathlib import Path
from urllib.parse import urlsplit

import numpy as np
from sklearn.feature_extraction.text import HashingVectorizer

from ragang.adapters.embedding_adapter import BaseEmbeddingAdapter, LocalEmbeddingAdapter
from ragang.adapters.llm_adapter import OllamaLocalLLMAdapter
from ragang.adapters.milvus_adapter import MilvusAdapter

__all__ = ['load']


class OfflineEmbeddingAdapter(BaseEmbeddingAdapter):
    def __init__(self):
        super().__init__('local', 'token-hashing-1024-v1')
        self.vectorizer = HashingVectorizer(n_features=1024, alternate_sign=False, norm='l2')

    def create_embeddings(self, texts: list[str], batch_size: int = 32) -> np.ndarray:
        if not texts:
            return np.array([])
        return self.vectorizer.transform(texts).toarray()


class InMemoryDocumentIndex:
    def __init__(self, documents: list[str], embedding_adapter):
        self.documents = documents
        self.embedding_adapter = embedding_adapter
        self.vectors = embedding_adapter.create_embeddings(documents)
        if self.vectors.size == 0:
            raise RuntimeError('Document embedding failed; check the local embedding model')

    def retrieve(self, collection_name: str, query_vectors, top_k: int):
        vectors = np.asarray(query_vectors)
        if vectors.ndim != 2 or vectors.shape[1] != self.vectors.shape[1]:
            raise ValueError('Query and document embeddings have incompatible dimensions')
        results = []
        for query in vectors:
            norms = np.linalg.norm(self.vectors, axis=1) * np.linalg.norm(query)
            similarities = np.divide(self.vectors @ query, norms,
                                     out=np.zeros(len(self.documents)), where=norms > 0)
            ranked = np.argsort(-similarities, kind='stable')[:top_k]
            results.append([self.documents[index] for index in ranked if similarities[index] > 0])
        return results


def __init_milvus(collection_name: str = 'test', dim: int = 768) -> MilvusAdapter:
    """Connect to a pre-ingested collection without changing its contents."""
    adapter = MilvusAdapter(config_path='./config/vector_db.json')
    if not adapter.has_collection(collection_name):
        raise RuntimeError('Create and ingest the configured Milvus collection separately before evaluation')
    return adapter


def _loopback_endpoint(value: str) -> str:
    parsed = urlsplit(f'http://{value}')
    if parsed.hostname not in {'127.0.0.1', 'localhost', '::1'} or parsed.username or parsed.password:
        raise ValueError('The sample local profile requires a loopback Ollama endpoint')
    if parsed.path or parsed.query or parsed.fragment:
        raise ValueError('Ollama endpoint must be a host and port')
    return value


def load(api_key: str | None = None) -> dict:
    profile = os.environ.get('RAGANG_PROFILE', 'offline')
    if profile not in {'offline', 'ollama'}:
        raise ValueError('RAGANG_PROFILE must be offline or ollama')
    if profile == 'offline':
        embedding = OfflineEmbeddingAdapter()
        llm = None
    else:
        endpoint = _loopback_endpoint(os.environ.get('RAGANG_OLLAMA_HOST', '127.0.0.1:11434'))
        embedding = LocalEmbeddingAdapter(endpoint, os.environ.get('RAGANG_EMBEDDING_MODEL', 'nomic-embed-text'))
        llm = OllamaLocalLLMAdapter(endpoint, os.environ.get('RAGANG_LLM_MODEL', 'qwen2.5:3b'))
    documents = []
    for path in sorted(Path('datas/docs').glob('*.txt')):
        text = path.read_text(encoding='utf-8')
        documents.extend(text[index:index + 500] for index in range(0, len(text), 500) if text[index:index + 500].strip())
    if not documents:
        raise ValueError('Add UTF-8 .txt documents to datas/docs before running the sample')
    return {'vec': InMemoryDocumentIndex(documents, embedding), 'emb': embedding, 'llm': llm}
