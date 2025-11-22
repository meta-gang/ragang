from core.utils.query_generator.prompts import prompt_summarize_chunks, prompt_summarize_summaries
from adapters.llm_adapter import BaseLLMAdapter
from core.utils.query_generator.models import Chunk, DocSummary, Explanation
from core.utils.query_generator.config import MAX_WORKERS
import asyncio
import logging
import re
from collections import defaultdict
from typing import List, Dict, Set, Tuple

logger = logging.getLogger(__name__)


class ContentAnalyzer:
    def __init__(self, llm_adapter : BaseLLMAdapter):
        """
        list[Chunk]를 입력받아 LLM을 통해 요약 및 키워드를 추출하고,
        이를 list[DocSummary] 및 keywordSearch 딕셔너리로 구조화합니다.
        """
        self.llm_adapter = llm_adapter
        pass

    async def _call_llm(self, prompts: List[str], max_workers: int = MAX_WORKERS) -> List[dict]:
        """
        LLM 어댑터를 사용하여 프롬프트 배치를 비동기적으로 전송합니다.
        """
        queries = [""] * len(prompts)
        results = await self.llm_adapter.request_async_batch(prompts, queries, max_workers=max_workers)
        return results

    def _process_answers(self, responses: List[dict]) -> List[Tuple[str, List[str]]]:
        """
        LLM 응답을 파싱하여 요약 및 키워드를 추출합니다.
        """
        parsed_results: List[Tuple[str, List[str]]] = []
        for response_dict in responses:
            if isinstance(response_dict, Exception):
                logger.error(f"LLM 호출 중 예외 발생: {response_dict}")
                parsed_results.append(("", []))
                continue

            response_text = response_dict.get("text", "")

            summary_match = re.search(r"요약:\s*(.*?)(?=\n키워드:|$)", response_text, re.DOTALL)
            keywords_match = re.search(r"키워드:\s*\[(.*?)\]", response_text)

            if summary_match and keywords_match:
                summary = summary_match.group(1).strip()
                keywords_str = keywords_match.group(1)
                keywords = [k.strip() for k in keywords_str.split(',') if k.strip()]
                parsed_results.append((summary, keywords))
            else:
                # 파싱 실패 시 에러 로그 기록
                logger.error(f"LLM 응답 파싱 실패. 원본 응답: {response_text}")
                parsed_results.append(("", []))

        return parsed_results
        

    def summarize_chunks(self, all_chunks: List[Chunk], max_workers: int = 10) -> List[DocSummary]:
        """
        [동기] 전체 청크 리스트를 받아, 문서별/페이지별로 요약 및 키워드를 생성합니다.
        내부적으로 비동기 LLM 호출을 동기적으로 실행합니다.
        
        입력:
            all_chunks: List[Chunk]: DocumentProcessor가 생성한 전체 청크 리스트.
            max_workers: int: LLM API 동시 요청 수.
        출력:
            List[DocSummary]: 문서별 요약 정보가 담긴 리스트.
        """
        if not all_chunks:
            return []

        grouped_chunks: Dict[int, Dict[int, List[Chunk]]] = defaultdict(lambda: defaultdict(list))
        for chunk in all_chunks:
            grouped_chunks[chunk.doc_idx][chunk.page_idx].append(chunk)

        doc_summaries: List[DocSummary] = []

        for doc_idx in sorted(grouped_chunks.keys()):
            page_explanations: List[Explanation] = []
            page_prompts: List[str] = []
            page_chunk_indices_map: Dict[int, List[int]] = {}

            for page_idx in sorted(grouped_chunks[doc_idx].keys()):
                chunks_on_page = sorted(grouped_chunks[doc_idx][page_idx], key=lambda c: c.chunk_idx)
                
                all_sentences = []
                for chunk in chunks_on_page:
                    # 마침표 뒤에 공백이 있는 경우를 기준으로 문장 분리
                    sentences = [s.strip() for s in chunk.text.split('. ') if s.strip()]
                    all_sentences.extend(sentences)
                
                # dict.fromkeys를 사용하여 순서를 유지하면서 중복 제거
                unique_sentences = list(dict.fromkeys(all_sentences))
                page_text = ". ".join(unique_sentences)
                if page_text: # 문장이 하나 이상 있을 경우 마침표 추가
                    page_text += "."

                page_chunk_indices_map[page_idx] = [chunk.chunk_idx for chunk in chunks_on_page]
                page_prompts.append(prompt_summarize_chunks.format(text=page_text))
            
            page_llm_responses = asyncio.run(self._call_llm(page_prompts, max_workers=max_workers))
            parsed_page_results = self._process_answers(page_llm_responses)

            for i, (page_idx, chunk_indices) in enumerate(sorted(page_chunk_indices_map.items())):
                summary, keywords = parsed_page_results[i]
                page_explanations.append(Explanation(index=page_idx, explanation=summary, keywords=keywords, related_chunks=chunk_indices))
            
            combined_page_summaries_text = "\n".join([exp.explanation for exp in page_explanations])
            doc_level_prompt = prompt_summarize_summaries.format(text=combined_page_summaries_text)

            doc_llm_response = asyncio.run(self._call_llm([doc_level_prompt], max_workers=1))
            parsed_doc_result = self._process_answers(doc_llm_response)[0]

            doc_summary_text, doc_keywords = parsed_doc_result
            
            all_doc_chunks_indices = [chunk.chunk_idx for page_idx in sorted(grouped_chunks[doc_idx].keys()) for chunk in grouped_chunks[doc_idx][page_idx]]

            doc_explanation = Explanation(index=doc_idx, explanation=doc_summary_text, keywords=doc_keywords, related_chunks=sorted(list(set(all_doc_chunks_indices))))

            doc_summaries.append(DocSummary(docExplanation=doc_explanation, pageExplanations=page_explanations))
        
        return doc_summaries




    def build_keyword_index(self, summaries: List[DocSummary]) -> Dict[str, List[int]]:
        """
        summarize_chunks의 결과물을 바탕으로, 키워드를 통해 관련 
        chunk_idx를 빠르게 찾을 수 있는 역인덱스(Inverted Index)를 구축합니다.
        
        입력:
            summaries: List[DocSummary]: summarize_chunks에서 반환된 요약 리스트.
        출력:
            Dict[str, List[int]]: { "키워드": [1, 5, 10], ... } 형태의 딕셔너리.
        """
        
        # 1. keywordSearch: dict[str, set[int]] 초기화 (중복 방지용 set 사용)
        keywordSearch_set: Dict[str, Set[int]] = defaultdict(set)
        
        # 2. summaries 리스트 순회
        for docSummary in summaries:
            
            # 3. 페이지 요약(pageExplanations)만을 순회하여 인덱싱합니다.
            # 문서 전체 요약(docExplanation)은 관련 청크 범위가 너무 넓어 제외합니다.
            for explanation in docSummary.pageExplanations:
                # 4. keywords와 related_chunks 가져오기
                keywords = explanation.keywords
                related_chunks = explanation.related_chunks
                
                # 5. keywords 리스트의 각 keyword에 대해
                for keyword in keywords:
                    # (선택적) 키워드 정규화 (소문자 변환, 양쪽 공백 제거)
                    normalized_keyword = keyword.lower().strip()
                    
                    if normalized_keyword:
                        # 6. keywordSearch[keyword]에 related_chunks 추가
                        keywordSearch_set[normalized_keyword].update(related_chunks)
                        
        # 7. 딕셔너리의 값(set)을 list[int]로 변환하여 반환
        # 결과를 정렬하여 일관성을 유지
        keywordSearch_list: Dict[str, List[int]] = {
            keyword: sorted(list(chunks_set))
            for keyword, chunks_set in keywordSearch_set.items()
        }
        
        return keywordSearch_list
