"""Retriever 성능 평가를 위한 메트릭 클래스를 정의하는 모듈입니다.

이 모듈의 메트릭들은 텍스트 기반, 임베딩 기반, 정답 데이터셋(Ground Truth) 기반 등
다양한 방식으로 Retriever의 성능을 측정합니다.

모듈 설계 노트
==============

.. note:: **Input 데이터 형식**

    모든 메트릭은 텍스트 데이터가 사전에 전처리되었다고 가정합니다.
    (특수문자 제거, 불용어 제거, 토큰화 등)

    - **query**: 단일 텍스트 문자열
    - **retrieved_documents**: 문서 텍스트들의 리스트
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

from typing import List, Any
import numpy as np
from scipy.stats import kendalltau
from sklearn.metrics.pairwise import cosine_similarity
import os
from dotenv import load_dotenv

# --- 공통 기반 클래스 및 어댑터 import ---
from common.bases.abstracts.base_module import BaseMetric
from common.bases.datas.performance_dataclass import Performance
from adapters.llm_adapter import BaseLLMAdapter, LocalLLMAdapter
from adapters.embedding_adapter import BaseEmbeddingAdapter, LocalEmbeddingAdapter

# .env 파일에서 환경 변수 불러오기
load_dotenv()
gemini_api_key = os.getenv("GEMINI_API_KEY")

class KeywordMatchingMetric(BaseMetric):
    """쿼리와 문서 간의 키워드 매칭 비율을 평가합니다.

    단순히 띄어쓰기 기준으로 토큰화하여, 쿼리 토큰이 각 문서에 얼마나
    포함되어 있는지를 계산하고 그 평균을 백분율로 반환합니다.
    """
    def evaluate(self, query: str, retrieved_documents: List[str]) -> Performance:
        """
        Keyword Matching 점수를 계산합니다.

        :param query: 사용자 원본 쿼리 텍스트
        :type query: str
        :param retrieved_documents: 검색된 문서 텍스트 리스트
        :type retrieved_documents: List[str]
        :return: Keyword Matching 점수를 담은 Performance 객체
        :rtype: Performance
        """
        if not retrieved_documents:
            return Performance(score=0.0, unit='%', metric='Keyword Matching Metric')
        
        tokenized_query = set(query.split())
        scores = []
        for doc in retrieved_documents:
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

    두 텍스트를 토큰 집합으로 보고, (교집합 크기 / 합집합 크기)를 계산합니다.
    검색된 모든 문서에 대한 평균 Jaccard 유사도를 백분율로 반환합니다.
    """
    def evaluate(self, query: str, retrieved_documents: List[str]) -> Performance:
        """
        Jaccard 유사도 점수를 계산합니다.

        :param query: 사용자 원본 쿼리 텍스트
        :type query: str
        :param retrieved_documents: 검색된 문서 텍스트 리스트
        :type retrieved_documents: List[str]
        :return: Jaccard 유사도 점수를 담은 Performance 객체
        :rtype: Performance
        """
        if not retrieved_documents:
            return Performance(score=0.0, unit='%', metric='Jaccard Similarity Metric')

        tokenized_query = set(query.split())
        scores = []
        for doc in retrieved_documents:
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

    .. note:: 입력되는 벡터들은 동일한 임베딩 모델을 통해 생성되어야 합니다.
    """
    def evaluate(self, query_embedding: np.ndarray, doc_embeddings: List[np.ndarray]) -> Performance:
        """
        평균 코사인 유사도 점수를 계산합니다.

        :param query_embedding: 쿼리의 임베딩 벡터
        :type query_embedding: np.ndarray
        :param doc_embeddings: 검색된 각 문서의 임베딩 벡터 리스트
        :type doc_embeddings: List[np.ndarray]
        :return: 평균 코사인 유사도 점수를 담은 Performance 객체
        :rtype: Performance
        """
        if not doc_embeddings:
            return Performance(score=0.0, unit='-1 to 1', metric='Cosine Similarity Metric')

        scores = cosine_similarity([query_embedding], doc_embeddings)[0]
        avg_score = np.mean(scores) if scores.size > 0 else 0.0
        return Performance(score=avg_score, unit='-1 to 1', metric='Cosine Similarity Metric')


class EuclideanDistanceMetric(BaseMetric):
    """쿼리와 문서 임베딩 간의 평균 유클리드 거리를 평가합니다.

    유클리드 거리는 벡터 공간에서 두 점 사이의 직선 거리를 나타냅니다.
    값이 작을수록 두 벡터가 가깝다는 것을 의미합니다.

    .. note:: 입력되는 벡터들은 동일한 임베딩 모델을 통해 생성되어야 합니다.
    """
    def evaluate(self, query_embedding: np.ndarray, doc_embeddings: List[np.ndarray]) -> Performance:
        """
        평균 유클리드 거리를 계산합니다.

        :param query_embedding: 쿼리의 임베딩 벡터
        :type query_embedding: np.ndarray
        :param doc_embeddings: 검색된 각 문서의 임베딩 벡터 리스트
        :type doc_embeddings: List[np.ndarray]
        :return: 평균 유클리드 거리를 담은 Performance 객체
        :rtype: Performance
        """
        if not doc_embeddings:
            return Performance(score=0.0, unit='distance', metric='Euclidean Distance Metric')

        distances = [np.linalg.norm(query_embedding - doc_emb) for doc_emb in doc_embeddings]
        avg_distance = np.mean(distances) if distances else 0.0
        return Performance(score=avg_distance, unit='distance', metric='Euclidean Distance Metric')


class ManhattanDistanceMetric(BaseMetric):
    """쿼리와 문서 임베딩 간의 평균 맨해튼 거리를 평가합니다.

    맨해튼 거리는 각 차원의 차이의 절댓값 합으로, 고차원 데이터에서 유용할 수 있습니다.
    값이 작을수록 두 벡터가 가깝다는 것을 의미합니다.

    .. note:: 입력되는 벡터들은 동일한 임베딩 모델을 통해 생성되어야 합니다.
    """
    def evaluate(self, query_embedding: np.ndarray, doc_embeddings: List[np.ndarray]) -> Performance:
        """
        평균 맨해튼 거리를 계산합니다.

        :param query_embedding: 쿼리의 임베딩 벡터
        :type query_embedding: np.ndarray
        :param doc_embeddings: 검색된 각 문서의 임베딩 벡터 리스트
        :type doc_embeddings: List[np.ndarray]
        :return: 평균 맨해튼 거리를 담은 Performance 객체
        :rtype: Performance
        """
        if not doc_embeddings:
            return Performance(score=0.0, unit='distance', metric='Manhattan Distance Metric')
        
        distances = [np.sum(np.abs(query_embedding - doc_emb)) for doc_emb in doc_embeddings]
        avg_distance = np.mean(distances) if distances else 0.0
        return Performance(score=avg_distance, unit='distance', metric='Manhattan Distance Metric')


class NegativeRejectionRateMetric(BaseMetric):
    """쿼리와 관련 없는(코사인 유사도 <= 0) 문서의 비율을 평가합니다.

    이 비율(NRR)이 낮을수록 검색 결과에 관련 없는 문서가 적게 포함되었다는 것을 의미합니다.

    .. note:: 입력되는 벡터들은 동일한 임베딩 모델을 통해 생성되어야 합니다.
    """
    def evaluate(self, query_embedding: np.ndarray, doc_embeddings: List[np.ndarray]) -> Performance:
        """
        NRR(Negative Rejection Rate) 점수를 백분율로 계산합니다.

        :param query_embedding: 쿼리의 임베딩 벡터
        :type query_embedding: np.ndarray
        :param doc_embeddings: 검색된 각 문서의 임베딩 벡터 리스트
        :type doc_embeddings: List[np.ndarray]
        :return: NRR 점수를 담은 Performance 객체
        :rtype: Performance
        """
        if not doc_embeddings:
            return Performance(score=0.0, unit='%', metric='Negative Rejection Rate Metric')

        similarities = cosine_similarity([query_embedding], doc_embeddings)[0]
        irrelevant_count = np.sum(similarities <= 0)
        rejection_rate = (irrelevant_count / len(doc_embeddings)) * 100
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
    """
    def __init__(self, mode: str = 'token', threshold: float = 0.5):
        """
        :param mode: 'token' 또는 'embedding' 중 평가 모드를 선택합니다. 기본값은 'token'입니다.
        :type mode: str
        :param threshold: 유사도가 이 값 이상일 때 정답으로 간주합니다. 기본값은 0.5입니다.
        :type threshold: float
        """
        if mode not in ['token', 'embedding']:
            raise ValueError("mode는 'token' 또는 'embedding'만 지원합니다.")
        self.mode = mode
        self.threshold = threshold

    def _jaccard_similarity(self, a: str, b: str) -> float:
        """두 텍스트 간의 Jaccard 유사도를 계산하는 헬퍼 함수입니다."""
        set_a, set_b = set(a.split()), set(b.split())
        intersection = set_a.intersection(set_b)
        union = set_a.union(set_b)
        return len(intersection) / len(union) if union else 0.0

    def evaluate(self, retrieved: List[Any], ground_truth: List[Any]) -> Performance:
        """
        설정된 모드에 따라 정밀도 점수를 계산합니다.

        :param retrieved: 검색된 문서(텍스트 또는 임베딩) 리스트
        :type retrieved: List[Any]
        :param ground_truth: 정답 문서(텍스트 또는 임베딩) 리스트
        :type ground_truth: List[Any]
        :return: 계산된 정밀도 점수를 담은 Performance 객체
        :rtype: Performance
        :raises ValueError: 'mode'가 'token'이나 'embedding'이 아닐 경우
        """
        if not retrieved:
            return Performance(score=0.0, unit='0 to 1', metric='Precision')
        
        relevant_count = 0
        if self.mode == 'token':
            for ret_doc in retrieved:
                is_relevant = any(self._jaccard_similarity(ret_doc, gt_doc) >= self.threshold for gt_doc in ground_truth)
                if is_relevant:
                    relevant_count += 1
        elif self.mode == 'embedding':
            for ret_emb in retrieved:
                sims = cosine_similarity([ret_emb], ground_truth)[0]
                if np.max(sims) >= self.threshold:
                    relevant_count += 1
        
        precision = relevant_count / len(retrieved)
        return Performance(score=precision, unit='0 to 1', metric='Precision')


