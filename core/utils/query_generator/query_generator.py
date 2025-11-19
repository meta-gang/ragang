import asyncio
import logging
import random
import re
import json
from typing import List, Dict, Optional, Tuple, Set
from collections import defaultdict

# LLM 어댑터 및 모델 임포트
from adapters.llm_adapter import BaseLLMAdapter
from core.utils.query_generator.models import (
    Chunk, Query, QueryType, Scenario, Explanation, DocSummary
)

# 프롬프트 임포트
from core.utils.query_generator.prompts import (
    prompt_generate_simple_search_queries_wr,
    prompt_generate_simple_expln_queries_wr,
    prompt_generate_simple_tf_queries_wr,
    prompt_generate_complex_multi_queries_wr,
    prompt_generate_complex_comp_queries_wr,
    prompt_generate_complex_infer_queries_wr,
    prompt_generate_complex_cond_queries_wr,
    prompt_generate_simple_search_queries_nr,
    prompt_generate_simple_expln_queries_nr,
    prompt_generate_simple_tf_queries_nr,
    prompt_generate_complex_multi_queries_nr,
    prompt_generate_complex_comp_queries_nr,
    prompt_generate_complex_infer_queries_nr,
    prompt_generate_complex_cond_queries_nr
)

logger = logging.getLogger(__name__)

QUERY_DISTRIBUTION_WEIGHTS = {
    # With Reference (WR) - 13
    "WR_SIMPLE_SEARCH": 2,
    "WR_SIMPLE_EXPLN": 2,
    "WR_SIMPLE_TF": 2,
    "WR_COMPLEX_MULTI": 2,
    "WR_COMPLEX_COMP": 2,
    "WR_COMPLEX_INFER": 2,
    "WR_COMPLEX_COND": 1,
    # No Reference (NR) - 7
    "NR_SIMPLE_SEARCH": 1,
    "NR_SIMPLE_EXPLN": 1,
    "NR_SIMPLE_TF": 1,
    "NR_COMPLEX_MULTI": 1,
    "NR_COMPLEX_COMP": 1,
    "NR_COMPLEX_INFER": 1,
    "NR_COMPLEX_COND": 1,
}
TOTAL_BASE_WEIGHT = sum(QUERY_DISTRIBUTION_WEIGHTS.values()) # 20

MIN_CHUNKS_FOR_COMPLEX_QUERY = 3    # 복잡 쿼리 생성을 위한 최소 청크 수
MAX_CONTEXT_LENGTH = 8000           # LLM에 전달할 최대 컨텍스트 길이


