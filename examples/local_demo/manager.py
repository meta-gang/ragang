"""Network-free RAGANG demo using real runtime documents and metrics."""

from pathlib import Path
import os
import re

from ragang.container import RAGContainer
from ragang.core.bases.datas.linker import Linker
from ragang.core.bases.datas.performance import Performance
from ragang.metrics.custom import CustomMetric
from ragang.modules.custom import CustomModule
from ragang.modules.generation_module import GenerationModule
from ragang.modules.retrieval_module import RetrievalModule


PROJECT_ROOT = Path(__file__).resolve().parent


def _tokens(text: str) -> set[str]:
    return {token for token in re.findall(r"[0-9A-Za-z가-힣]+", text.lower()) if len(token) > 1}


class QueryInput(CustomModule):
    async def execute(self, query: str):
        return {"query": query}


class LocalTextRetriever(RetrievalModule):
    def __init__(self, module_id: str, linker: Linker, mode: str, metrics=None):
        super().__init__(module_id, linker, metrics, False)
        if mode not in {"focused", "noisy", "empty"}:
            raise ValueError("RAGANG_DEMO_MODE must be focused, noisy, or empty")
        self.mode = mode
        self.top_k = 1
        self.documents = [
            path.read_text(encoding="utf-8")
            for path in sorted((PROJECT_ROOT / "datas/docs").glob("*.txt"))
        ]

    async def execute(self, query: str):
        if self.mode == "empty":
            return {"query": query, "ret_docs": []}
        query_tokens = _tokens(query)
        ranked = sorted(
            self.documents,
            key=lambda document: len(query_tokens & _tokens(document)),
            reverse=self.mode == "focused",
        )
        return {"query": query, "ret_docs": ranked[:self.top_k]}


class EvidenceBoundAnswer(GenerationModule):
    async def execute(self, query: str, ret_docs: list[str]):
        if not ret_docs:
            return {"gen": "No retrieved evidence is available, so I cannot answer safely."}
        excerpt = " ".join(ret_docs[0].split())[:360]
        return {"gen": f"Based on the retrieved document: {excerpt}"}


class QueryContextCoverage(CustomMetric):
    def evaluate(self, query: str, ret_docs: list[str]) -> Performance:
        query_tokens = _tokens(query)
        context_tokens = _tokens(" ".join(ret_docs))
        score = 0.0 if not query_tokens else 100.0 * len(query_tokens & context_tokens) / len(query_tokens)
        return Performance(score=score, metric="Query-context coverage")


class AnswerEvidenceOverlap(CustomMetric):
    def evaluate(self, ret_docs: list[str], answer: str) -> Performance:
        answer_tokens = _tokens(answer)
        context_tokens = _tokens(" ".join(ret_docs))
        score = 0.0 if not answer_tokens else 100.0 * len(answer_tokens & context_tokens) / len(answer_tokens)
        return Performance(score=score, metric="Answer-evidence overlap")


class QueryAnswerAlignment(CustomMetric):
    def evaluate(self, query: str, answer: str) -> Performance:
        query_tokens = _tokens(query)
        answer_tokens = _tokens(answer)
        score = 0.0 if not query_tokens else 100.0 * len(query_tokens & answer_tokens) / len(query_tokens)
        return Performance(score=score, metric="Query-answer alignment")


class UnavailableEvaluatorProbe(CustomMetric):
    """Acceptance-only probe for verifying honest not-evaluated rendering."""

    def evaluate(self, answer: str) -> Performance:
        return Performance(metric="Unavailable evaluator probe", _eval=False)


def containers():
    mode = os.getenv("RAGANG_DEMO_MODE", "focused")
    generation_metrics = [
        AnswerEvidenceOverlap(["retrieval.ret_docs", "generation.gen"]),
    ]
    if os.getenv("RAGANG_DEMO_INCLUDE_NOT_EVALUATED", "0") == "1":
        generation_metrics.append(UnavailableEvaluatorProbe(["generation.gen"]))
    return [
        RAGContainer(
            flow_id="local_demo",
            modules=[
                QueryInput("starter", metrics=None, is_starter=True),
                LocalTextRetriever(
                    "retrieval",
                    linker=Linker("starter"),
                    mode=mode,
                    metrics=[QueryContextCoverage(["starter.query", "retrieval.ret_docs"])],
                ),
                EvidenceBoundAnswer(
                    "generation",
                    linker=Linker("retrieval"),
                    metrics=generation_metrics,
                ),
            ],
            e2e_metrics=[QueryAnswerAlignment(["starter.query", "generation.gen"])],
        )
    ]
