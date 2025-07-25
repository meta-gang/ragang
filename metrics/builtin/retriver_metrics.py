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


class PrecisionMetric(BaseMetric):
    """
    정밀도 평가 : 얼마나 많은 검색된 문서가 실제로 정답에 해당하는지를 평가

    방법:
        * mode='token' : 각 검색 문서와 정답 문서 쌍마다 Jaccard 유사도(토큰 교집합/합집합 비율)를 계산, 유사도가 임계값(threshold) 이상이면 정답으로 간주
        * mode='embedding' : 각 검색 문서 임베딩과 정답 문서 임베딩 쌍마다 코사인 유사도를 계산, 유사도가 임계값(threshold) 이상이면 정답으로 간주
        * 정답 문서 수 / 검색된 문서 수
        * 값이 1에 가까울수록 검색 결과가 정확함을 의미
    사용 예 : 검색 시스템의 정확도를 평가할 때 사용

    Parameters
    ----------
    retrieved : List[str] 또는 List[np.ndarray]
        검색 시스템이 반환한 문서(또는 임베딩)의 리스트
    ground_truth : List[str] 또는 List[np.ndarray]
        실제 정답에 해당하는 문서(또는 임베딩)의 리스트
    threshold : float, optional
        유사도 임계값 (기본값: 0.5 for token, 0.95 for embedding)
    mode : str, optional
        'token' 또는 'embedding' (기본값: 'token')

    Returns
    -------
    Performance
        계산된 정밀도 점수를 담은 Performance 객체
    """
    def __init__(self, threshold=0.5, mode='token'):
        self.threshold = threshold
        self.mode = mode

    def jaccard_similarity(self, a: str, b: str) -> float:
        set_a = set(a.split())
        set_b = set(b.split())
        intersection = set_a & set_b
        union = set_a | set_b
        return len(intersection) / len(union) if union else 0.0

    def evaluate(self, retrieved, ground_truth) -> Performance:
        if not retrieved:
            return Performance(score=0.0, unit='', metric='Precision', _eval=False)
        relevant = 0
        if self.mode == 'token':
            for ret_doc in retrieved:
                for gt_doc in ground_truth:
                    if self.jaccard_similarity(ret_doc, gt_doc) >= self.threshold:
                        relevant += 1
                        break
        elif self.mode == 'embedding':
            for ret_emb in retrieved:
                sims = cosine_similarity([ret_emb], ground_truth)[0]
                if np.max(sims) >= self.threshold:
                    relevant += 1
        else:
            raise ValueError("mode는 'token' 또는 'embedding'만 지원합니다.")
        precision = relevant / len(retrieved)
        return Performance(score=precision, unit='', metric='Precision')


# random_document_injection_effect
class RandomDocumentInjectionEffect(BaseMetric):
    """
    검색 결과에 LLM이 생성한 '그럴듯한 노이즈 문서'를 삽입했을 때 정밀도가 얼마나 하락하는지 측정
    """
    def __init__(self, precision_metric: PrecisionMetric, embedding_adapter: BaseEmbeddingAdapter = None):
        """
        Parameters
        ----------
        precision_metric : PrecisionMetric
            정밀도 계산에 사용할 PrecisionMetric 객체 (mode, threshold가 설정된 상태)
        embedding_adapter : BaseEmbeddingAdapter, optional
            'embedding' 모드 사용 시, 텍스트를 임베딩할 어댑터. 기본값은 None.
        """
        self.precision_calculator = precision_metric
        self.embedding_adapter = embedding_adapter
        if self.precision_calculator.mode == 'embedding' and not self.embedding_adapter:
            raise ValueError("'embedding' 모드에서는 embedding_adapter가 반드시 필요합니다.")

    def evaluate(self, query: str, retrieved_documents: List[Any], ground_truth: List[Any], llm_adapter: BaseLLMAdapter) -> Performance:
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
                # injected_precision_score는 original_precision.score와 동일하게 유지
            else:
                adversarial_embedding = embeddings[0]
                injected_embs = retrieved_documents + [adversarial_embedding]
                injected_precision = self.precision_calculator.evaluate(injected_embs, ground_truth)
                injected_precision_score = injected_precision.score
        
        effect = original_precision.score - injected_precision_score
        return Performance(score=effect, unit='precision_drop', metric='Random Doc Injection Effect')


# ranking_consistency_kendall_tau
class RankingConsistencyKendallTau(BaseMetric):
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
    def evaluate(self, ranking1: List[int], ranking2: List[int]) -> Performance:
        if len(ranking1) < 2 or len(ranking2) < 2:
             return Performance(score=0.0, unit='', metric="Kendall's Tau", _eval=False)
        tau, _ = kendalltau(ranking1, ranking2)
        return Performance(score=tau, unit='(-1 to 1)', metric="Kendall's Tau")


# diversity_metric
class DiversityMetric(BaseMetric):
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
    def evaluate(self, doc_embeddings: List[np.ndarray]) -> Performance:
        # 문서가 2개 미만이면 다양성을 측정할 수 없음
        if len(doc_embeddings) < 2:
            return Performance(score=0.0, unit='', metric='Diversity', _eval=False)
        # 모든 문서 쌍 간의 코사인 유사도 계산
        similarity_matrix = cosine_similarity(doc_embeddings)
        # 대각선(자기 자신과의 유사도=1)을 제외한 상삼각행렬의 평균을 계산
        # 이는 모든 문서 쌍의 유사도 평균과 같음
        indices = np.triu_indices(len(doc_embeddings), k=1)
        mean_similarity = np.mean(similarity_matrix[indices])
        # 다양성 점수는 (1 - 평균 유사도)로 정의
        diversity_score = 1 - mean_similarity
        return Performance(score=diversity_score, unit='(0 to 1)', metric='Diversity')


# generalized_embedding_coverage_error
class GeneralizedEmbeddingCoverageError(BaseMetric):
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
    def evaluate(self, query_embedding: np.ndarray, doc_embeddings: List[np.ndarray]) -> Performance:
        if not doc_embeddings:
            return Performance(score=0.0, unit='distance', metric='GECE', _eval=False)
            
        distances = [np.linalg.norm(query_embedding - doc_emb) for doc_emb in doc_embeddings]
        coverage_error = np.mean(distances)
        return Performance(score=coverage_error, unit='', metric='GECE')


# embedding_consine_similarity_evaluation
class EmbeddingCosineSimilarityEvaluation(BaseMetric):
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
    def evaluate(self, query_embedding: np.ndarray, doc_embeddings: List[np.ndarray]) -> Performance:
        if not doc_embeddings:
            return Performance(score=0.0, unit='', metric='Embedding Consistency E', _eval=False)

        sims = cosine_similarity([query_embedding], doc_embeddings)[0]
        local_score = np.max(sims)  # 가장 가까운 문서와의 유사도
        high_score = np.mean(sims)  # 전체 문서와의 평균 유사도
        
        final_score = (local_score + high_score) / 2
        return Performance(score=final_score, unit='', metric='Embedding Consistency E')