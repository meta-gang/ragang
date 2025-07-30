"""Retriever 성능 평가를 위한 메트릭 클래스를 정의하는 모듈입니다.

이 모듈의 메트릭들은 텍스트 기반, 임베딩 기반, 정답 데이터셋(Ground Truth) 기반 등
다양한 방식으로 Retriever의 성능을 측정합니다.

모듈 설계 노트
==============

.. note:: **Input 데이터 형식**

    모든 메트릭은 텍스트 데이터가 사전에 전처리되었다고 가정합니다.
    (특수문자 제거, 불용어 제거, 토큰화 등)

    - **query**: 단일 텍스트 문자열
    - **ret_docs**: 문서 텍스트들의 리스트
      (예: ``["문서1 텍스트", "문서2 텍스트", ...]``)

.. note:: **Output 데이터 형식**

    모든 메트릭은 ``Performance`` 데이터 클래스 객체를 반환합니다.
    (예: ``Performance(score=0.78, unit='%', metric='Precision')``)


**주요 설계 고려사항**
--------------------

1.  **전처리 범위**:
    이 모듈은 텍스트 전처리 기능을 직접 구현하지 않습니다.
    평가를 수행하기 전에 사용자가 자신의 요구사항에 맞게
    데이터 전처리를 완료해야 합니다.

2.  **입력 데이터 타입**:
    메트릭의 특성에 따라 텍스트(``str``) 또는 임베딩(``np.ndarray``)을
    입력으로 받습니다. 각 클래스의 ``evaluate`` 메소드 Docstring에
    필요한 입력 타입이 명시되어 있습니다.

"""
import numpy as np
from common.bases.datas.performance_dataclass import Performance
from common.bases.abstracts.base_metric import BaseMetric
from adapters.embedding_adapter import BaseEmbeddingAdapter
from common.utils.tools import CosineSimilarity

from typing import List, Any
from scipy.stats import kendalltau
from sklearn.metrics.pairwise import cosine_similarity
import os
from dotenv import load_dotenv

# --- 공통 기반 클래스 및 어댑터 import ---
from adapters.embedding_adapter import BaseEmbeddingAdapter

class KeywordMatchingMetric(BaseMetric):
    """쿼리와 문서 간의 키워드 매칭 비율을 평가합니다.

    쿼리 토큰이 각 문서 텍스트의 토큰들과 얼마나 일치하는지 계산하고
    그 평균을 백분율로 반환합니다.
    """
    def evaluate(self, query: str, ret_docs: List[str]) -> Performance:
        """
        Keyword Matching 점수를 계산합니다.

        :param query: 사용자 원본 쿼리 텍스트
        :type query: str
        :param ret_docs: 검색된 문서 텍스트 리스트
        :type ret_docs: List[str]
        :return: Keyword Matching 점수를 담은 Performance 객체
        :rtype: Performance
        """
        if not ret_docs:
            return Performance(score=0.0, unit='%', metric='Keyword Matching Metric')
        
        tokenized_query = set(query.split())
        scores = []
        for doc in ret_docs:
            tokenized_doc = doc.split()
            if not tokenized_doc:
                continue
            
            matched_tokens = sum(1 for token in tokenized_doc if token in tokenized_query)
            score_per_doc = matched_tokens / len(tokenized_doc)
            scores.append(score_per_doc)
            
        avg_score = np.mean(scores) * 100 if scores else 0.0
        return Performance(score=avg_score, unit='%', metric='Keyword Matching Metric')


