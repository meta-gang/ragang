"""Offline graph execution examples; extractive text is not an LLM quality benchmark.

``linear`` runs one lexical retriever. ``hybrid_cycle`` merges lexical and
graph-neighborhood retrieval, drafts an answer, and performs one explicit
verification/rewrite pass. ``graph_module`` wraps a small bounded graph traversal
as one retriever module. No gold answers, paid APIs, or databases are required.
"""

from pathlib import Path
import re

from ragang.container import RAGContainer
from ragang.core.bases.datas.linker import Linker
from ragang.core.bases.datas.performance import Performance
from ragang.metrics.custom import CustomMetric
from ragang.modules.custom import CustomModule
from ragang.modules.retrieval_module import RetrievalModule


DOCS = Path(__file__).resolve().parent / "datas/docs"


def terms(text):
    return set(re.findall(r"[0-9A-Za-z가-힣]+", text.casefold()))


def documents():
    return {path.stem: path.read_text(encoding="utf-8") for path in sorted(DOCS.glob("*.txt"))}


def excerpt(ret_docs):
    if not ret_docs:
        return "검색된 근거가 없어 답변할 수 없습니다."
    return "로컬 문서 발췌:\n" + "\n".join(" ".join(doc.split())[:280] for doc in ret_docs)


class QueryInput(CustomModule):
    async def execute(self, query):
        return {"query": query, "current_query": query, "round": 0}


class SearchRouter(CustomModule):
    async def execute(self, current_query, round):
        return {"current_query": current_query, "round": round, "next": ["keyword", "graph_search"]}


class KeywordRetriever(RetrievalModule):
    def __init__(self, module_id, linker, metrics=None):
        super().__init__(module_id, linker, metrics)
        self.documents = documents()
        self.top_k = 1

    async def execute(self, current_query, round):
        scores = [(len(terms(current_query) & terms(text)), name, text) for name, text in self.documents.items()]
        ranked = sorted(scores, key=lambda item: (-item[0], item[1]))
        selected = [(name, text) for score, name, text in ranked[:self.top_k] if score > 0]
        texts = [text for _, text in selected]
        return {"query": self.lazy_state.query, "current_query": current_query,
                "ret_docs": texts, "ret_docs_keyword": texts,
                "round_keyword": round, "document_ids": [name for name, _ in selected]}


class GraphNeighborhoodRetriever(RetrievalModule):
    """Actual two-hop traversal over an explicit, user-supplied document graph.

    Edges below are example input relationships, not inferred or validated
    knowledge-graph facts. The module reports observed traversal only.
    """
    def __init__(self, module_id, linker, metrics=None):
        super().__init__(module_id, linker, metrics)
        self.documents = documents()
        self.edges = {"deployment": ["operations"], "operations": ["rollback"], "rollback": []}
        self.max_hops = 2

    async def execute(self, current_query, round):
        ranked = sorted(self.documents, key=lambda name: (-len(terms(current_query) & terms(self.documents[name])), name))
        if not ranked or not terms(current_query) & terms(self.documents[ranked[0]]):
            return {"ret_docs": [], "ret_docs_graph": [], "round_graph": round,
                    "retrieved_node_ids": [], "traversed_edges": []}
        pending, seen, traversed = [(ranked[0], 0)], [], []
        while pending:
            node, depth = pending.pop(0)
            if node in seen:
                continue
            seen.append(node)
            if depth >= self.max_hops:
                continue
            for target in self.edges.get(node, []):
                if target in self.documents:
                    traversed.append([node, target])
                    pending.append((target, depth + 1))
        texts = [self.documents[node] for node in seen]
        return {"ret_docs": texts, "ret_docs_graph": texts, "round_graph": round,
                "retrieved_node_ids": seen, "traversed_edges": traversed}


