from dataclasses import dataclass
from typing import List
from enum import Enum

class QueryType(Enum):
    SIMPLE = "simple"
    COMPLEX_MULTI = "complex_multi"
    COMPLEX_COND = "complex_cond"
    COMPLEX_COMP = "complex_comp"

@dataclass
class Chunk:
    chunk_idx: int
    doc_idx: int
    page_idx: int
    para_idx: int
    sentence_idx: int
    text: str

@dataclass
class Query:
    query: str
    type: QueryType
    reference: list[int] | None

@dataclass
class Scenario:
    persona: str
    scenarios: List[str]

@dataclass
class Explanation:
    index : int
    explanation: str
    keywords: List[str]
    related_chunks: List[int]

@dataclass
class DocSummary:
    docExplanation: Explanation
    pageExplanations: list[Explanation]