class JaccardSimilarityMetric(BaseMetric):
    """쿼리와 문서 간의 Jaccard 유사도를 평가합니다.

    쿼리와 문서 텍스트를 토큰 집합으로 보고, (쿼리와 텍스트의 교집합 토큰 수 / 쿼리와 텍스트의 합집합 토큰 수)를 계산합니다.
    검색된 모든 문서에 대한 평균 Jaccard 유사도를 백분율로 반환합니다.
    """
    def evaluate(self, query: str, ret_docs: List[str]) -> Performance:
        """
        Jaccard 유사도 점수를 계산합니다.

        :param query: 사용자 원본 쿼리 텍스트
        :type query: str
        :param ret_docs: 검색된 문서 텍스트 리스트
        :type ret_docs: List[str]
        :return: Jaccard 유사도 점수를 담은 Performance 객체
        :rtype: Performance
        """
        if not ret_docs:
            return Performance(score=0.0, unit='%', metric='Jaccard Similarity Metric')

        tokenized_query = set(query.split())
        scores = []
        for doc in ret_docs:
            tokenized_doc = set(doc.split())
            if not tokenized_doc:
                continue

            intersection = tokenized_query.intersection(tokenized_doc)
            union = tokenized_query.union(tokenized_doc)
            score_per_doc = len(intersection) / len(union) if union else 0.0
            scores.append(score_per_doc)

        avg_score = np.mean(scores) * 100 if scores else 0.0
        return Performance(score=avg_score, unit='%', metric='Jaccard Similarity Metric')


class CosineSimilarityMetric(BaseMetric):
    """쿼리와 문서 임베딩 간의 평균 코사인 유사도를 평가합니다.

    코사인 유사도는 두 벡터가 가리키는 방향의 유사성을 측정하며,
    -1에서 1 사이의 값을 가집니다. 1에 가까울수록 유사합니다.

    .. note:: 입력되는 벡터들의 크기는 서로 동일해야 합니다.
    """
    def __init__(self, embedding_adapter: BaseEmbeddingAdapter):
        """
        :param embedding_adapter: 텍스트를 임베딩 벡터로 변환할 어댑터
        :type embedding_adapter: BaseEmbeddingAdapter
        """
        self.embedding_adapter = embedding_adapter

    def evaluate(self, query: str, ret_docs: List[str]) -> Performance:
        """
        평균 코사인 유사도 점수를 계산합니다.

        :param query: 사용자 원본 쿼리 텍스트
        :type query: str
        :param ret_docs: 검색된 문서 텍스트 리스트
        :type ret_docs: List[str]
        :return: Jaccard 유사도 점수를 담은 Performance 객체
        :rtype: Performance
        """
        if not ret_docs:
            return Performance(score=0.0, unit='-1 to 1', metric='Cosine Similarity Metric')
        
        query_vec = self.embedding_adapter.create_embeddings([query])[0]
        ret_docs_vec = self.embedding_adapter.create_embeddings(ret_docs)

        similarity_scores = cosine_similarity([query_vec], ret_docs_vec)[0]

        avg_score = np.mean(similarity_scores) if similarity_scores.size else 0.0

        return Performance(score=avg_score, unit="-1 to 1", metric="Cosine Similarity Metric")


class EuclideanDistanceMetric(BaseMetric):
    """쿼리와 문서 임베딩 간의 평균 유클리드 거리를 평가합니다.

    유클리드 거리는 벡터 공간에서 두 점 사이의 직선 거리를 나타냅니다.
    값이 작을수록 두 벡터가 가깝다는 것을 의미합니다.

    .. note:: 입력되는 벡터들의 크기는 서로 동일해야 합니다.
    """
    def __init__(self, embedding_adapter: BaseEmbeddingAdapter):
        """
        :param embedding_adapter: 텍스트를 임베딩 벡터로 변환할 어댑터
        :type embedding_adapter: BaseEmbeddingAdapter
        """
        self.embedding_adapter = embedding_adapter

    def evaluate(self, query: str, ret_docs: List[str]) -> Performance:
        """
        평균 유클리드 거리를 계산합니다.

        :param query: 사용자 원본 쿼리 텍스트
        :type query: str
        :param ret_docs: 검색된 문서 텍스트 리스트
        :type ret_docs: List[str]
        :return: Jaccard 유사도 점수를 담은 Performance 객체
        :rtype: Performance
        """
        if not ret_docs:
            return Performance(score=0.0, unit='distance', metric='Euclidean Distance Metric')

        query_vec = self.embedding_adapter.create_embeddings([query])[0]
        ret_docs_vec = self.embedding_adapter.create_embeddings(ret_docs)

        distances = [np.linalg.norm(query_vec - doc_vec) for doc_vec in ret_docs_vec]
        avg_distance = np.mean(distances) if distances else 0.0
        return Performance(score=avg_distance, unit='distance', metric='Euclidean Distance Metric')


