"""Live demo with real Milvus retrieval and a supported Ollama LLM adapter."""

from __future__ import annotations

from hashlib import sha256
import os
from pathlib import Path
import re
from time import monotonic, sleep

import numpy as np

from ragang.adapters.embedding_adapter import BaseEmbeddingAdapter
from ragang.adapters.llm_adapter import OllamaLocalLLMAdapter
from ragang.adapters.milvus_adapter import MilvusAdapter
from ragang.container import RAGContainer
from ragang.core.bases.datas.linker import Linker
from ragang.metrics.builtin.e2e.non_llm_based import AnswerQuerySimilarity
from ragang.metrics.builtin.generator.non_llm_based import AnswerContextSimilarity
from ragang.metrics.builtin.retriever.non_llm_based import CosineSimilarityMetric
from ragang.modules.custom import CustomModule
from ragang.modules.generation_module import GenerationModule
from ragang.modules.retrieval_module import RetrievalModule


ROOT = Path(__file__).resolve().parent
COLLECTION = "ragang_live_demo"
DIMENSION = 64


class DeterministicTokenEmbedding(BaseEmbeddingAdapter):
    """Transparent local embedding used to isolate Milvus/LLM acceptance."""

    def __init__(self):
        super().__init__("local://deterministic", "token-hash-v1")

    def create_embeddings(self, texts: list[str], batch_size: int = 32) -> np.ndarray:
        vectors = []
        for text in texts:
            vector = np.zeros(DIMENSION, dtype=float)
            tokens = re.findall(r"[0-9A-Za-z가-힣]+", text.lower())
            for token in tokens:
                digest = sha256(token.encode("utf-8")).digest()
                index = int.from_bytes(digest[:4], "big") % DIMENSION
                vector[index] += 1.0 if digest[4] % 2 == 0 else -1.0
            norm = np.linalg.norm(vector)
            if norm == 0:
                vector[0] = 1.0
            else:
                vector /= norm
            vectors.append(vector)
        return np.asarray(vectors)


embedding_adapter = DeterministicTokenEmbedding()
llm_adapter = OllamaLocalLLMAdapter(
    os.getenv("RAGANG_OLLAMA_HOST", "127.0.0.1:11434"),
    os.getenv("RAGANG_OLLAMA_MODEL", "llama3:latest"),
)
milvus_adapter = MilvusAdapter(config_path=str(ROOT / "config/vector_db.json"))


def prepare_collection(
    timeout_seconds: float = 90.0,
    retry_interval_seconds: float = 2.0,
) -> None:
    documents = [
        path.read_text(encoding="utf-8")
        for path in sorted((ROOT / "datas/docs").glob("live_*.txt"))
    ]
    vectors = embedding_adapter.create_embeddings(documents)
    deadline = monotonic() + timeout_seconds

    while True:
        try:
            if milvus_adapter.has_collection(COLLECTION):
                milvus_adapter.drop_collection(COLLECTION)
            collection = milvus_adapter.create_collection(COLLECTION, DIMENSION)
            if collection is not None:
                result = milvus_adapter.insert(
                    COLLECTION,
                    [vectors.tolist(), documents],
                )
                if result is not None:
                    milvus_adapter.create_index(COLLECTION)
                    return
        except Exception:
            # The adapter logs the Milvus-side cause. Keep retry output generic so
            # connection details cannot accidentally become persisted metadata.
            pass

        if monotonic() >= deadline:
            raise RuntimeError("Milvus did not become ready for the live demo")
        print("Milvus is not ready; retrying live demo collection setup...")
        sleep(retry_interval_seconds)


class QueryInput(CustomModule):
    async def execute(self, query: str):
        return {"query": query}


class LiveMilvusRetrieval(RetrievalModule):
    def __init__(self, module_id: str, linker: Linker, mode: str, metrics=None):
        super().__init__(module_id, linker, metrics, False)
        if mode not in {"focused", "noisy"}:
            raise ValueError("RAGANG_LIVE_DEMO_MODE must be focused or noisy")
        self.mode = mode
        self.embedding_adapter = embedding_adapter
        self.milvus_adapter = milvus_adapter
        self.collection_name = COLLECTION
        self.top_k = 1

    async def execute(self, query: str):
        retrieval_query = query if self.mode == "focused" else "sourdough fermentation baking"
        query_vectors = self.embedding_adapter.create_embeddings([retrieval_query])
        result = self.milvus_adapter.retrieve(
            self.collection_name,
            query_vectors.tolist(),
            top_k=self.top_k,
        )
        if not result:
            raise RuntimeError("Milvus returned no retrieval result")
        return {"query": query, "ret_docs": result[0]}


class LiveOllamaGeneration(GenerationModule):
    def __init__(self, module_id: str, linker: Linker, metrics=None):
        super().__init__(module_id, linker, metrics, False)
        self.llm_adapter = llm_adapter

    async def execute(self, query: str, ret_docs: list[str]):
        context = "\n\n".join(ret_docs)
        response = self.llm_adapter.request(
            "Answer only from the supplied context. If unsupported, say you do not know.",
            f"Context:\n{context}\n\nQuestion: {query}",
        )
        if "error" in response or not response.get("text"):
            raise RuntimeError("Ollama generation failed")
        return {"gen": response["text"]}


def containers():
    mode = os.getenv("RAGANG_LIVE_DEMO_MODE", "focused")
    prepare_collection()
    return [
        RAGContainer(
            "live_ollama_milvus",
            [
                QueryInput("starter", is_starter=True),
                LiveMilvusRetrieval(
                    "retrieval",
                    linker=Linker("starter"),
                    mode=mode,
                    metrics=[
                        CosineSimilarityMetric(
                            ["starter.query", "retrieval.ret_docs"],
                            embedding_adapter=embedding_adapter,
                        )
                    ],
                ),
                LiveOllamaGeneration(
                    "generation",
                    linker=Linker("retrieval"),
                    metrics=[
                        AnswerContextSimilarity(
                            ["retrieval.ret_docs", "generation.gen"],
                            embedding_adapter=embedding_adapter,
                        )
                    ],
                ),
            ],
            e2e_metrics=[
                AnswerQuerySimilarity(
                    ["starter.query", "generation.gen"],
                    embedding_adapter=embedding_adapter,
                )
            ],
        )
    ]
