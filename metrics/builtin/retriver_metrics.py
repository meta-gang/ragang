from typing import List, Any
import numpy as np
from scipy.stats import kendalltau
from sklearn.metrics.pairwise import cosine_similarity
from common.bases.abstracts.base_module import BaseMetric
from common.bases.datas.performance_dataclass import Performance

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
    """평가 결과의 표준 형식을 정의하는 클래스"""
    def __init__(self, score: float, unit: str, metric: str):
        self.score = score
        self.unit = unit
        self.metric = metric

    def __repr__(self):
        return f"Performance(score={self.score}, unit='{self.unit}', metric='{self.metric}')"



# Keyword Matching
class KeywordMatchingMetric(BaseMetric):
    """
    Keyword Matching 평가 : 단순히 쿼리 & 문서 간 키워드 매칭 비율의 평균 (= 쿼리 단어가 각 문서 별로 차지하는 비율의 평균)
    
    방법:
        * ( 쿼리와 문서에서 동일한 토큰 수 / 토큰화된 문서의 길이 )의 평균
        * % 값이 높을수록 쿼리와 문서 간 키워드 매칭이 잘 이루어짐
    
    Parameters
    ----------
    query : str
        사용자 쿼리 (예: "어느 지역 사과가 제일 맛있어?")

    retrieved_documents : List[str]
        검색 시스템이 반환한 문서 별 텍스트 리스트 (예: ["충주 사과가 아주 맛있다.", "집앞 가게에서 산 사과가 맛있더라.", ...])

    Returns
    -------
    Performance
        Keyword Matching 점수를 담은 Performance 객체
    """
    def evaluate(self, query: str, retrieved_documents: list[str]) -> Performance:
        # 검색된 문서가 없는 경우, Performance 점수 = 0
        if not retrieved_documents:
            return Performance(score=0.0, unit=' There is no retrieved document', metric='Embedding Similarity Metric')
        
        tokenized_query = set(query.split())
        scores = []

        for doc in retrieved_documents:
            tokenized_doc = doc.split()

            if not tokenized_doc:
                continue  # 빈 문서 무시
            
            matched_word_cnt = sum(1 for token in tokenized_doc if token in tokenized_query)
            score_per_doc = matched_word_cnt / len(tokenized_doc)
            scores.append(score_per_doc)

        score = sum(scores) / len(scores) * 100 if scores else 0.0
        return Performance(score=score, unit='%', metric='Keyword Matching Metric')



# Jaccard Similarity
class JaccardSimilarityMetric(BaseMetric):
    """
    Jaccard 유사도 평가 : 쿼리와 문서 별 토큰의 교집합 / 쿼리와 문서 별 토큰의 합집합
    
    방법:
        * ( 토큰화 된 쿼리와 토큰화 된 문서 별 토큰 중 교집합 토큰의 개수 / 토큰화 된 쿼리와 토큰화 된 문서 별 토큰 중 합집합 토큰의 개수 )의 평균
        * % 값이 높을수록 쿼리와 문서 간 Jaccard 유사도가 높음
        * Keyword Matching이 문서 토큰에 대한 쿼리 토큰의 일치 비율의 평균이었다면, 자카드 유사도는 문서 토큰과 쿼리 토큰의 합집합에 대한 문서 토큰과 쿼리 토큰의 교집합의 비율임
    
    Parameters
    ----------
    query : str
        사용자 쿼리 (예: "어느 지역 사과가 제일 맛있어?")

    retrieved_documents : List[str]
        검색 시스템이 반환한 문서 별 텍스트 리스트 (예: ["충주 사과가 아주 맛있다.", "집앞 가게에서 산 사과가 맛있더라.", ...])

    Returns
    -------
    Performance
        Jaccard 유사도 점수를 담은 Performance 객체
    """
    def evaluate(self, query: str, retrieved_documents: list[str]) -> Performance:
        if not retrieved_documents:
            return Performance(score=0.0, unit=' There is no retrieved document', metric='Jaccard Similarity Metric')

        # 쿼리 토큰화
        tokenized_query = set(query.split())
        scores = []

        for doc in retrieved_documents:
            tokenized_doc = set(doc.split())
            if not tokenized_doc:
                continue

            # 자카드 유사도 계산: 쿼리 & 문서 별 토큰의 교집합 / 쿼리 & 검색된 문서 별 토큰의 합집합
            intersection = tokenized_query & tokenized_doc
            union = tokenized_query | tokenized_doc
            score_per_doc = len(intersection) / len(union) if union else 0.0
            scores.append(score_per_doc)

        avg_score = sum(scores) / len(scores) * 100 if scores else 0.0
        return Performance(score=avg_score, unit='%', metric='Jaccard Similarity Metric')
    