class ManhattanDistanceMetric(BaseMetric):
    """쿼리와 문서 임베딩 간의 평균 맨해튼 거리를 평가합니다.

    맨해튼 거리는 각 차원의 차이의 절댓값 합으로, 고차원 데이터에서 유용할 수 있습니다.
    값이 작을수록 두 벡터가 가깝다는 것을 의미합니다.

    .. note:: 입력되는 벡터들의 크기는 서로 동일해야 합니다.
    """
    def __init__(self, embedding_adapter: BaseEmbeddingAdapter):
        """
        :param embedding_adapter: 텍스트를 임베딩 벡터로 변환할 어댑터
        :type embedding_adapter: BaseEmbeddingAdapter
        """
        self.embedding_adapter = embedding_adapter

    def evaluate(self, query: str, ret_docs: List[str]) -> Performance:
        """
        평균 맨해튼 거리를 계산합니다.

        :param query: 사용자 원본 쿼리 텍스트
        :type query: str
        :param ret_docs: 검색된 문서 텍스트 리스트
        :type ret_docs: List[str]
        :return: Jaccard 유사도 점수를 담은 Performance 객체
        :rtype: Performance
        """
        if not ret_docs:
            return Performance(score=0.0, unit='distance', metric='Manhattan Distance Metric')
        
        query_vec = self.embedding_adapter.create_embeddings([query])[0]
        ret_docs_vec = self.embedding_adapter.create_embeddings(ret_docs)

        distances = [np.sum(np.abs(query_vec - doc_vec)) for doc_vec in ret_docs_vec]
        avg_distance = np.mean(distances) if distances else 0.0
        return Performance(score=avg_distance, unit='distance', metric='Manhattan Distance Metric')


class NegativeRejectionRateMetric(BaseMetric):
    """쿼리와 관련 없는(코사인 유사도 <= 0) 문서의 비율을 평가합니다.

    이 비율(NRR)이 낮을수록 검색 결과에 관련 없는 문서가 적게 포함되었다는 것을 의미합니다.

    .. note:: 입력되는 벡터들의 크기는 서로 동일해야 합니다.
    """
    def evaluate(self, query: str, ret_docs: List[str]) -> Performance:
        """
        NRR(Negative Rejection Rate) 점수를 백분율로 계산합니다.

        :param query: 사용자 원본 쿼리 텍스트
        :type query: str
        :param ret_docs: 검색된 문서 텍스트 리스트
        :type ret_docs: List[str]
        :return: Jaccard 유사도 점수를 담은 Performance 객체
        :rtype: Performance
        """
        if not ret_docs:
            return Performance(score=0.0, unit='%', metric='Negative Rejection Rate Metric')

        query_vec = self.embedding_adapter.create_embeddings([query])[0]
        ret_docs_vec = self.embedding_adapter.create_embeddings(ret_docs)

        similarities = cosine_similarity([query_vec], ret_docs_vec)[0]
        irrelevant_count = np.sum(similarities <= 0)
        rejection_rate = (irrelevant_count / len(ret_docs_vec)) * 100
        return Performance(score=rejection_rate, unit='%', metric='Negative Rejection Rate Metric')