class QueryGenerator:
    """
    🎭 QueryGenerator 클래스
    역할 (Responsibility): 분석된 문서 요약(DocSummary)을 바탕으로 쿼리 생성의 맥락이 될 페르소나와 시나리오를 생성합니다.
    """

    def __init__(self, llm_adapter: BaseLLMAdapter):
        self.llm_adapter = llm_adapter

    # --- 5.1. Private Methods (Helper) ---

    # [신규] 쿼리 개수 분배 헬퍼
    def _distribute_queries(self, num_total_queries: int) -> Dict[str, int]:
        """
        [Helper] 총 쿼리 개수를 입력받아, QUERY_DISTRIBUTION_WEIGHTS 비율대로 각 타입에 분배합니다.
        (Largest Remainder Method를 사용하여 반올림 오류 없이 총합을 맞춥니다)
        """
        logger.info(f"총 {num_total_queries}개의 쿼리를 {len(QUERY_DISTRIBUTION_WEIGHTS)}개 타입에 분배합니다...")
        
        allocated: Dict[str, int] = {}
        remainders: List[Tuple[str, float]] = []
        current_total = 0

        for key, weight in QUERY_DISTRIBUTION_WEIGHTS.items():
            exact_share = num_total_queries * (weight / TOTAL_BASE_WEIGHT)
            base_num = int(exact_share)
            remainder = exact_share - base_num
            
            allocated[key] = base_num
            current_total += base_num
            remainders.append((key, remainder))

        # 남은 쿼리 개수 계산 (반올림으로 인해 버려진 총합)
        queries_to_distribute = num_total_queries - current_total
        
        # 나머지가 큰 순서대로 정렬
        remainders.sort(key=lambda x: x[1], reverse=True)
        
        # 나머지가 큰 순서대로 1개씩 추가 분배
        for i in range(queries_to_distribute):
            key_to_increment = remainders[i][0]
            allocated[key_to_increment] += 1
            
        logger.debug(f"쿼리 분배 결과: {allocated}")
        return allocated


    def _parse_json_queries(self, response_text: str, query_type: QueryType, reference_chunks: Optional[List[int]]) -> List[Query]:
        """ [동기] LLM 응답(JSON 문자열 리스트)을 파싱하여 Query 객체 리스트로 변환합니다. """
        try:
            # LLM이 코드블럭(```json ... ```)이나 불필요한 텍스트와 함께 반환할 경우 대비
            json_match = re.search(r'\[.*\]', response_text, re.DOTALL)
            if not json_match:
                logger.warning(f"LLM 응답에서 JSON 리스트를 찾지 못했습니다. 응답: {response_text[:100]}...")
                return []

            query_strings = json.loads(json_match.group(0))
            
            if not isinstance(query_strings, list):
                logger.warning(f"파싱된 JSON이 리스트가 아닙니다. 타입: {type(query_strings)}")
                return []

            queries: List[Query] = []
            for q_str in query_strings:
                if isinstance(q_str, str) and q_str.strip():
                    queries.append(Query(
                        query=q_str.strip(),
                        type=query_type,
                        reference=reference_chunks
                    ))
            return queries

        except json.JSONDecodeError as e:
            logger.error(f"JSON 파싱 실패: {e}. 원본 응답: {response_text}")
            return []
        except Exception as e:
            logger.error(f"쿼리 파싱 중 알 수 없는 오류: {e}")
            return []

    async def _call_llm_and_parse_async(
        self,
        context_text: str,
        scenario: Scenario,
        prompt_template: str,
        query_type: QueryType,
        num_queries: int,
        reference_chunks: Optional[List[int]]
    ) -> List[Query]:
        """ [비동기] (gather의 대상) 단일 LLM 호출을 실행하고 결과를 파싱합니다. """
        
        # [수정] 쿼리 개수가 0 이하면 아예 호출하지 않음
        if not prompt_template or not prompt_template.strip() or num_queries <= 0:
            return []
            
        try:
            # 시나리오 객체에서 페르소나와 태스크 추출
            persona = scenario.persona
            task = scenario.scenarios[0] if scenario.scenarios else "정보 검색"

            prompt = prompt_template.format(
                context=context_text,
                persona=persona,
                task=task,
                num_queries=num_queries
            )
            
            # 단일 호출 실행
            results = await self.llm_adapter.request_async_batch([prompt], [""], max_workers=1)
            if not results:
                raise ValueError("LLM 어댑터가 빈 결과를 반환했습니다.")

            result = results[0]
            if isinstance(result, Exception):
                raise result
                
            response_text = result.get("text", "")
            
            return self._parse_json_queries(response_text, query_type, reference_chunks)

        except Exception as e:
            logger.error(f"{query_type.value} 쿼리 생성 중 예외 발생: {e}")
            return [] # 실패 시 빈 리스트 반환

    def _group_chunks_by_page(self, all_chunks: List[Chunk]) -> Dict[Tuple[int, int], List[Chunk]]:
        """ [동기] 청크 리스트를 (doc_idx, page_idx) 키를 가진 딕셔너리로 그룹화합니다. """
        page_groups: Dict[Tuple[int, int], List[Chunk]] = defaultdict(list)
        for chunk in all_chunks:
            page_groups[(chunk.doc_idx, chunk.page_idx)].append(chunk)
        return page_groups

    def _get_complex_chunk_groups(self, all_chunks: List[Chunk], keyword_index: Dict[str, List[int]]) -> List[List[Chunk]]:
        """ [동기] 키워드 인덱스를 기반으로 복잡한 쿼리 생성에 사용할 청크 그룹 리스트를 반환합니다. """
        chunk_map: Dict[int, Chunk] = {chunk.chunk_idx: chunk for chunk in all_chunks}
        
        groups: List[List[Chunk]] = []
        for keyword, chunk_indices in keyword_index.items():
            if len(chunk_indices) >= MIN_CHUNKS_FOR_COMPLEX_QUERY:
                chunk_group = [chunk_map[idx] for idx in chunk_indices if idx in chunk_map]
                if len(chunk_group) >= MIN_CHUNKS_FOR_COMPLEX_QUERY:
                    groups.append(chunk_group)
        return groups

    def _combine_chunks_for_context(self, chunks: List[Chunk]) -> str:
        """ 
        [Helper] 여러 청크를 하나의 컨텍스트 문자열로 병합합니다.
        (이전 요청과 동일)
        """
        if not chunks:
            return ""

        sorted_chunks = sorted(chunks, key=lambda c: (c.doc_idx, c.page_idx, c.para_idx, c.sentence_idx))
        all_seen_sentences: Set[str] = set()
        combined_parts: List[str] = []

        for chunk in sorted_chunks:
            sentences = [s.strip() for s in chunk.text.split('. ') if s.strip()]
            
            new_sentences = []
            for s in sentences:
                if s not in all_seen_sentences:
                    new_sentences.append(s)
                    all_seen_sentences.add(s)
            
            if new_sentences:
                part_text = ". ".join(new_sentences)
                if part_text: 
                    part_text += "."
                combined_parts.append(part_text)

        context_text = "\n---\n".join(combined_parts)
        
        if len(context_text) > MAX_CONTEXT_LENGTH:
            original_len = len(context_text)
            context_text = context_text[:MAX_CONTEXT_LENGTH]
            
            last_separator = context_text.rfind("\n---\n")
            if last_separator > MAX_CONTEXT_LENGTH * 0.7: 
                context_text = context_text[:last_separator]

            logger.warning(f"컨텍스트 길이가 {MAX_CONTEXT_LENGTH}자를 초과하여 일부가 잘렸습니다. (원본: {original_len}자, Chunk IDs: {[c.chunk_idx for c in chunks]})")

        return context_text


    # --- 5.1. Private Methods (Docstring-based) ---

    # [수정] (distribution: dict) 인자 추가 및 로직 변경
    async def _generateSimpleQueriesWR(self, all_chunks: list[Chunk], scenarios: list[Scenario], distribution: Dict[str, int]) -> list[Query]:
        """
        [비동기] (WR) 페이지별 청크 그룹과 랜덤 시나리오를 받아 간단한 단일 홉 쿼리를 생성합니다.
        [수정] distribution에 할당된 만큼만 랜덤 페이지를 선택하여 생성합니다.
        """
        if not all_chunks or not scenarios:
            return []

        page_groups = self._group_chunks_by_page(all_chunks)
        if not page_groups:
            logger.warning("SimpleQueriesWR: 페이지 그룹이 없어 쿼리를 생성할 수 없습니다.")
            return []
            
        page_list = list(page_groups.values())
        tasks = []
        
        # 1. Simple Search
        num_search = distribution.get("WR_SIMPLE_SEARCH", 0)
        if num_search > 0:
            chunks = random.choice(page_list)
            scenario = random.choice(scenarios)
            context = self._combine_chunks_for_context(chunks)
            refs = [c.chunk_idx for c in chunks]
            tasks.append(self._call_llm_and_parse_async(
                context, scenario, prompt_generate_simple_search_queries_wr,
                QueryType.SIMPLE_SEARCH, num_search, refs
            ))

        # 2. Simple Expln
        num_expln = distribution.get("WR_SIMPLE_EXPLN", 0)
        if num_expln > 0:
            chunks = random.choice(page_list) # 새 랜덤 페이지
            scenario = random.choice(scenarios)
            context = self._combine_chunks_for_context(chunks)
            refs = [c.chunk_idx for c in chunks]
            tasks.append(self._call_llm_and_parse_async(
                context, scenario, prompt_generate_simple_expln_queries_wr,
                QueryType.SIMPLE_EXPLN, num_expln, refs
            ))
            
        # 3. Simple TF
        num_tf = distribution.get("WR_SIMPLE_TF", 0)
        if num_tf > 0:
            chunks = random.choice(page_list) # 새 랜덤 페이지
            scenario = random.choice(scenarios)
            context = self._combine_chunks_for_context(chunks)
            refs = [c.chunk_idx for c in chunks]
            tasks.append(self._call_llm_and_parse_async(
                context, scenario, prompt_generate_simple_tf_queries_wr,
                QueryType.SIMPLE_TF, num_tf, refs
            ))

        if not tasks:
            return []

        try:
            results = await asyncio.gather(*tasks, return_exceptions=True)
        except Exception as e:
            logger.error(f"SimpleQueriesWR 비동기 실행 중 오류: {e}")
            return []

        final_queries: List[Query] = []
        for result in results:
            if isinstance(result, list):
                final_queries.extend(result)
            elif isinstance(result, Exception):
                logger.warning(f"SimpleQueriesWR 작업 실패: {result}")
                
        return final_queries


    # [수정] (distribution: dict) 인자 추가 및 로직 변경
    async def _generateComplexQueriesWR(self, all_chunks: list[Chunk], keyword_index: dict, scenarios: list[Scenario], distribution: Dict[str, int]) -> list[Query]:
        """
        [비동기] (WR) 키워드별 청크 그룹과 시나리오를 받아 복잡한 쿼리를 생성합니다.
        [수정] distribution에 할당된 만큼만 랜덤 키워드 그룹을 선택하여 생성합니다.
        """
        if not all_chunks or not keyword_index or not scenarios:
            return []
            
        complex_groups = self._get_complex_chunk_groups(all_chunks, keyword_index)
        if not complex_groups:
            logger.warning("ComplexQueriesWR: 키워드 그룹이 없어 쿼리를 생성할 수 없습니다.")
            return []
            
        tasks = []

        # 1. Complex Multi
        num_multi = distribution.get("WR_COMPLEX_MULTI", 0)
        if num_multi > 0:
            chunks = random.choice(complex_groups)
            scenario = random.choice(scenarios)
            context = self._combine_chunks_for_context(chunks)
            refs = [c.chunk_idx for c in chunks]
            tasks.append(self._call_llm_and_parse_async(
                context, scenario, prompt_generate_complex_multi_queries_wr,
                QueryType.COMPLEX_MULTI, num_multi, refs
            ))

        # 2. Complex Comp
        num_comp = distribution.get("WR_COMPLEX_COMP", 0)
        if num_comp > 0:
            chunks = random.choice(complex_groups)
            scenario = random.choice(scenarios)
            context = self._combine_chunks_for_context(chunks)
            refs = [c.chunk_idx for c in chunks]
            tasks.append(self._call_llm_and_parse_async(
                context, scenario, prompt_generate_complex_comp_queries_wr,
                QueryType.COMPLEX_COMP, num_comp, refs
            ))

        # 3. Complex Infer
        num_infer = distribution.get("WR_COMPLEX_INFER", 0)
        if num_infer > 0:
            chunks = random.choice(complex_groups)
            scenario = random.choice(scenarios)
            context = self._combine_chunks_for_context(chunks)
            refs = [c.chunk_idx for c in chunks]
            tasks.append(self._call_llm_and_parse_async(
                context, scenario, prompt_generate_complex_infer_queries_wr,
                QueryType.COMPLEX_INFER, num_infer, refs
            ))

        # 4. Complex Cond
        num_cond = distribution.get("WR_COMPLEX_COND", 0)
        if num_cond > 0:
            chunks = random.choice(complex_groups)
            scenario = random.choice(scenarios)
            context = self._combine_chunks_for_context(chunks)
            refs = [c.chunk_idx for c in chunks]
            tasks.append(self._call_llm_and_parse_async(
                context, scenario, prompt_generate_complex_cond_queries_wr,
                QueryType.COMPLEX_COND, num_cond, refs
            ))

        if not tasks:
            return []
            
        try:
            results = await asyncio.gather(*tasks, return_exceptions=True)
        except Exception as e:
            logger.error(f"ComplexQueriesWR 비동기 실행 중 오류: {e}")
            return []
            
        final_queries: List[Query] = []
        for result in results:
            if isinstance(result, list):
                final_queries.extend(result)
            elif isinstance(result, Exception):
                logger.warning(f"ComplexQueriesWR 작업 실패: {result}")

        return final_queries


    # [수정] (distribution: dict) 인자 추가 및 로직 변경
    async def _generateSimpleQueriesNR(self, summaries: list[DocSummary], scenarios: list[Scenario], distribution: Dict[str, int]) -> list[Query]:
        """
        [비동기] (NR) **페이지 요약**과 시나리오를 받아 레퍼런스 없는 간단한 쿼리를 생성합니다.
        [수정] distribution에 할당된 만큼만 랜덤 페이지 요약을 선택하여 생성합니다.
        """
        if not summaries or not scenarios:
            return []
            
        # 모든 문서의 모든 페이지 요약을 하나의 리스트로
        all_page_exps = [page_exp for doc_summary in summaries for page_exp in doc_summary.pageExplanations]
        if not all_page_exps:
            logger.warning("SimpleQueriesNR: 페이지 요약이 없어 쿼리를 생성할 수 없습니다.")
            return []

        tasks = []

        # 1. Simple Search NR
        num_search = distribution.get("NR_SIMPLE_SEARCH", 0)
        if num_search > 0:
            page_exp = random.choice(all_page_exps)
            scenario = random.choice(scenarios)
            context_text = page_exp.explanation[:MAX_CONTEXT_LENGTH]
            tasks.append(self._call_llm_and_parse_async(
                context_text, scenario, prompt_generate_simple_search_queries_nr,
                QueryType.SIMPLE_SEARCH, num_search, None
            ))

        # 2. Simple Expln NR
        num_expln = distribution.get("NR_SIMPLE_EXPLN", 0)
        if num_expln > 0:
            page_exp = random.choice(all_page_exps)
            scenario = random.choice(scenarios)
            context_text = page_exp.explanation[:MAX_CONTEXT_LENGTH]
            tasks.append(self._call_llm_and_parse_async(
                context_text, scenario, prompt_generate_simple_expln_queries_nr,
                QueryType.SIMPLE_EXPLN, num_expln, None
            ))

        # 3. Simple TF NR
        num_tf = distribution.get("NR_SIMPLE_TF", 0)
        if num_tf > 0:
            page_exp = random.choice(all_page_exps)
            scenario = random.choice(scenarios)
            context_text = page_exp.explanation[:MAX_CONTEXT_LENGTH]
            tasks.append(self._call_llm_and_parse_async(
                context_text, scenario, prompt_generate_simple_tf_queries_nr,
                QueryType.SIMPLE_TF, num_tf, None
            ))
            
        if not tasks:
            return []

        try:
            results = await asyncio.gather(*tasks, return_exceptions=True)
        except Exception as e:
            logger.error(f"SimpleQueriesNR 비동기 실행 중 오류: {e}")
            return []

        final_queries: List[Query] = []
        for result in results:
            if isinstance(result, list):
                final_queries.extend(result)
            elif isinstance(result, Exception):
                logger.warning(f"SimpleQueriesNR 작업 실패: {result}")
                
        return final_queries

    # [수정] (distribution: dict) 인자 추가 및 로직 변경
    async def _generateComplexQueriesNR(self, summaries: list[DocSummary], scenarios: list[Scenario], distribution: Dict[str, int]) -> list[Query]:
        """
        [비동기] (NR) **문서 전체 요약**과 시나리오를 받아 레퍼런스 없는 복잡한 쿼리를 생성합니다.
        [수정] distribution에 할당된 만큼만 랜덤 문서 요약을 선택하여 생성합니다.
        """
        if not summaries or not scenarios:
            return []

        # 모든 문서 요약을 하나의 리스트로
        all_doc_exps = [doc_summary.docExplanation for doc_summary in summaries if doc_summary.docExplanation]
        if not all_doc_exps:
            logger.warning("ComplexQueriesNR: 문서 요약이 없어 쿼리를 생성할 수 없습니다.")
            return []
            
        tasks = []

        # 1. Complex Multi NR
        num_multi = distribution.get("NR_COMPLEX_MULTI", 0)
        if num_multi > 0:
            doc_exp = random.choice(all_doc_exps)
            scenario = random.choice(scenarios)
            context_text = doc_exp.explanation[:MAX_CONTEXT_LENGTH]
            tasks.append(self._call_llm_and_parse_async(
                context_text, scenario, prompt_generate_complex_multi_queries_nr,
                QueryType.COMPLEX_MULTI, num_multi, None
            ))

        # 2. Complex Comp NR
        num_comp = distribution.get("NR_COMPLEX_COMP", 0)
        if num_comp > 0:
            doc_exp = random.choice(all_doc_exps)
            scenario = random.choice(scenarios)
            context_text = doc_exp.explanation[:MAX_CONTEXT_LENGTH]
            tasks.append(self._call_llm_and_parse_async(
                context_text, scenario, prompt_generate_complex_comp_queries_nr,
                QueryType.COMPLEX_COMP, num_comp, None
            ))

        # 3. Complex Infer NR
        num_infer = distribution.get("NR_COMPLEX_INFER", 0)
        if num_infer > 0:
            doc_exp = random.choice(all_doc_exps)
            scenario = random.choice(scenarios)
            context_text = doc_exp.explanation[:MAX_CONTEXT_LENGTH]
            tasks.append(self._call_llm_and_parse_async(
                context_text, scenario, prompt_generate_complex_infer_queries_nr,
                QueryType.COMPLEX_INFER, num_infer, None
            ))
            
        # 4. Complex Cond NR
        num_cond = distribution.get("NR_COMPLEX_COND", 0)
        if num_cond > 0:
            doc_exp = random.choice(all_doc_exps)
            scenario = random.choice(scenarios)
            context_text = doc_exp.explanation[:MAX_CONTEXT_LENGTH]
            tasks.append(self._call_llm_and_parse_async(
                context_text, scenario, prompt_generate_complex_cond_queries_nr,
                QueryType.COMPLEX_COND, num_cond, None
            ))

        if not tasks:
            return []

        try:
            results = await asyncio.gather(*tasks, return_exceptions=True)
        except Exception as e:
            logger.error(f"ComplexQueriesNR 비동기 실행 중 오류: {e}")
            return []
            
        final_queries: List[Query] = []
        for result in results:
            if isinstance(result, list):
                final_queries.extend(result)
            elif isinstance(result, Exception):
                logger.warning(f"ComplexQueriesNR 작업 실패: {result}")

        return final_queries


    # [수정] (distribution: dict) 인자 추가
    async def _generateQueriesWithReference(self, all_chunks: list[Chunk], keyword_index: dict, scenarios: list[Scenario], distribution: Dict[str, int]) -> list[Query]:
        """
        [비동기] 레퍼런스 기반 쿼리 생성을 총괄합니다.
        """
        logger.info("레퍼런스 기반(WR) 쿼리 생성을 시작합니다...")
        
        simple_queries_wr = await self._generateSimpleQueriesWR(all_chunks, scenarios, distribution)
        logger.info(f"  - 단순(WR) 쿼리 {len(simple_queries_wr)}개 생성 완료.")
        
        complex_queries_wr = await self._generateComplexQueriesWR(all_chunks, keyword_index, scenarios, distribution)
        logger.info(f"  - 복잡(WR) 쿼리 {len(complex_queries_wr)}개 생성 완료.")

        return simple_queries_wr + complex_queries_wr


    # [수정] (distribution: dict) 인자 추가
    async def _generateQueriesNoReference(self, summaries: list[DocSummary], scenarios: list[Scenario], distribution: Dict[str, int]) -> list[Query]:
        """
        [비동기] 레퍼런스 없는 쿼리 생성을 총괄합니다.
        """
        logger.info("레퍼런스 미기반(NR) 쿼리 생성을 시작합니다...")
        
        simple_queries_nr = await self._generateSimpleQueriesNR(summaries, scenarios, distribution)
        logger.info(f"  - 단순(NR) 쿼리 {len(simple_queries_nr)}개 생성 완료.")
        
        complex_queries_nr = await self._generateComplexQueriesNR(summaries, scenarios, distribution)
        logger.info(f"  - 복잡(NR) 쿼리 {len(complex_queries_nr)}개 생성 완료.")

        return simple_queries_nr + complex_queries_nr

    # [수정] (distribution: dict) 인자 추가
    async def _async_generate_all(
        self, 
        all_chunks: list[Chunk], 
        summaries: list[DocSummary], 
        keyword_index: dict, 
        scenarios: list[Scenario],
        distribution: Dict[str, int]
    ) -> list[Query]:
        """
        [비동기] (Internal) 모든 비동기 생성 작업을 병렬로 실행합니다.
        """
        logger.info("내부 비동기 쿼리 생성 코어를 시작합니다...")
        
        results = await asyncio.gather(
            self._generateQueriesWithReference(all_chunks, keyword_index, scenarios, distribution),
            self._generateQueriesNoReference(summaries, scenarios, distribution),
            return_exceptions=True
        )
        
        total_queries: List[Query] = []
        queries_wr: List[Query] = []
        queries_nr: List[Query] = []

        if isinstance(results[0], list):
            queries_wr = results[0]
            total_queries.extend(queries_wr)
        elif isinstance(results[0], Exception):
            logger.error(f"_generateQueriesWithReference 작업 실패: {results[0]}")

        if isinstance(results[1], list):
            queries_nr = results[1]
            total_queries.extend(queries_nr)
        elif isinstance(results[1], Exception):
            logger.error(f"_generateQueriesNoReference 작업 실패: {results[1]}")

        return total_queries, len(queries_wr), len(queries_nr)


    # --- 5.2. Public Methods ---
    # [수정] Public 함수의 시그니처 변경 (num_total_queries 추가)
    def generate_all_queries(
        self, 
        all_chunks: list[Chunk], 
        summaries: list[DocSummary], 
        keyword_index: dict, 
        scenarios: list[Scenario],
        num_total_queries: int  # [신규] 총 쿼리 개수 입력
    ) -> list[Query]:
        """
        [동기] (Public) 모든 쿼리 생성 로직을 총괄 실행합니다.
        [수정] num_total_queries를 받아 쿼리 개수를 분배합니다.
        """
        logger.info(f"전체 쿼리 생성 (동기 래퍼) 시작 (목표: {num_total_queries}개)...")
        
        if num_total_queries <= 0:
            logger.warning("num_total_queries가 0 이하이므로 쿼리를 생성하지 않습니다.")
            return []
            
        try:
            # [신규] 쿼리 개수 분배
            distribution = self._distribute_queries(num_total_queries)

            # [수정] _async_generate_all로 distribution 전달
            total_queries, wr_count, nr_count = asyncio.run(self._async_generate_all(
                all_chunks, summaries, keyword_index, scenarios, distribution
            ))
            
            logger.info(f"총 {len(total_queries)}개의 쿼리 생성 완료. (WR: {wr_count}, NR: {nr_count})")
            
            if len(total_queries) != num_total_queries:
                 logger.warning(f"목표 쿼리 개수({num_total_queries})와 실제 생성된 쿼리 개수({len(total_queries)})가 다릅니다. LLM 응답 파싱 실패 또는 컨텍스트 부족일 수 있습니다.")
            
            return total_queries
            
        except RuntimeError as e:
            if "cannot run current event loop" in str(e):
                logger.error("치명적 오류: 이미 실행 중인 이벤트 루프에서 asyncio.run()이 호출되었습니다. (Jupyter/Colab 환경인지 확인하세요)")
            else:
                logger.error(f"generate_all_queries에서 예기치 않은 런타임 오류: {e}")
            return []
        except Exception as e:
            logger.error(f"generate_all_queries 실행 중 오류 발생: {e}")
            return []