# Cosine Similarity: 쿼리 & 문서 간 임베딩 코사인 유사도의 평균
# 가정1. 사용자가 get_embedding()을 쓰던 어떤 방법을 써서 매개변수로 해당 벡터가 담긴 넘파이 배열 전달 가정
# 가정2. 쿼리와 문서가 동일한 임베딩 모델로 벡터화 된 상태로, 서로의 벡터 크기가 동일
class CosineSimilarityMetric(BaseMetric):
    """
    Cosine 유사도 평가 : 쿼리와 문서 임베딩 벡터 간 코사인 유사도의 평균
    
    방법:
        * ( 임베딩 된 쿼리와 임베딩 된 문서 별 코사인 유사도 값 )의 평균
        * Cosine 유사도 값이 높을수록 쿼리와 문서 간 관련 정도가 높음
    
    Parameters
    ----------
    query : np.ndarray
        사용자 쿼리의 벡터 임베딩 (예: [1.01, 0.9, -0.1])

    retrieved_documents : List[np.ndarray]
        검색 시스템이 반환한 문서 별 텍스트의 벡터 임베딩 (예: [[1.01, 0.9, -0.1], [0.05, 2.8, -3.1]])

    Returns
    -------
    Performance
        Cosine 유사도 점수를 담은 Performance 객체
    """
    def evaluate(self, query: np.ndarray, retrieved_documents: list[np.ndarray]) -> Performance:
        # 검색된 문서가 없는 경우, Performance 점수 = 0
        if not retrieved_documents:
            return Performance(score=0.0, unit=' There is no retrieved document', metric='Embedding Similarity Metric')

        # score = 쿼리 & 문서 간 코사인 유사도 평균
        scores = [self.cosine_similarity(query, doc) for doc in retrieved_documents]
        score = sum(scores) / len(scores) if scores else 0.0
        return Performance(score=score, unit=' (-1 ~ 1)', metric='Embedding Similarity Metric')
    
    # 코사인 유사도 계산 함수
    def cosine_similarity(self, vec_a, vec_b):
        dot_product = sum(a * b for a, b in zip(vec_a, vec_b))
        norm_a = sum(a ** 2 for a in vec_a) ** 0.5
        norm_b = sum(b ** 2 for b in vec_b) ** 0.5
        return dot_product / (norm_a * norm_b) if norm_a and norm_b else 0.0
    


# Euclidean Distance: 쿼리 & 문서 간 유클리드 거리의 평균
# 가정1. 사용자가 get_embedding()을 쓰던 어떤 방법을 써서 매개변수로 해당 벡터가 담긴 넘파이 배열 전달 가정
# 가정2. 쿼리와 문서가 동일한 임베딩 모델로 벡터화 된 상태로, 서로의 벡터 크기가 동일
class EuclideanDistanceMetric(BaseMetric):
    def evaluate(self, query: np.ndarray, retrieved_documents: list[np.ndarray]) -> Performance:
        # 검색된 문서가 없는 경우
        if not retrieved_documents:
            return Performance(score=0.0, unit=' There is no retrieved document', metric='Euclidean Distance Metric')

        # score = 쿼리 & 문서 간 유클리드 거리 평균
        scores = [self.euclidean_distance(query, doc) for doc in retrieved_documents]
        score = float(np.mean(scores)) if scores else 0.0
        return Performance(score=score, unit='', metric='Euclidean Distance Metric')

    def euclidean_distance(self, vec_a: np.ndarray, vec_b: np.ndarray) -> float:
        return float(np.linalg.norm(vec_a - vec_b))
    