class PrecisionMetric(BaseMetric):
    """정밀도(Precision)를 평가합니다.

    검색된 문서 중 실제 정답 문서의 비율을 측정합니다.
    'token' 모드(Jaccard 유사도)와 'embedding' 모드(코사인 유사도)를 지원하며,
    유사도가 지정된 임계값(threshold) 이상일 경우 정답으로 간주합니다.

    :ivar mode: 평가 모드 ('token' 또는 'embedding')
    :vartype mode: str
    :ivar threshold: 관련성을 판단하는 유사도 임계값
    :vartype threshold: float
    :ivar embedding_adapter: 'embedding' 모드에서 사용될 임베딩 어댑터
    :vartype embedding_adapter: BaseEmbeddingAdapter, optional
    """
    def __init__(self, mode: str = 'token', threshold: float = 0.5, embedding_adapter: BaseEmbeddingAdapter = None):
        """
        :param mode: 'token' 또는 'embedding' 중 평가 모드를 선택합니다. 기본값은 'token'입니다.
        :type mode: str
        :param threshold: 유사도가 이 값 이상일 때 정답으로 간주합니다. 기본값은 0.5입니다.
        :type threshold: float
        :param embedding_adapter: 'embedding' 모드에서 사용할 텍스트 임베딩 어댑터.
        :type embedding_adapter: BaseEmbeddingAdapter, optional
        :raises ValueError: 'embedding' 모드인데 embedding_adapter가 제공되지 않은 경우
        """
        if mode not in ['token', 'embedding']:
            raise ValueError("mode는 'token' 또는 'embedding'만 지원합니다.")
        if mode == 'embedding' and not embedding_adapter:
            raise ValueError("'embedding' 모드에서는 embedding_adapter가 반드시 필요합니다.")
        
        self.mode = mode
        self.threshold = threshold
        self.embedding_adapter = embedding_adapter

    def _jaccard_similarity(self, a: str, b: str) -> float:
        """두 텍스트 간의 Jaccard 유사도를 계산하는 헬퍼 함수입니다."""
        set_a, set_b = set(a.split()), set(b.split())
        intersection = set_a.intersection(set_b)
        union = set_a.union(set_b)
        return len(intersection) / len(union) if union else 0.0

    def evaluate(self, ret_docs: List[str], ground_truth: List[str]) -> Performance:
        """
        설정된 모드에 따라 정밀도 점수를 계산합니다.

        :param retrieved: 검색된 문서 텍스트 리스트
        :type retrieved: List[str]
        :param ground_truth: 정답 문서 텍스트 리스트
        :type ground_truth: List[str]
        :return: 계산된 정밀도 점수를 담은 Performance 객체
        :rtype: Performance
        """
        if not ret_docs:
            return Performance(score=0.0, unit='0 to 1', metric='Precision')
        
        relevant_count = 0
        if self.mode == 'token':
            for ret_doc in ret_docs:
                is_relevant = any(self._jaccard_similarity(ret_doc, gt_doc) >= self.threshold for gt_doc in ground_truth)
                if is_relevant:
                    relevant_count += 1
        
        elif self.mode == 'embedding':
            ret_docs_vec = self.embedding_adapter.create_embeddings(ret_docs)
            ground_truth_vec = self.embedding_adapter.create_embeddings(ground_truth)
            
            if ret_docs_vec.size == 0 or ground_truth_vec.size == 0:
                 return Performance(score=0.0, unit='0 to 1', metric='Precision')

            for ret_doc_vec in ret_docs_vec:
                sims = cosine_similarity([ret_doc_vec], ground_truth_vec)[0]
                if np.max(sims) >= self.threshold:
                    relevant_count += 1
        
        precision = relevant_count / len(ret_docs)
        return Performance(score=precision, unit='0 to 1', metric='Precision')


class RankingConsistencyKendallTau(BaseMetric):
    """두 랭킹 리스트 간의 순위 일관성을 켄달 타우(Kendall's Tau) 계수로 계산합니다.
    
    두 리스트의 모든 순서쌍을 비교하여 순서가 일치하는 쌍과 불일치하는 쌍의 비율을 계산합니다.
    결과는 -1에서 1 사이의 값을 가지며, 1에 가까울수록 두 랭킹이 일치함을 의미합니다.
    """
    def evaluate(self, ranking1: List[int], ranking2: List[int]) -> Performance:
        """
        켄달 타우 점수를 계산합니다.

        :param ranking1: 첫 번째 랭킹 리스트 (예: [1, 2, 3, 4])
        :type ranking1: List[int]
        :param ranking2: 두 번째 랭킹 리스트 (예: [1, 3, 2, 4])
        :type ranking2: List[int]
        :return: 계산된 켄달 타우 점수를 담은 Performance 객체
        :rtype: Performance
        :raises ValueError: 두 리스트의 길이가 다르거나, 계산에 필요한 최소 길이(2)보다 짧을 경우
        :raises TypeError: 리스트가 아니거나, 리스트 내에 숫자가 아닌 값이 포함되어 있을 경우
        :raises RuntimeError: 그 외 계산 중 예상치 못한 오류가 발생했을 경우
        """
        # 1. 입력값 타입 유효성 검사
        if not isinstance(ranking1, list) or not isinstance(ranking2, list):
            raise TypeError("입력값(ranking1, ranking2)은 반드시 리스트(List) 형태여야 합니다.")

        # 2. 입력값 길이 유효성 검사
        if len(ranking1) != len(ranking2):
            raise ValueError("두 랭킹 리스트의 길이가 동일해야 합니다.")
        
        if len(ranking1) < 2:
            raise ValueError("켄달 타우를 계산하려면 리스트에 최소 2개 이상의 요소가 필요합니다.")

        # 3. 켄달 타우 계산 시 발생할 수 있는 연산 오류 처리
        try:
            tau, _ = kendalltau(ranking1, ranking2)
            return Performance(score=tau, unit='-1 to 1', metric="Kendall's Tau")
        except TypeError as e:
            # 리스트 안에 숫자가 아닌 값이 포함되어 연산이 불가능한 경우 등
            raise TypeError(f"랭킹 리스트의 값 타입을 확인해주세요. 숫자만 포함되어야 합니다. 원본 오류: {e}")
        except Exception as e:
            # 그 외 scipy 연산 중 발생할 수 있는 예기치 못한 오류
            raise RuntimeError(f"켄달 타우 계산 중 예상치 못한 오류가 발생했습니다: {e}")


