from dataclasses import dataclass
from typing import List
from enum import Enum

class QueryType(Enum):
    SIMPLE_SEARCH = "simple_search" # 단순 정보 검색    ex. "사내 '프로젝트 제우스'의 최근 주간 보고서에서 언급된 주요 리스크 3가지는?"
    SIMPLE_EXPLN = "simple_expln"   # 단순 정보 검색 & 설명     ex. "알파-7 카메라의 펌웨어 2.1 업데이트로 개선된 기능은 뭐야?"
    SIMPLE_TF = "simple_tf"         # 단순 정보 검색 & 참거짓 진술 비교     ex. "애플의 최신 스마트폰이 아이폰 15이라던데, 맞아?"
    COMPLEX_MULTI = "complex_multi" # 복잡한 멀티홉 쿼리    ex. "2025년 3분기 우리 회사 마케팅 캠페인 중 가장 ROI가 높았던 캠페인은 무엇이며, 주요 성공 요인은?"
    COMPLEX_COMP = "complex_comp"   # 복수의 정보 비교  ex. "경쟁사 제품 'X-Widget'과 우리 'Y-Widget'의 기능 차이점을 비교해줘."
    COMPLEX_INFER = "complex_infer" # 필요한 정보 검색 & 추론   ex. "최근 3개월간 'A사'의 주가 변동에 영향을 미친 주요 뉴스 이벤트는 무엇이야?"
    COMPLEX_COND = "complex_cond"   # 조건을 만족하는 정보 검색 & 선별  ex. "우리 소프트웨어 설치 매뉴얼에서 '도커(Docker)를 이용한 설치' 부분만 찾아서 단계별로 설명해 줘."

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