# Manhattan Distance: 쿼리 & 문서 간 맨하탄 거리의 평균(고차원 벡터에 더 적합)
# 가정1. 사용자가 get_embedding()을 쓰던 어떤 방법을 써서 매개변수로 해당 벡터가 담긴 넘파이 배열 전달 가정
# 가정2. 쿼리와 문서가 동일한 임베딩 모델로 벡터화 된 상태로, 서로의 벡터 크기가 동일
class ManhattanDistanceMetric(BaseMetric):
    def evaluate(self, query: np.ndarray, retrieved_documents: list[np.ndarray]) -> Performance:
        # 검색된 문서가 없는 경우
        if not retrieved_documents:
            return Performance(score=0.0, unit=' There is no retrieved document', metric='Manhattan Distance Metric')
        
        # score = 쿼리 & 문서 간 맨하탄 거리 평균
        scores = [self.manhattan_distance(query, doc) for doc in retrieved_documents]
        score = float(np.mean(scores)) if scores else 0.0
        return Performance(score=score, unit='', metric='Manhattan Distance Metric')
    
    def manhattan_distance(self, vec_a: np.ndarray, vec_b: np.ndarray) -> float:
        return float(np.sum(np.abs(vec_a - vec_b)))


# Negative Rejection Rate: 쿼리와 무관한(코사인 유사도 <= 0) 문서의 비율
# 가정1. 사용자가 get_embedding()을 쓰던 어떤 방법을 써서 매개변수로 해당 벡터가 담긴 넘파이 배열 전달 가정
# 가정2. 쿼리와 문서가 동일한 임베딩 모델로 벡터화 된 상태로, 서로의 벡터 크기가 동일
class NegativeRejectionRateMetric(BaseMetric):
    def evaluate(self, query: np.ndarray, retrieved_documents: list[np.ndarray])-> Performance:
        # 검색된 문서가 없는 경우
        if not retrieved_documents:
            return Performance(score=0.0, unit=' There is no retrieved document', metric='Negative Rejection Rate Metric')

        # score = 쿼리와 무관한 retrieved_documents의 비율
        # 코사인 유사도 <= 0인 문서는 관련없으므로 해당 문서들의 비율 백분율 계산
        # 쿼리와 관련 없는 문서 수 / 전체 문서 수 * 100
        irr_documents=0
        for doc in retrieved_documents:
            if self.cosine_similarity(query, doc) <= 0:
                irr_documents += 1

        score = (irr_documents / len(retrieved_documents))*100 if retrieved_documents else 0.0

        return Performance(score=score, unit='%', metric='Negative Rejection Rate Metric')
    
    # 코사인 유사도 계산 함수
    def cosine_similarity(self, vec_a, vec_b):
        dot_product = sum(a * b for a, b in zip(vec_a, vec_b))
        norm_a = sum(a ** 2 for a in vec_a) ** 0.5
        norm_b = sum(b ** 2 for b in vec_b) ** 0.5
        return dot_product / (norm_a * norm_b) if norm_a and norm_b else 0.0



def ranking_consistency_kendall_tau(ranking1: List[int], ranking2: List[int]) -> Performance:
    """
    랭킹 일관성 평가 (Kendall's Tau) : 두 개의 랭킹 리스트(ex. 정답 랭킹, 모델이 반환한 랭킹) 간의 순위 일관성을 켄달 타우(Kendall's Tau) 계수로 계산
    방법 :
        * 두 리스트의 순서쌍을 비교하여, 순서가 일치하는 쌍(동의쌍)과 불일치하는 쌍(불일치쌍)의 비율을 계산한다.
        * 켄달 타우 계수는 -1에서 1 사이의 값을 가지며, 1에 가까울수록 두 랭킹이 일치함을 의미한다.
    사용 예 : 검색 결과의 랭킹 품질을 평가할 때 사용한다.
    Parameters
    ----------
    ranking1 : List[int]
        첫 번째 랭킹 리스트 (예: [1, 2, 3, 4])
    ranking2 : List[int]
        두 번째 랭킹 리스트 (예: [1, 3, 2, 4])

    Returns
    -------
    Performance : 계산된 켄달 타우 점수를 담은 Performance 객체
    """
    tau, _ = kendalltau(ranking1, ranking2)
    return Performance(score=tau, unit='', metric='Kendall\'s Tau')