class DiversityMetric(BaseMetric):
    """검색된 문서들의 텍스트를 기반으로 다양성을 평가합니다.

    모든 문서 임베딩 쌍의 평균 코사인 유사도를 계산한 뒤, `1 - 평균 유사도`로 다양성 점수를 산출합니다.
    값이 1에 가까울수록 문서들이 서로 의미적으로 다르다는 것(다양성이 높음)을 의미합니다.
    """
    def __init__(self, embedding_adapter: BaseEmbeddingAdapter):
        """
        :param embedding_adapter: 텍스트를 임베딩 벡터로 변환할 어댑터
        :type embedding_adapter: BaseEmbeddingAdapter
        """
        if not isinstance(embedding_adapter, BaseEmbeddingAdapter):
            raise TypeError("embedding_adapter는 BaseEmbeddingAdapter의 인스턴스여야 합니다.")
        self.embedding_adapter = embedding_adapter

    def evaluate(self, ret_docs: List[str]) -> Performance:
        """
        다양성 점수를 계산합니다.

        :param ret_docs: 검색된 문서 텍스트 리스트
        :type ret_docs: List[str]
        :return: 계산된 다양성 점수를 담은 Performance 객체
        :rtype: Performance
        :raises ValueError: 문서 리스트의 길이가 2 미만일 경우
        :raises TypeError: 입력값이 문자열 리스트가 아닐 경우
        :raises RuntimeError: 임베딩 생성 또는 유사도 계산 중 예상치 못한 오류가 발생했을 경우
        """
        # 1. 입력값 유효성 검사
        if not isinstance(ret_docs, list):
            raise TypeError("입력값(ret_docs)은 반드시 문자열 리스트(List[str]) 형태여야 합니다.")
        if len(ret_docs) < 2:
            raise ValueError("다양성을 계산하려면 최소 2개 이상의 문서가 필요합니다.")

        # 2. 임베딩 생성 및 유사도 계산 오류 처리
        try:
            # 텍스트 리스트를 임베딩 벡터(Numpy 배열) 리스트로 변환
            ret_docs_vec = self.embedding_adapter.create_embeddings(ret_docs)

            # 임베딩 결과가 비어있거나 유효하지 않은 경우 에러 발생
            if not isinstance(ret_docs_vec, np.ndarray) or ret_docs_vec.size == 0:
                raise ValueError("임베딩 어댑터가 유효한 임베딩 결과를 반환하지 않았습니다.")
            
            # 코사인 유사도 계산
            similarity_matrix = cosine_similarity(ret_docs_vec)
            indices = np.triu_indices(len(ret_docs_vec), k=1)
            
            mean_similarity = np.mean(similarity_matrix[indices]) if indices[0].size > 0 else 0.0
            
            diversity_score = 1 - mean_similarity
            return Performance(score=diversity_score, unit='0 to 1', metric='Diversity')

        except Exception as e:
            # 임베딩 어댑터 API 호출 실패, sklearn 연산 오류 등 모든 예외를 처리
            # 원본 에러(e)를 포함하여 RuntimeError 발생
            raise RuntimeError(f"다양성 점수 계산 중 오류가 발생했습니다: {e}")