class RandomDocumentInjectionEffect(BaseMetric):
    """LLM이 생성한 노이즈 문서를 주입했을 때 정밀도 하락을 측정합니다.

    쿼리와 유사해 보이지만 관련 없는 '적대적 문서'를 LLM으로 생성하고,
    이 문서를 검색 결과에 추가했을 때 정밀도가 얼마나 떨어지는지를 통해
    시스템의 강건성(Robustness)을 평가합니다.

    :ivar precision_calculator: 정밀도 계산에 사용될 PrecisionMetric 객체
    :vartype precision_calculator: PrecisionMetric
    :ivar embedding_adapter: 'embedding' 모드에서 텍스트 임베딩에 사용될 어댑터
    :vartype embedding_adapter: BaseEmbeddingAdapter
    """
    def __init__(self, precision_metric: PrecisionMetric, embedding_adapter: BaseEmbeddingAdapter = None):
        """
        :param precision_metric: 정밀도 계산에 사용할 PrecisionMetric 객체 (mode, threshold가 설정된 상태)
        :type precision_metric: PrecisionMetric
        :param embedding_adapter: 'embedding' 모드에서 사용할 텍스트 임베딩 어댑터. 기본값은 None.
        :type embedding_adapter: BaseEmbeddingAdapter, optional
        :raises ValueError: 'embedding' 모드인데 embedding_adapter가 제공되지 않은 경우
        """
        self.precision_calculator = precision_metric
        self.embedding_adapter = embedding_adapter
        if self.precision_calculator.mode == 'embedding' and not self.embedding_adapter:
            raise ValueError("'embedding' 모드에서는 embedding_adapter가 반드시 필요합니다.")

    def evaluate(self, query: str, retrieved_documents: List[Any], ground_truth: List[Any], llm_adapter: BaseLLMAdapter) -> Performance:
        """
        노이즈 문서 주입 후 정밀도 하락폭을 계산합니다.

        :param query: 노이즈 문서 생성을 위한 사용자 원본 쿼리
        :type query: str
        :param retrieved_documents: 원본 검색 결과 (텍스트 또는 임베딩) 리스트
        :type retrieved_documents: List[Any]
        :param ground_truth: 정답 (텍스트 또는 임베딩) 리스트
        :type ground_truth: List[Any]
        :param llm_adapter: 노이즈 문서 생성에 사용할 LLM 어댑터
        :type llm_adapter: BaseLLMAdapter
        :return: 정밀도 하락폭(effect) 점수를 담은 Performance 객체
        :rtype: Performance
        """
        original_precision = self.precision_calculator.evaluate(retrieved_documents, ground_truth)
        
        prompt = "Based on the user's query below, write a short, plausible-looking document that uses similar keywords but does NOT contain the real answer. Respond only with the document text."
        response_data = llm_adapter.request(prompt=prompt, query=query)
        
        adversarial_doc_text = ""
        if "error" not in response_data and response_data.get("text"):
            adversarial_doc_text = response_data["text"].strip()
        else:
            print("Warning: Failed to generate adversarial document. Using a generic random document instead.")
            adversarial_doc_text = "This is a generic irrelevant document for system testing."

        injected_precision_score = original_precision.score
        if self.precision_calculator.mode == 'token':
            injected_docs = retrieved_documents + [adversarial_doc_text]
            injected_precision = self.precision_calculator.evaluate(injected_docs, ground_truth)
            injected_precision_score = injected_precision.score
        elif self.precision_calculator.mode == 'embedding':
            embeddings = self.embedding_adapter.create_embeddings([adversarial_doc_text])
            if embeddings.size == 0: 
                print("Error: Failed to embed the adversarial document. Skipping injection for this test.")
            else:
                adversarial_embedding = embeddings[0]
                injected_embs = retrieved_documents + [adversarial_embedding]
                injected_precision = self.precision_calculator.evaluate(injected_embs, ground_truth)
                injected_precision_score = injected_precision.score
        
        effect = original_precision.score - injected_precision_score
        return Performance(score=effect, unit='precision_drop', metric='Random Doc Injection Effect')


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
        """
        if len(ranking1) < 2 or len(ranking2) < 2 or len(ranking1) != len(ranking2):
            return Performance(score=0.0, unit='-1 to 1', metric="Kendall's Tau")
        tau, _ = kendalltau(ranking1, ranking2)
        return Performance(score=tau, unit='-1 to 1', metric="Kendall's Tau")


class DiversityMetric(BaseMetric):
    """검색된 문서들의 임베딩을 기반으로 다양성을 평가합니다.

    모든 문서 임베딩 쌍의 평균 코사인 유사도를 계산한 뒤, `1 - 평균 유사도`로 다양성 점수를 산출합니다.
    값이 1에 가까울수록 문서들이 서로 의미적으로 다르다는 것(다양성이 높음)을 의미합니다.
    """
    def evaluate(self, doc_embeddings: List[np.ndarray]) -> Performance:
        """
        다양성 점수를 계산합니다.

        :param doc_embeddings: 검색된 각 문서의 임베딩 벡터 리스트
        :type doc_embeddings: List[np.ndarray]
        :return: 계산된 다양성 점수를 담은 Performance 객체
        :rtype: Performance
        """
        if len(doc_embeddings) < 2:
            return Performance(score=0.0, unit='0 to 1', metric='Diversity')

        similarity_matrix = cosine_similarity(doc_embeddings)
        indices = np.triu_indices(len(doc_embeddings), k=1)
        mean_similarity = np.mean(similarity_matrix[indices]) if indices[0].size > 0 else 0.0
        diversity_score = 1 - mean_similarity
        return Performance(score=diversity_score, unit='0 to 1', metric='Diversity')


class GeneralizedEmbeddingCoverageError(BaseMetric):
    """GECE: 쿼리와 검색 결과의 임베딩 공간상 근접성을 평가합니다.

    쿼리 임베딩과 검색된 문서 임베딩들 간의 평균 유클리드 거리를 계산합니다.
    값이 작을수록 검색 결과가 쿼리와 가깝다는 의미(커버리지가 좋음)입니다.
    """
    def evaluate(self, query_embedding: np.ndarray, doc_embeddings: List[np.ndarray]) -> Performance:
        """
        평균 유클리드 거리 (GECE 점수)를 계산합니다.

        :param query_embedding: 쿼리의 임베딩 벡터
        :type query_embedding: np.ndarray
        :param doc_embeddings: 검색된 각 문서의 임베딩 벡터 리스트
        :type doc_embeddings: List[np.ndarray]
        :return: 계산된 평균 거리(coverage_error)를 담은 Performance 객체
        :rtype: Performance
        """
        if not doc_embeddings:
            return Performance(score=0.0, unit='distance', metric='GECE')
            
        distances = [np.linalg.norm(query_embedding - doc_emb) for doc_emb in doc_embeddings]
        coverage_error = np.mean(distances) if distances else 0.0
        return Performance(score=coverage_error, unit='distance', metric='GECE')


class EmbeddingCosineSimilarityEvaluation(BaseMetric):
    """쿼리와 문서 임베딩 간의 코사인 유사도를 기반으로 일관성과 커버리지를 평가합니다.

    가장 높은 유사도(local)와 전체 평균 유사도(global)를 구해, 두 값을 평균내어 반환합니다.
    값이 1에 가까울수록 쿼리와 검색 결과가 임베딩 공간에서 잘 맞닿아 있음을 의미합니다.
    """
    def evaluate(self, query_embedding: np.ndarray, doc_embeddings: List[np.ndarray]) -> Performance:
        """
        임베딩 기반 일관성 점수를 계산합니다.

        :param query_embedding: 쿼리의 임베딩 벡터
        :type query_embedding: np.ndarray
        :param doc_embeddings: 검색된 각 문서의 임베딩 벡터 리스트
        :type doc_embeddings: List[np.ndarray]
        :return: 계산된 일관성 점수를 담은 Performance 객체
        :rtype: Performance
        """
        if not doc_embeddings:
            return Performance(score=0.0, unit='-1 to 1', metric='Embedding Cosine Similarity')

        sims = cosine_similarity([query_embedding], doc_embeddings)[0]
        local_score = np.max(sims)
        global_score = np.mean(sims)
        final_score = (local_score + global_score) / 2
        return Performance(score=final_score, unit='-1 to 1', metric='Embedding Cosine Similarity')