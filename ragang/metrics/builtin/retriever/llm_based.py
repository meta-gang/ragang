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

from typing import List

# --- 공통 기반 클래스 및 어댑터 import ---
from ragang.core.bases.abstracts.base_module import BaseMetric
from ragang.core.bases.datas.performance import Performance
from ragang.metrics.builtin.retriever.non_llm_based import PrecisionMetric
from ragang.adapters.llm_adapter import BaseLLMAdapter
from ragang.adapters.embedding_adapter import BaseEmbeddingAdapter


class BaseBuiltinMetric(BaseMetric):
    def __init__(self, param_src: list[str], llm_adapter: BaseLLMAdapter = None, embedding_adapter: BaseEmbeddingAdapter = None):
        super().__init__(param_src)
        self.llm_adapter = llm_adapter
        self.embedding_adapter = embedding_adapter


class RandomDocumentInjectionEffect(BaseBuiltinMetric):
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

    def __init__(self, precision_metric: PrecisionMetric, llm_adapter: BaseLLMAdapter = None,
                 embedding_adapter: BaseEmbeddingAdapter = None):
        """
        :param precision_metric: 정밀도 계산에 사용할 PrecisionMetric 객체 (mode, threshold가 설정된 상태)
        :type precision_metric: PrecisionMetric
        :param llm_adapter: 노이즈 문서 생성에 사용할 LLM 어댑터
        :type llm_adapter: BaseLLMAdapter
        :param embedding_adapter: 'embedding' 모드에서 사용할 텍스트 임베딩 어댑터. 기본값은 None.
        :type embedding_adapter: BaseEmbeddingAdapter, optional
        :raises ValueError: 'embedding' 모드인데 embedding_adapter가 제공되지 않은 경우
        """
        self.precision_calculator = precision_metric
        super().__init__(llm_adapter, embedding_adapter)
        if self.precision_calculator.mode == 'embedding' and not self.embedding_adapter:
            raise ValueError("'embedding' 모드에서는 embedding_adapter가 반드시 필요합니다.")

    def evaluate(self, query: str, retrieved_documents: List[str], ground_truth: List[str]) -> Performance:
        """
        노이즈 문서 주입 후 정밀도 하락폭을 계산합니다.

        :param query: 노이즈 문서 생성을 위한 사용자 원본 쿼리
        :type query: str
        :param retrieved_documents: 원본 검색 결과 텍스트 리스트
        :type retrieved_documents: List[str]
        :param ground_truth: 정답 텍스트 리스트
        :type ground_truth: List[str]
        :return: 정밀도 하락폭(effect) 점수를 담은 Performance 객체
        :rtype: Performance
        """
        original_precision = self.precision_calculator.evaluate(retrieved_documents, ground_truth)

        prompt = "Based on the user's query below, write a short, plausible-looking document that uses similar keywords but does NOT contain the real answer. Respond only with the document text."
        response_data = self.llm_adapter.request(prompt=prompt, query=query)

        adversarial_doc_text = ""
        if "error" not in response_data and response_data.get("text"):
            adversarial_doc_text = response_data["text"].strip()
        else:
            print("Warning: Failed to generate adversarial document. Using a generic random document instead.")
            adversarial_doc_text = "This is a generic irrelevant document for system testing."

        injected_docs = retrieved_documents + [adversarial_doc_text]
        injected_precision = self.precision_calculator.evaluate(injected_docs, ground_truth)

        effect = original_precision.score - injected_precision.score
        return Performance(score=effect, unit='precision_drop', metric='Random Doc Injection Effect')
