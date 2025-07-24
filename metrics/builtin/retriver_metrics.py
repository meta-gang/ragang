from typing import List, Any
import numpy as np
from scipy.stats import kendalltau


"""
input 데이터: 쿼리와 검색된 문서 모두 평가 진행 전에 텍스트 전처리(특수문자 제거, 공백 개수 통일, 불용어 제거, 어간 추출, 토큰화 등) 돼 있어야 함
    query,
    retrieved_documents["문서1 텍스트", "문서2 텍스트", "문서3 텍스트"...], <- [['문서1'], [['문서2']], [['문서3']] 식으로 문서 단위로 묶으려 했으나 쿼리에 관련된 청크 텍스트만 뽑아오면 되므로 전자로 하는게 좋을 듯

<짚고 넘어가야할 점>
1. 텍스트 전처리 함수 구현 or 사용자가 이미 전처리했다고 믿고 전처리 함수 구현 없이 진행
2. 쿼리와 그에 따른 검색 문서는 사용자가 사전에 임베딩 모델로 벡터로 만든 것인지 아니면 '원래의 텍스트 쿼리'와 '원본 문서 텍스트'라고 가정하는게 맞는지?


output 데이터 : metric 결과(정답률, recall, precision 등 원하는 평가 지표의 값)
    return Performance(score=0.78, unit='', metric='LLM as a judge')

"""
class Performance:
    def __init__(self, score: float, unit: str, metric: str):
        self.score = score
        self.unit = unit
        self.metric = metric

    def __repr__(self):
        return f"Performance(score={self.score}, unit='{self.unit}', metric='{self.metric}')"

def ranking_consistency_kendall_tau(ranking1: List[int], ranking2: List[int]) -> Performance:
    """
    랭킹 일관성 평가 (Kendall's Tau)
    ranking1, ranking2: 각 문서의 랭킹 리스트 (ex. [1,2,3])
    """
    tau, _ = kendalltau(ranking1, ranking2)
    return Performance(score=tau, unit='', metric='Kendall\'s Tau')

def diversity_metric(retrieved_documents: List[str]) -> Performance:
    """
    결과 다양성 평가 (예시: 문서 내 중복 단어/문장 비율, 토픽 다양성 등)
    """
    # TODO: 실제 다양성 평가 로직 구현 (예: 토픽 모델링, 유사도 기반 다양성)
    unique_docs = set(retrieved_documents)
    diversity_score = len(unique_docs) / len(retrieved_documents) if retrieved_documents else 0
    return Performance(score=diversity_score, unit='', metric='Diversity')

def random_document_injection_effect(query: str, retrieved_documents: List[str], ground_truth: List[str]) -> Performance:
    """
    무작위 문서 삽입 시 성능 변화 평가
    """
    # 기존 성능
    original_precision = precision_metric(retrieved_documents, ground_truth)
    # 무작위 문서 삽입
    random_doc = "무작위 문서 텍스트"
    injected_docs = retrieved_documents + [random_doc]
    injected_precision = precision_metric(injected_docs, ground_truth)
    effect = original_precision.score - injected_precision.score    # 차이가 작으면 무작위 문서가 성능에 큰 영향을 미치지 않음
    return Performance(score=effect, unit='', metric='Random Doc Injection Effect')

def precision_metric(retrieved_documents: List[str], ground_truth: List[str]) -> Performance:
    """
    정밀도 평가 : 얼마나 많은 검색된 문서가 실제로 정답에 해당하는지를 평가
    """
    # retrived_documents : 검색된 문서, ground_truth: 정답 문서
    relevant = set(retrieved_documents) & set(ground_truth) 
    # precision : retrieved_documents에서 ground_truth에 있는 문서의 비율
    precision = len(relevant) / len(retrieved_documents) if retrieved_documents else 0
    return Performance(score=precision, unit='', metric='Precision')

def generalized_embedding_coverage_error(query_embedding: np.ndarray, doc_embeddings: List[np.ndarray]) -> Performance:
    """
    GECE: Query와 Retrieval이 서로 골고루 덮고 있는가
    """
    # TODO: 실제 GECE 계산 로직 구현
    # 예시: 평균 거리 기반 커버리지
    
    # query_embedding과 각 문서 임베딩 간의 거리 계산
    distances = [np.linalg.norm(query_embedding - doc_emb) for doc_emb in doc_embeddings]   
    coverage_error = np.mean(distances)
    return Performance(score=coverage_error, unit='', metric='GECE')

def embedding_consine_similarity_evaluation(query_embedding: np.ndarray, doc_embeddings: List[np.ndarray]) -> Performance:
    """
    임베딩 코사인 유사도 기반 공간 커버러지/균일성 평가
    """
    # TODO: 실제 코사인 유사도 기반 평가 로직 구현
    from sklearn.metrics.pairwise import cosine_similarity
    sims = cosine_similarity([query_embedding], doc_embeddings)[0]
    local_score = np.max(sims)  # 가장 가까운 문서
    high_score = np.mean(sims)  # 전체 평균
    # 반환 예시: local/high 평균값
    return Performance(score=(local_score + high_score) / 2, unit='', metric='Embedding Consistency E')