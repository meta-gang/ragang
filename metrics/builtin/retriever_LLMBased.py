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

from typing import List, Any
import numpy as np
from scipy.stats import kendalltau
from sklearn.metrics.pairwise import cosine_similarity
import os
from dotenv import load_dotenv

# --- 공통 기반 클래스 및 어댑터 import ---
from common.bases.abstracts.base_module import BaseMetric
from common.bases.datas.performance_dataclass import Performance
from metrics.builtin.retriever_NonLLMBased import PrecisionMetric
from adapters.llm_adapter import BaseLLMAdapter, LocalLLMAdapter
from adapters.embedding_adapter import BaseEmbeddingAdapter, LocalEmbeddingAdapter



class RandomDocumentInjectionEffect(BaseMetric):
    """LLM이 생성한 노이즈 문서를 주입했을 때 정밀도 하락을 측정합니다.

    쿼리와 유사해 보이지만 관련 없는 '적대적 문서'를 LLM으로 생성하고,
    이 문서를 검색 결과에 추가했을 때 정밀도가 얼마나 떨어지는지를 통해
    시스템의 강건성(Robustness)을 평가합니다.

    :ivar precision_calculator: 정밀도 계산에 사용될 PrecisionMetric 객체
    :vartype precision_calculator: PrecisionMetric
    :ivar embedding_adapter: 'embedding' 모드에서 텍스트 임베딩에 사용될 어댑터
    :vartype embedding_adapter: BaseEmbeddingAdapter, optional
    :ivar llm_adapter: 노이즈 문서 생성에 사용될 LLM 어댑터
    :vartype llm_adapter: BaseLLMAdapter
    """
    def __init__(self, precision_metric: PrecisionMetric, llm_adapter: BaseLLMAdapter, embedding_adapter: BaseEmbeddingAdapter = None):
        """
        :param precision_metric: 정밀도 계산에 사용할 PrecisionMetric 객체 (mode, threshold가 설정된 상태)
        :type precision_metric: PrecisionMetric
        :param llm_adapter: 노이즈 문서 생성에 사용할 LLM 어댑터
        :type llm_adapter: BaseLLMAdapter
        :param embedding_adapter: 'embedding' 모드에서 사용할 텍스트 임베딩 어댑터. 기본값은 None.
        :type embedding_adapter: BaseEmbeddingAdapter, optional
        :raises ValueError: 'embedding' 모드인데 embedding_adapter가 제공되지 않은 경우
        :raises TypeError: 어댑터 타입이 올바르지 않은 경우
        """
        if not isinstance(llm_adapter, BaseLLMAdapter):
            raise TypeError("llm_adapter는 BaseLLMAdapter의 인스턴스여야 합니다.")
        if embedding_adapter and not isinstance(embedding_adapter, BaseEmbeddingAdapter):
            raise TypeError("embedding_adapter는 BaseEmbeddingAdapter의 인스턴스여야 합니다.")
        
        self.precision_calculator = precision_metric
        self.llm_adapter = llm_adapter
        self.embedding_adapter = embedding_adapter
        
        if self.precision_calculator.mode == 'embedding' and not self.embedding_adapter:
            raise ValueError("'embedding' 모드에서는 embedding_adapter가 반드시 필요합니다.")

    def evaluate(self, query: str, ret_docs: List[Any], ground_truth: List[Any]) -> Performance:
        """
        노이즈 문서 주입 후 정밀도 하락폭을 계산합니다.

        :param query: 노이즈 문서 생성을 위한 사용자 원본 쿼리
        :type query: str
        :param ret_docs: 원본 검색 결과 리스트 (텍스트 또는 임베딩)
        :type ret_docs: List[Any]
        :param ground_truth: 정답 리스트 (텍스트 또는 임베딩)
        :type ground_truth: List[Any]
        :return: 정밀도 하락폭(effect) 점수를 담은 Performance 객체
        :rtype: Performance
        :raises RuntimeError: LLM/임베딩 어댑터 호출 실패 또는 계산 중 예상치 못한 오류 발생 시
        """
        try:
            # 1. 원본 정밀도 계산
            original_precision = self.precision_calculator.evaluate(ret_docs, ground_truth)
            
            # 2. LLM으로 노이즈 문서 생성
            prompt = "Based on the user's query below, write a short, plausible-looking document that uses similar keywords but does NOT contain the real answer. Respond only with the document text."
            response_data = self.llm_adapter.request(prompt=prompt, query=query)
            
            if "error" in response_data or not response_data.get("text"):
                raise RuntimeError(f"LLM 노이즈 문서 생성 실패: {response_data.get('error', 'Empty response')}")
            
            adversarial_doc_text = response_data["text"].strip()

            injected_precision_score = original_precision.score
            
            # 3. 모드에 따라 노이즈 주입 및 재평가
            if self.precision_calculator.mode == 'token':
                injected_docs = ret_docs + [adversarial_doc_text]
                injected_precision = self.precision_calculator.evaluate(injected_docs, ground_truth)
                injected_precision_score = injected_precision.score
            elif self.precision_calculator.mode == 'embedding':
                embeddings = self.embedding_adapter.create_embeddings([adversarial_doc_text])
                if embeddings.size == 0:
                    raise RuntimeError("생성된 노이즈 문서를 임베딩하는 데 실패했습니다.")
                
                adversarial_embedding = embeddings[0]
                injected_embs = ret_docs + [adversarial_embedding]
                injected_precision = self.precision_calculator.evaluate(injected_embs, ground_truth)
                injected_precision_score = injected_precision.score

            # 4. 최종 하락폭 계산
            effect = original_precision.score - injected_precision_score
            return Performance(score=effect, unit='precision_drop', metric='Random Doc Injection Effect')

        except Exception as e:
            # 정밀도 계산 오류, 어댑터 오류 등 모든 예외를 처리
            raise RuntimeError(f"RandomDocInjectionEffect 계산 중 오류가 발생했습니다: {e}")