def diversity_metric(doc_embeddings: List[np.ndarray]) -> Performance:
    """
    결과 다양성 평가 (예시: 문서 내 중복 단어/문장 비율, 토픽 다양성 등) : 검색된 문서들의 임베딩을 이용해, 결과가 얼마나 다양한지 평가
    
    방법 :
        * 모든 문서 임베딩 쌍의 코사인 유사도를 계산
        * 평균 유사도를 구한 뒤, 1 - 평균 유사도로 다양성 점수를 산출
        * 값이 1에 가까울수록 문서들이 서로 다르다는 의미(다양성이 높음)
    사용 예 : 검색 결과가 한쪽에 치우치지 않고 다양한 주제를 포함하는지 평가할 때 사용
    
    Parameters
    ----------
    doc_embeddings : List[np.ndarray]
        검색된 각 문서의 임베딩 벡터 리스트

    Returns
    -------
    Performance
        계산된 다양성 점수를 담은 Performance 객체
    """
    
    """
    # (단순 텍스트 기반 비교 - 매개변 수 retrieved_documents: List[str] 받아와야 함)
    # # TODO: 실제 다양성 평가 로직 구현 (예: 토픽 모델링, 유사도 기반 다양성) 
    # unique_docs = set(retrieved_documents)
    # diversity_score = len(unique_docs) / len(retrieved_documents) if retrieved_documents else 0
    # return Performance(score=diversity_score, unit='', metric='Diversity')
    """
    
    # 문서가 2개 미만이면 다양성을 측정할 수 없음
    if len(doc_embeddings) < 2:
        return Performance(score=0.0, unit='', metric='Diversity')

    # 모든 문서 쌍 간의 코사인 유사도 계산
    similarity_matrix = cosine_similarity(doc_embeddings)
    
    # 대각선(자기 자신과의 유사도=1)을 제외한 상삼각행렬의 평균을 계산
    # 이는 모든 문서 쌍의 유사도 평균과 같음
    indices = np.triu_indices(len(doc_embeddings), k=1)
    mean_similarity = np.mean(similarity_matrix[indices])
    
    # 다양성 점수는 (1 - 평균 유사도)로 정의
    diversity_score = 1 - mean_similarity
    
    return Performance(score=diversity_score, unit='', metric='Diversity')


def random_document_injection_effect(query: str, retrieved_documents: List[str], ground_truth: List[str]) -> Performance:
    """
    검색 결과에 무작위(관련없는) 문서를 삽입했을 때 정밀도(Precision)가 얼마나 하락하는지 측정한다.
    이 점수가 낮을수록 무작위 문서(노이즈)에 강건하다는 의미!
    
    방법:
        * 원래 검색 결과의 정밀도를 계산
        * 무작위 문서를 추가한 뒤 정밀도를 다시 계산
        * 두 점수의 차이(하락폭)를 반환
        * 값이 작을수록(0에 가까울수록) 시스템이 노이즈에 강건함을 의미
    사용 예 : 검색 시스템의 노이즈(무관한 문서) 내성 평가

    Parameters
    ----------
    query : str
        사용자 쿼리 (현재 로직에서는 미사용, 확장성을 위해 유지)
    retrieved_documents : List[str]
        원본 검색 결과 문서 리스트
    ground_truth : List[str]
        실제 정답 문서 리스트

    Returns
    -------
    Performance
        성능 하락폭(effect) 점수를 담은 Performance 객체
    """
    original_precision = precision_metric(retrieved_documents, ground_truth)
    
    # 무작위 문서 삽입
    random_doc = "이것은 시스템 테스트를 위한 무작위로 삽입된 관련 없는 문서입니다."
    injected_docs = retrieved_documents + [random_doc]
    
    injected_precision = precision_metric(injected_docs, ground_truth)
    
    effect = original_precision.score - injected_precision.score
    return Performance(score=effect, unit='', metric='Random Doc Injection Effect')

