import asyncio
import logging
import random
import re
import json
from typing import List, Dict, Optional, Tuple, Set, Iterator, Any
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
from core.utils.query_generator.config import MAX_WORKERS, MAX_CONTEXT_LENGTH

logger = logging.getLogger(__name__)

QUERY_DISTRIBUTION_WEIGHTS = {
    # With Reference (WR) - 13
    "WR_SIMPLE_SEARCH": 1,
    "WR_SIMPLE_EXPLN": 1,
    "WR_SIMPLE_TF": 1,
    "WR_COMPLEX_MULTI": 1,
    "WR_COMPLEX_COMP": 1,
    "WR_COMPLEX_INFER": 1,
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
TOTAL_BASE_WEIGHT = sum(QUERY_DISTRIBUTION_WEIGHTS.values()) 

MIN_CHUNKS_FOR_COMPLEX_QUERY = 3    # 복잡 쿼리 생성을 위한 최소 청크 수


class QueryGenerator:
    """
    🎭 QueryGenerator 클래스
    역할 (Responsibility): 분석된 문서 요약(DocSummary)을 바탕으로 쿼리 생성의 맥락이 될 페르소나와 시나리오를 생성합니다.
    
    [개선사항]
    1. Shuffle & Round-Robin Iterator 적용으로 데이터 편향 방지 (random.choice 제거)
    2. 비동기 메서드(generate_all_queries_async) 명시적 노출로 아키텍처 개선
    """

    def __init__(self, llm_adapter: BaseLLMAdapter):
        self.llm_adapter = llm_adapter

    # --- 5.1. Private Methods (Helper) ---

    def _distribute_queries(self, num_total_queries: int) -> Dict[str, int]:
        """
        [Helper] 총 쿼리 개수를 입력받아, QUERY_DISTRIBUTION_WEIGHTS 비율대로 각 타입에 분배합니다.
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

        queries_to_distribute = num_total_queries - current_total
        remainders.sort(key=lambda x: x[1], reverse=True)
        
        for i in range(queries_to_distribute):
            key_to_increment = remainders[i][0]
            allocated[key_to_increment] += 1
            
        logger.debug(f"쿼리 분배 결과: {allocated}")
        return allocated

    def _get_shuffled_iterator(self, items: List[Any]) -> Iterator[Any]:
        """
        [Helper] 리스트를 섞어서 무한히 반환하는 제너레이터 (Round-Robin with Shuffle).
        데이터가 편향되지 않고 골고루 선택되도록 합니다.
        """
        if not items:
            return
        
        # 원본 보존을 위해 복사
        shuffled = list(items)
        random.shuffle(shuffled)
        
        while True:
            for item in shuffled:
                yield item
            # 한 바퀴 다 돌면 다시 섞어서 시작
            random.shuffle(shuffled)

    def _parse_json_queries(self, response_text: str, query_type: QueryType, reference_chunks: Optional[List[int]]) -> List[Query]:
        """ [동기] LLM 응답(JSON 문자열 리스트)을 파싱하여 Query 객체 리스트로 변환합니다. """
        try:
            json_match = re.search(r'\[.*\]', response_text, re.DOTALL)
            if not json_match:
                # 파싱 실패 시 로그를 남기고 빈 리스트 반환 -> 호출부에서 재시도 트리거됨
                logger.warning(f"LLM 응답에서 JSON 리스트를 찾지 못했습니다. 응답: {response_text[:100]}...")
                return []

            json_data = json.loads(json_match.group(0))
            
            queries = []
            for item in json_data:
                if isinstance(item, str):
                    queries.append(Query(
                        query=item,
                        answer=None,
                        type=query_type, 
                        reference=reference_chunks
                    ))
                elif isinstance(item, dict):
                    queries.append(Query(
                        query=item["question"],
                        answer=item.get("answer"),
                        type=query_type,
                        reference=reference_chunks
                    ))
            return queries

        except json.JSONDecodeError as e:
            logger.error(f"JSON 파싱 실패: {e}. 원본 응답: {response_text[:200]}")
            return []
        except Exception as e:
            logger.error(f"쿼리 파싱 중 알 수 없는 오류: {e}")
            return []

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
        reference_chunks: Optional[List[int]],
        max_retries: int = 3  # 재시도 횟수 인자 추가
    ) -> List[Query]:
        """ [비동기] 단일 LLM 호출을 실행하고 결과를 파싱합니다. (재시도 로직 포함) """
        if not prompt_template or not prompt_template.strip() or num_queries <= 0:
            return []
            
        persona = scenario.persona
        task = scenario.scenarios[0] if scenario.scenarios else "정보 검색"

        prompt = prompt_template.format(
            context=context_text,
            persona=persona,
            task=task,
            num_queries=num_queries
        )

        # [변경] 재시도 로직 추가
        for attempt in range(max_retries):
            try:
                # [변경] MAX_WORKERS를 인자로 전달하여 API 호출
                results = await self.llm_adapter.request_async_batch(
                    prompts=[prompt], 
                    queries=[""], 
                    max_workers=MAX_WORKERS
                )
                
                if not results:
                    raise ValueError("LLM 어댑터가 빈 결과를 반환했습니다.")

                result = results[0]
                if isinstance(result, Exception):
                    raise result
                    
                response_text = result.get("text", "")
                
                # 응답 파싱
                queries = self._parse_json_queries(response_text, query_type, reference_chunks)
                
                # 파싱된 쿼리가 있으면 성공으로 간주하고 반환
                if queries:
                    return queries
                else:
                    # 파싱 실패(빈 리스트) -> 재시도 트리거
                    logger.warning(f"[{query_type.value}] 생성 실패 (파싱 오류 또는 빈 결과), 재시도 {attempt + 1}/{max_retries}...")

            except Exception as e:
                logger.warning(f"[{query_type.value}] API 호출 또는 처리 중 에러: {e}, 재시도 {attempt + 1}/{max_retries}...")


        logger.error(f"[{query_type.value}] {max_retries}회 시도 후에도 쿼리 생성 실패.")
        return []

    def _group_chunks_by_page(self, all_chunks: List[Chunk]) -> Dict[Tuple[int, int], List[Chunk]]:
        page_groups: Dict[Tuple[int, int], List[Chunk]] = defaultdict(list)
        for chunk in all_chunks:
            page_groups[(chunk.doc_idx, chunk.page_idx)].append(chunk)
        return page_groups

    def _get_complex_chunk_groups(self, all_chunks: List[Chunk], keyword_index: Dict[str, List[int]]) -> List[List[Chunk]]:
        chunk_map: Dict[int, Chunk] = {chunk.chunk_idx: chunk for chunk in all_chunks}
        groups: List[List[Chunk]] = []
        for keyword, chunk_indices in keyword_index.items():
            if len(chunk_indices) >= MIN_CHUNKS_FOR_COMPLEX_QUERY:
                chunk_group = [chunk_map[idx] for idx in chunk_indices if idx in chunk_map]
                if len(chunk_group) >= MIN_CHUNKS_FOR_COMPLEX_QUERY:
                    groups.append(chunk_group)
        return groups

    def _combine_chunks_for_context(self, chunks: List[Chunk]) -> str:
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
            logger.warning(f"컨텍스트 길이가 초과되어 잘림. (원본: {original_len}자)")

        return context_text

    # --- 5.2. Private Methods (Core Logic with Iterator) ---

    async def _generateSimpleQueriesWR(self, all_chunks: list[Chunk], scenarios: list[Scenario], distribution: Dict[str, int]) -> list[Query]:
        if not all_chunks or not scenarios:
            return []

        page_groups = self._group_chunks_by_page(all_chunks)
        if not page_groups:
            return []
            
        # [변경] Random Choice -> Shuffled Iterator 사용
        page_list = list(page_groups.values())
        page_iter = self._get_shuffled_iterator(page_list)
        scenario_iter = self._get_shuffled_iterator(scenarios)
        
        tasks = []
        
        # 1. Simple Search (1개씩 요청하여 문서 다양성 확보)
        num_search = distribution.get("WR_SIMPLE_SEARCH", 0)
        for _ in range(num_search):
            chunks = next(page_iter)
            scenario = next(scenario_iter)
            context = self._combine_chunks_for_context(chunks)
            refs = [c.chunk_idx for c in chunks]
            tasks.append(self._call_llm_and_parse_async(
                context, scenario, prompt_generate_simple_search_queries_wr,
                QueryType.SIMPLE_SEARCH, 1, refs
            ))

        # 2. Simple Expln
        num_expln = distribution.get("WR_SIMPLE_EXPLN", 0)
        for _ in range(num_expln):
            chunks = next(page_iter)
            scenario = next(scenario_iter)
            context = self._combine_chunks_for_context(chunks)
            refs = [c.chunk_idx for c in chunks]
            tasks.append(self._call_llm_and_parse_async(
                context, scenario, prompt_generate_simple_expln_queries_wr,
                QueryType.SIMPLE_EXPLN, 1, refs
            ))
            
        # 3. Simple TF
        num_tf = distribution.get("WR_SIMPLE_TF", 0)
        for _ in range(num_tf):
            chunks = next(page_iter)
            scenario = next(scenario_iter)
            context = self._combine_chunks_for_context(chunks)
            refs = [c.chunk_idx for c in chunks]
            tasks.append(self._call_llm_and_parse_async(
                context, scenario, prompt_generate_simple_tf_queries_wr,
                QueryType.SIMPLE_TF, 1, refs
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

    async def _generateComplexQueriesWR(self, all_chunks: list[Chunk], keyword_index: dict, scenarios: list[Scenario], distribution: Dict[str, int]) -> list[Query]:
        if not all_chunks or not keyword_index or not scenarios:
            return []
            
        complex_groups = self._get_complex_chunk_groups(all_chunks, keyword_index)
        if not complex_groups:
            return []
            
        # [변경] Random Choice -> Shuffled Iterator 사용
        group_iter = self._get_shuffled_iterator(complex_groups)
        scenario_iter = self._get_shuffled_iterator(scenarios)
        
        tasks = []

        # 1. Complex Multi
        num_multi = distribution.get("WR_COMPLEX_MULTI", 0)
        for _ in range(num_multi):
            chunks = next(group_iter)
            scenario = next(scenario_iter)
            context = self._combine_chunks_for_context(chunks)
            refs = [c.chunk_idx for c in chunks]
            tasks.append(self._call_llm_and_parse_async(
                context, scenario, prompt_generate_complex_multi_queries_wr,
                QueryType.COMPLEX_MULTI, 1, refs
            ))

        # 2. Complex Comp
        num_comp = distribution.get("WR_COMPLEX_COMP", 0)
        for _ in range(num_comp):
            chunks = next(group_iter)
            scenario = next(scenario_iter)
            context = self._combine_chunks_for_context(chunks)
            refs = [c.chunk_idx for c in chunks]
            tasks.append(self._call_llm_and_parse_async(
                context, scenario, prompt_generate_complex_comp_queries_wr,
                QueryType.COMPLEX_COMP, 1, refs
            ))

        # 3. Complex Infer
        num_infer = distribution.get("WR_COMPLEX_INFER", 0)
        for _ in range(num_infer):
            chunks = next(group_iter)
            scenario = next(scenario_iter)
            context = self._combine_chunks_for_context(chunks)
            refs = [c.chunk_idx for c in chunks]
            tasks.append(self._call_llm_and_parse_async(
                context, scenario, prompt_generate_complex_infer_queries_wr,
                QueryType.COMPLEX_INFER, 1, refs
            ))

        # 4. Complex Cond
        num_cond = distribution.get("WR_COMPLEX_COND", 0)
        for _ in range(num_cond):
            chunks = next(group_iter)
            scenario = next(scenario_iter)
            context = self._combine_chunks_for_context(chunks)
            refs = [c.chunk_idx for c in chunks]
            tasks.append(self._call_llm_and_parse_async(
                context, scenario, prompt_generate_complex_cond_queries_wr,
                QueryType.COMPLEX_COND, 1, refs
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


    async def _generateSimpleQueriesNR(self, summaries: list[DocSummary], scenarios: list[Scenario], distribution: Dict[str, int]) -> list[Query]:
        if not summaries or not scenarios:
            return []
            
        all_page_exps = [page_exp for doc_summary in summaries for page_exp in doc_summary.pageExplanations]
        if not all_page_exps:
            return []

        # Shuffled Iterator 사용, 랜덤하면서 균일한 뽑기
        page_iter = self._get_shuffled_iterator(all_page_exps)
        scenario_iter = self._get_shuffled_iterator(scenarios)
        
        tasks = []

        # 1. Simple Search NR
        num_search = distribution.get("NR_SIMPLE_SEARCH", 0)
        for _ in range(num_search):
            page_exp = next(page_iter)
            scenario = next(scenario_iter)
            context_text = page_exp.explanation[:MAX_CONTEXT_LENGTH]
            tasks.append(self._call_llm_and_parse_async(
                context_text, scenario, prompt_generate_simple_search_queries_nr,
                QueryType.SIMPLE_SEARCH, 1, None
            ))

        # 2. Simple Expln NR
        num_expln = distribution.get("NR_SIMPLE_EXPLN", 0)
        for _ in range(num_expln):
            page_exp = next(page_iter)
            scenario = next(scenario_iter)
            context_text = page_exp.explanation[:MAX_CONTEXT_LENGTH]
            tasks.append(self._call_llm_and_parse_async(
                context_text, scenario, prompt_generate_simple_expln_queries_nr,
                QueryType.SIMPLE_EXPLN, 1, None
            ))

        # 3. Simple TF NR
        num_tf = distribution.get("NR_SIMPLE_TF", 0)
        for _ in range(num_tf):
            page_exp = next(page_iter)
            scenario = next(scenario_iter)
            context_text = page_exp.explanation[:MAX_CONTEXT_LENGTH]
            tasks.append(self._call_llm_and_parse_async(
                context_text, scenario, prompt_generate_simple_tf_queries_nr,
                QueryType.SIMPLE_TF, 1, None
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

    async def _generateComplexQueriesNR(self, summaries: list[DocSummary], scenarios: list[Scenario], distribution: Dict[str, int]) -> list[Query]:
        if not summaries or not scenarios:
            return []

        all_doc_exps = [doc_summary.docExplanation for doc_summary in summaries if doc_summary.docExplanation]
        if not all_doc_exps:
            return []
            
        # Shuffled Iterator 사용
        doc_iter = self._get_shuffled_iterator(all_doc_exps)
        scenario_iter = self._get_shuffled_iterator(scenarios)
        
        tasks = []

        # 1. Complex Multi NR
        num_multi = distribution.get("NR_COMPLEX_MULTI", 0)
        for _ in range(num_multi):
            doc_exp = next(doc_iter)
            scenario = next(scenario_iter)
            context_text = doc_exp.explanation[:MAX_CONTEXT_LENGTH]
            tasks.append(self._call_llm_and_parse_async(
                context_text, scenario, prompt_generate_complex_multi_queries_nr,
                QueryType.COMPLEX_MULTI, 1, None
            ))

        # 2. Complex Comp NR
        num_comp = distribution.get("NR_COMPLEX_COMP", 0)
        for _ in range(num_comp):
            doc_exp = next(doc_iter)
            scenario = next(scenario_iter)
            context_text = doc_exp.explanation[:MAX_CONTEXT_LENGTH]
            tasks.append(self._call_llm_and_parse_async(
                context_text, scenario, prompt_generate_complex_comp_queries_nr,
                QueryType.COMPLEX_COMP, 1, None
            ))

        # 3. Complex Infer NR
        num_infer = distribution.get("NR_COMPLEX_INFER", 0)
        for _ in range(num_infer):
            doc_exp = next(doc_iter)
            scenario = next(scenario_iter)
            context_text = doc_exp.explanation[:MAX_CONTEXT_LENGTH]
            tasks.append(self._call_llm_and_parse_async(
                context_text, scenario, prompt_generate_complex_infer_queries_nr,
                QueryType.COMPLEX_INFER, 1, None
            ))
            
        # 4. Complex Cond NR
        num_cond = distribution.get("NR_COMPLEX_COND", 0)
        for _ in range(num_cond):
            doc_exp = next(doc_iter)
            scenario = next(scenario_iter)
            context_text = doc_exp.explanation[:MAX_CONTEXT_LENGTH]
            tasks.append(self._call_llm_and_parse_async(
                context_text, scenario, prompt_generate_complex_cond_queries_nr,
                QueryType.COMPLEX_COND, 1, None
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

    async def _async_generate_all(
        self, 
        all_chunks: list[Chunk], 
        summaries: list[DocSummary], 
        keyword_index: dict, 
        scenarios: list[Scenario],
        distribution: Dict[str, int]
    ) -> Tuple[List[Query], int, int]:
        """
        [비동기] (Internal) 모든 비동기 생성 작업을 병렬로 실행합니다.
        """
        logger.info("내부 비동기 쿼리 생성 코어를 시작합니다...")
        
        # WR과 NR 작업을 동시에 시작
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

    async def _generateQueriesWithReference(self, all_chunks: list[Chunk], keyword_index: dict, scenarios: list[Scenario], distribution: Dict[str, int]) -> list[Query]:
        logger.info("레퍼런스 기반(WR) 쿼리 생성을 시작합니다...")
        simple_queries_wr = await self._generateSimpleQueriesWR(all_chunks, scenarios, distribution)
        complex_queries_wr = await self._generateComplexQueriesWR(all_chunks, keyword_index, scenarios, distribution)
        return simple_queries_wr + complex_queries_wr

    async def _generateQueriesNoReference(self, summaries: list[DocSummary], scenarios: list[Scenario], distribution: Dict[str, int]) -> list[Query]:
        logger.info("레퍼런스 미기반(NR) 쿼리 생성을 시작합니다...")
        simple_queries_nr = await self._generateSimpleQueriesNR(summaries, scenarios, distribution)
        complex_queries_nr = await self._generateComplexQueriesNR(summaries, scenarios, distribution)
        return simple_queries_nr + complex_queries_nr

    # --- 5.3. Public Methods ---

    async def generate_all_queries_async(
        self, 
        all_chunks: list[Chunk], 
        summaries: list[DocSummary], 
        keyword_index: dict, 
        scenarios: list[Scenario],
        num_total_queries: int
    ) -> list[Query]:
        """
        [비동기] (Public) 모든 쿼리 생성 로직을 총괄 실행합니다.
        
        [사용법]
        await query_generator.generate_all_queries_async(...)
        """
        logger.info(f"전체 쿼리 생성 (비동기) 시작 (목표: {num_total_queries}개)...")
        
        if num_total_queries <= 0:
            logger.warning("num_total_queries가 0 이하이므로 쿼리를 생성하지 않습니다.")
            return []
            
        try:
            # 쿼리 개수 분배
            distribution = self._distribute_queries(num_total_queries)

            # 비동기 코어 실행 (await)
            total_queries, wr_count, nr_count = await self._async_generate_all(
                all_chunks, summaries, keyword_index, scenarios, distribution
            )
            
            logger.info(f"총 {len(total_queries)}개의 쿼리 생성 완료. (WR: {wr_count}, NR: {nr_count})")
            return total_queries
            
        except Exception as e:
            logger.error(f"generate_all_queries_async 실행 중 오류 발생: {e}")
            return []

    def generate_all_queries_sync(
        self, 
        all_chunks: list[Chunk], 
        summaries: list[DocSummary], 
        keyword_index: dict, 
        scenarios: list[Scenario],
        num_total_queries: int
    ) -> list[Query]:
        """
        [동기] (Public Wrapper) generate_all_queries_async를 동기적으로 실행합니다.
        
        [주의]
        Jupyter Notebook, FastAPI 등 이미 Event Loop가 실행 중인 환경에서는 
        이 메서드 대신 generate_all_queries_async를 await로 호출해야 합니다.
        """
        try:
            return asyncio.run(self.generate_all_queries_async(
                all_chunks, summaries, keyword_index, scenarios, num_total_queries
            ))
        except RuntimeError as e:
            if "cannot run current event loop" in str(e):
                logger.error("이미 실행 중인 이벤트 루프가 감지되었습니다. await generate_all_queries_async(...)를 사용하세요.")
            raise e