class GeneralizedEmbeddingCoverageError(BaseMetric):
    """GECE: 쿼리와 검색 결과의 임베딩 공간상 근접성을 평가합니다.

    쿼리 임베딩과 검색된 문서 임베딩들 간의 평균 유클리드 거리를 계산합니다.
    값이 작을수록 검색 결과가 쿼리와 가깝다는 의미(커버리지가 좋음)입니다.
    """
    def __init__(self, embedding_adapter: BaseEmbeddingAdapter):
        """
        :param embedding_adapter: 텍스트를 임베딩 벡터로 변환할 어댑터
        :type embedding_adapter: BaseEmbeddingAdapter
        """
        if not isinstance(embedding_adapter, BaseEmbeddingAdapter):
            raise TypeError("embedding_adapter는 BaseEmbeddingAdapter의 인스턴스여야 합니다.")
        self.embedding_adapter = embedding_adapter

    def evaluate(self, query: str, ret_docs: List[str]) -> Performance:
        """
        평균 유클리드 거리 (GECE 점수)를 계산합니다.

        :param query: 사용자 원본 쿼리 텍스트
        :type query: str
        :param ret_docs: 검색된 각 문서의 텍스트 리스트
        :type ret_docs: List[str]
        :return: 계산된 평균 거리(coverage_error)를 담은 Performance 객체
        :rtype: Performance
        :raises ValueError: 문서 리스트가 비어있거나 임베딩 생성에 실패했을 경우
        :raises TypeError: 입력값의 타입이 올바르지 않을 경우
        :raises RuntimeError: 거리 계산 중 예상치 못한 오류가 발생했을 경우
        """
        # 1. 입력값 유효성 검사
        if not isinstance(query, str) or not isinstance(ret_docs, list):
            raise TypeError("입력값의 타입이 올바르지 않습니다 (query: str, ret_docs: List[str]).")
        if not ret_docs:
            raise ValueError("GECE를 계산하려면 최소 1개 이상의 문서가 필요합니다.")

        # 2. 임베딩 생성 및 거리 계산 오류 처리
        try:
            # 쿼리와 문서를 임베딩 벡터로 변환
            query_vec_list = self.embedding_adapter.create_embeddings([query])
            if query_vec_list.size == 0:
                raise ValueError("쿼리를 임베딩하는 데 실패했습니다.")
            query_vec = query_vec_list[0]
            
            ret_docs_vec = self.embedding_adapter.create_embeddings(ret_docs)
            if ret_docs_vec.size == 0:
                # 문서가 있었는데 임베딩 결과가 없다면 오류로 간주
                raise ValueError("문서들을 임베딩하는 데 실패했습니다.")

            # 유클리드 거리 계산
            distances = [np.linalg.norm(query_vec - doc_vec) for doc_vec in ret_docs_vec]
            coverage_error = np.mean(distances)
            
            return Performance(score=coverage_error, unit='distance', metric='GECE')
        
        except ValueError as e:
            # create_embeddings 결과가 비어있을 때 직접 발생시킨 ValueError
            raise e
        except Exception as e:
            # 임베딩 어댑터 API 호출 실패, Numpy 연산 오류 등 모든 예외를 처리
            raise RuntimeError(f"GECE 점수 계산 중 오류가 발생했습니다: {e}")