class MergeEvidence(CustomModule):
    async def execute(self, query, current_query, ret_docs_keyword, ret_docs_graph, round_keyword, round_graph):
        if round_keyword != round_graph:
            raise ValueError("The demo requires both retrievers to belong to the same router pass")
        return {"query": query, "current_query": current_query, "round": round_keyword,
                "ret_docs": list(dict.fromkeys([*ret_docs_keyword, *ret_docs_graph]))}


class DraftAnswer(CustomModule):
    async def execute(self, query, current_query, round, ret_docs):
        return {"query": query, "current_query": current_query, "round": round,
                "ret_docs": ret_docs, "gen": excerpt(ret_docs)}


class VerificationPolicy(CustomModule):
    """One deterministic extra pass demonstrates control flow, not correctness.

    A production critic should implement its own explicit evidence/acceptance
    policy. This example never calls the extra pass a quality improvement.
    """
    async def execute(self, query, current_query, round, ret_docs, gen):
        if round < 1:
            return {"current_query": query + " 절차 점검", "round": round + 1, "next": ["router"]}
        return {"gen": gen, "next": ["final"]}


class FinalAnswer(CustomModule):
    async def execute(self, gen):
        return {"gen": gen, "terminal": True}


class KeywordAnswer(CustomModule):
    async def execute(self, ret_docs_keyword):
        return {"gen": excerpt(ret_docs_keyword)}


class GraphAnswer(CustomModule):
    async def execute(self, ret_docs):
        return {"gen": excerpt(ret_docs)}


class DocumentCount(CustomMetric):
    def evaluate(self, ret_docs):
        return Performance(score=len(ret_docs), unit="documents", metric="Observed document count")


class AnswerEvidenceOverlap(CustomMetric):
    def evaluate(self, ret_docs, answer):
        answer_terms = terms(answer)
        if not ret_docs or not answer_terms:
            return Performance(unit="0 to 1", metric="Extractive evidence overlap", _eval=False,
                               failure={"type": "insufficient_input", "message": "No retrieved evidence to compare"})
        overlap = len(answer_terms & terms(" ".join(ret_docs))) / len(answer_terms)
        return Performance(score=overlap, unit="0 to 1", metric="Extractive evidence overlap",
                           scope={"documents_total": len(ret_docs), "documents_evaluated": len(ret_docs)})


def containers():
    linear = RAGContainer("linear", [
        QueryInput("starter", is_starter=True),
        KeywordRetriever("keyword", Linker("starter"), [DocumentCount(["keyword.ret_docs"])]),
        KeywordAnswer("answer", linker=Linker("keyword"),
                      metrics=[AnswerEvidenceOverlap(["keyword.ret_docs", "answer.gen"])]),
    ], max_steps=8)
    cycle = RAGContainer("hybrid_cycle", [
        QueryInput("starter", is_starter=True),
        SearchRouter("router", linker=Linker("starter") | Linker("critic")),
        KeywordRetriever("keyword", Linker("router"), [DocumentCount(["keyword.ret_docs"])]),
        GraphNeighborhoodRetriever("graph_search", Linker("router"), [DocumentCount(["graph_search.ret_docs"])]),
        MergeEvidence("merge", linker=Linker("keyword") & Linker("graph_search"),
                      metrics=[DocumentCount(["merge.ret_docs"])]),
        DraftAnswer("draft", linker=Linker("merge"),
                    metrics=[AnswerEvidenceOverlap(["merge.ret_docs", "draft.gen"])]),
        VerificationPolicy("critic", linker=Linker("draft")),
        FinalAnswer("final", linker=Linker("critic")),
    ], max_steps=20)
    graph = RAGContainer("graph_module", [
        QueryInput("starter", is_starter=True),
        GraphNeighborhoodRetriever("graph_search", Linker("starter"), [DocumentCount(["graph_search.ret_docs"])]),
        GraphAnswer("answer", linker=Linker("graph_search"),
                    metrics=[AnswerEvidenceOverlap(["graph_search.ret_docs", "answer.gen"])]),
    ], max_steps=8)
    return [linear, cycle, graph]