def precision_metric(retrieved_documents: List[str], ground_truth: List[str]) -> Performance:
    """
    정밀도 평가 : 얼마나 많은 검색된 문서가 실제로 정답에 해당하는지를 평가
    
    방법:
        * 정답 문서 수 / 검색된 문서 수
        * 값이 1에 가까울수록 검색 결과가 정확함을 의미
    사용 예 : 검색 시스템의 정확도를 평가할 때 사용
    
    Parameters
    ----------
    retrieved_documents : List[str]
        검색 시스템이 반환한 문서(또는 ID)의 리스트
    ground_truth : List[str]
        실제 정답에 해당하는 문서(또는 ID)의 리스트

    Returns
    -------
    Performance
        계산된 정밀도 점수를 담은 Performance 객체
    """
    if not retrieved_documents:
        return Performance(score=0.0, unit='', metric='Precision')
    
    relevant_items = set(retrieved_documents) & set(ground_truth)
    precision = len(relevant_items) / len(retrieved_documents)
    return Performance(score=precision, unit='', metric='Precision')

def generalized_embedding_coverage_error(query_embedding: np.ndarray, doc_embeddings: List[np.ndarray]) -> Performance:
    """
    GECE: Query와 Retrieval이 서로 골고루 덮고 있는가
    원리 : 쿼리 임베딩과 검색된 문서 임베딩들 간의 평균 유클리드 거리를 계산하여, 검색 결과가 쿼리와 얼마나 가까운지(커버리지)를 평가합니다.
    방법:
        * 각 문서 임베딩과 쿼리 임베딩의 거리를 모두 구해 평균을 낸다.
        * 값이 작을수록 검색 결과가 쿼리와 가깝다는 의미(커버리지가 좋음)
    사용 예: 임베딩 공간에서 쿼리와 검색 결과의 근접성 평가.
    Parameters
    ----------
    query_embedding : np.ndarray
        쿼리의 임베딩 벡터
    doc_embeddings : List[np.ndarray]
        검색된 각 문서의 임베딩 벡터 리스트

    Returns
    -------
    Performance
        계산된 평균 거리(coverage_error)를 담은 Performance 객체
    """
    if not doc_embeddings:
        return Performance(score=0.0, unit='distance', metric='GECE')
        
    distances = [np.linalg.norm(query_embedding - doc_emb) for doc_emb in doc_embeddings]
    coverage_error = np.mean(distances)
    return Performance(score=coverage_error, unit='distance', metric='GECE')

def embedding_consine_similarity_evaluation(query_embedding: np.ndarray, doc_embeddings: List[np.ndarray]) -> Performance:
    """
    임베딩 코사인 유사도 기반 공간 커버러지/균일성 평가 : 쿼리 임베딩과 검색된 문서 임베딩들 간의 코사인 유사도를 기반으로, 검색 결과의 일관성과 커버리지를 평가한다.
    방법:
        * 쿼리 임베딩과 각 문서 임베딩의 코사인 유사도를 모두 계산
        * 가장 높은 유사도(local)와 전체 평균 유사도(high)를 구해, 두 값을 평균내어 반환
        * 값이 1에 가까울수록 쿼리와 검색 결과가 임베딩 공간에서 잘 맞닿아 있음을 의미
    사용 예 : 임베딩 기반 검색 시스템의 일관성 및 커버리지 평가.
    Parameters
    ----------
    query_embedding : np.ndarray
        쿼리의 임베딩 벡터
    doc_embeddings : List[np.ndarray]
        검색된 각 문서의 임베딩 벡터 리스트

    Returns
    -------
    Performance
        계산된 일관성 점수를 담은 Performance 객체
    """
    if not doc_embeddings:
        return Performance(score=0.0, unit='cosine_similarity', metric='Embedding Consistency E')

    sims = cosine_similarity([query_embedding], doc_embeddings)[0]
    local_score = np.max(sims)  # 가장 가까운 문서와의 유사도
    high_score = np.mean(sims)  # 전체 문서와의 평균 유사도
    
    final_score = (local_score + high_score) / 2
    return Performance(score=final_score, unit='cosine_similarity', metric='Embedding Consistency E')