class EmbeddingCosineSimilarityEvaluation(BaseMetric):
    """쿼리와 문서 텍스트 간의 코사인 유사도를 기반으로 일관성과 커버리지를 평가합니다.

    가장 높은 유사도(local)와 전체 평균 유사도(global)를 구해, 두 값을 평균내어 반환합니다.
    값이 1에 가까울수록 쿼리와 검색 결과가 임베딩 공간에서 잘 맞닿아 있음을 의미합니다.
    """
    def __init__(self, embedding_adapter: BaseEmbeddingAdapter):
        """
        :param embedding_adapter: 텍스트를 임베딩 벡터로 변환할 어댑터
        :type embedding_adapter: BaseEmbeddingAdapter
        """
        if not isinstance(embedding_adapter, BaseEmbeddingAdapter):
            raise TypeError("embedding_adapter는 BaseEmbeddingAdapter의 인스턴스여야 합니다.")
        self.embedding_adapter = embedding_adapter
        
    def evaluate(self, query: str, ret_docs: List[str]) -> Performance:
        """
        임베딩 기반 일관성 점수를 계산합니다.

        :param query: 쿼리의 텍스트
        :type query: str
        :param ret_docs: 검색된 각 문서의 텍스트 리스트
        :type ret_docs: List[str]
        :return: 계산된 일관성 점수를 담은 Performance 객체
        :rtype: Performance
        :raises ValueError: 문서 리스트가 비어있거나 임베딩 생성에 실패했을 경우
        :raises TypeError: 입력값의 타입이 올바르지 않거나 임베딩 벡터 형식이 잘못되었을 경우
        :raises RuntimeError: 유사도 계산 중 예상치 못한 오류가 발생했을 경우
        """
        # 1. 입력값 유효성 검사
        if not isinstance(query, str) or not isinstance(ret_docs, list):
            raise TypeError("입력값의 타입이 올바르지 않습니다 (query: str, ret_docs: List[str]).")
        if not ret_docs:
            raise ValueError("일관성 점수를 계산하려면 최소 1개 이상의 문서가 필요합니다.")

        # 2. 임베딩 생성 및 유사도 계산 오류 처리
        try:
            # 쿼리와 문서를 임베딩 벡터로 변환
            query_vec_list = self.embedding_adapter.create_embeddings([query])
            if query_vec_list.size == 0:
                raise ValueError("쿼리를 임베딩하는 데 실패했습니다.")
            query_vec = query_vec_list[0]
            
            ret_docs_vec = self.embedding_adapter.create_embeddings(ret_docs)
            if ret_docs_vec.size == 0:
                raise ValueError("문서들을 임베딩하는 데 실패했습니다.")

            # 코사인 유사도 계산
            sims = cosine_similarity([query_vec], ret_docs_vec)[0]
            local_score = np.max(sims)
            global_score = np.mean(sims)
            final_score = (local_score + global_score) / 2
            
            return Performance(score=final_score, unit='-1 to 1', metric='Embedding Cosine Similarity')

        except (ValueError, TypeError, IndexError) as e:
            # 임베딩 결과가 잘못된 형식일 경우(e.g., shape 불일치) 발생 가능
            raise TypeError(f"임베딩 벡터의 형식이 올바르지 않습니다. 원본 오류: {e}")
        except Exception as e:
            # 임베딩 어댑터 API 호출 실패, Numpy/Sklearn 연산 오류 등 모든 예외 처리
            raise RuntimeError(f"일관성 점수 계산 중 오류가 발생했습니다: {e}")

class PairwiseCosineSimilarityVariance(BaseMetric):
    """
    Evaluate the semantic diversity of retrieval chunks by measuring the variance of pairwise cosine similarities
    
    :param embedding_adapter: The embedding model to use
    :type embedding_adapter: BaseEmbeddingAdapter
    :ivar embedding_adapter: Stores the embedding model
    :vartype embedding_adapter: BaseEmbeddingAdapter
    """

    def __init__(self, embedding_adapter: BaseEmbeddingAdapter):
        self.embedding_adapter = embedding_adapter

    def evaluate(self, ret_docs: list[str]) -> Performance:
        """
        Compute the semantic diversity among retrieval chunks by computing the variance of pairwise cosine similarities between their embeddings.
        
        :param context: Retrieved chunks
        :type context: list[str]
        :returns: Variance score of pairwise cosine similarities indicating semantic spread
        :rtype: Performance
        """
        ret_docs_vec = self.embedding_adapter.create_embeddings(ret_docs)
        similarity = []
        for i in range(len(ret_docs_vec)):
            for j in range(i+1, len(ret_docs_vec)):
                sim = CosineSimilarity.compute(ret_docs_vec[i], ret_docs_vec[j])
                similarity.append(sim)
        mean = np.mean(similarity)
        variance = np.mean((np.array(similarity) - mean) ** 2)
        return Performance(score=variance, unit="", metric="PCSV")