import asyncio
import logging
import random
import re
import json
from typing import List, Dict, Optional, Tuple
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

# --- 생성할 쿼리 개수 설정 ---
NUM_QUERIES_SIMPLE_WR_PER_TYPE = 2  # 페이지별, 단순 타입별 생성 개수
NUM_QUERIES_COMPLEX_WR_PER_TYPE = 2 # 키워드별, 복잡 타입별 생성 개수
NUM_QUERIES_SIMPLE_NR_PER_TYPE = 2  # 페이지 요약별, 단순 타입별 생성 개수
NUM_QUERIES_COMPLEX_NR_PER_TYPE = 2 # 문서 요약별, 복잡 타입별 생성 개수
MIN_CHUNKS_FOR_COMPLEX_QUERY = 3    # 복잡 쿼리 생성을 위한 최소 청크 수


class QueryGenerator:
    """
    🎭 QueryGenerator 클래스
    역할 (Responsibility): 분석된 문서 요약(DocSummary)을 바탕으로 쿼리 생성의 맥락이 될 페르소나와 시나리오를 생성합니다.
    """

    def __init__(self, llm_adapter: BaseLLMAdapter):
        self.llm_adapter = llm_adapter

    # --- 5.1. Private Methods (Helper) ---

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
        
        # 프롬프트가 비어있으면(정의되지 않았으면) 실행하지 않음
        if not prompt_template or not prompt_template.strip():
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

    # --- 5.1. Private Methods (Docstring-based) ---
    # [수정] 모든 _generate... 함수를 async def로 변경하고,
    # 내부의 asyncio.run()을 await asyncio.gather()로 변경합니다.

    async def _generateSimpleQueriesWR(self, all_chunks: list[Chunk], scenarios: list[Scenario]) -> list[Query]:
        """
        [비동기] (WR) 페이지별 청크 그룹과 랜덤 시나리오를 받아 간단한 단일 홉 쿼리를 생성합니다.
        """
        if not all_chunks or not scenarios:
            return []

        page_groups = self._group_chunks_by_page(all_chunks)
        tasks = []

        for page_key, chunks in page_groups.items():
            scenario = random.choice(scenarios)
            context_text = "\n".join([chunk.text for chunk in chunks])
            reference_chunks = [chunk.chunk_idx for chunk in chunks]
            
            # 3가지 SIMPLE 타입에 대한 작업 생성
            tasks.append(self._call_llm_and_parse_async(
                context_text, scenario, prompt_generate_simple_search_queries_wr,
                QueryType.SIMPLE_SEARCH, NUM_QUERIES_SIMPLE_WR_PER_TYPE, reference_chunks
            ))
            tasks.append(self._call_llm_and_parse_async(
                context_text, scenario, prompt_generate_simple_expln_queries_wr,
                QueryType.SIMPLE_EXPLN, NUM_QUERIES_SIMPLE_WR_PER_TYPE, reference_chunks
            ))
            tasks.append(self._call_llm_and_parse_async(
                context_text, scenario, prompt_generate_simple_tf_queries_wr,
                QueryType.SIMPLE_TF, NUM_QUERIES_SIMPLE_WR_PER_TYPE, reference_chunks
            ))

        try:
            # [수정] asyncio.run() 제거 -> await asyncio.gather()
            results = await asyncio.gather(*tasks, return_exceptions=True)
        except Exception as e:
            logger.error(f"SimpleQueriesWR 비동기 실행 중 오류: {e}")
            return []

        # 결과 취합 (결과는 List[List[Query]] 형태)
        final_queries: List[Query] = []
        for result in results:
            if isinstance(result, list):
                final_queries.extend(result)
            elif isinstance(result, Exception):
                logger.warning(f"SimpleQueriesWR 작업 실패: {result}")
                
        return final_queries


    async def _generateComplexQueriesWR(self, all_chunks: list[Chunk], keyword_index: dict, scenarios: list[Scenario]) -> list[Query]:
        """
        [비동기] (WR) 키워드별 청크 그룹과 시나리오를 받아 복잡한 쿼리를 생성합니다.
        """
        if not all_chunks or not keyword_index or not scenarios:
            return []
            
        complex_groups = self._get_complex_chunk_groups(all_chunks, keyword_index)
        tasks = []

        for chunks in complex_groups:
            scenario = random.choice(scenarios)
            context_text = "\n".join([chunk.text for chunk in chunks])
            reference_chunks = [chunk.chunk_idx for chunk in chunks]

            # 4가지 COMPLEX 타입에 대한 작업 생성
            tasks.append(self._call_llm_and_parse_async(
                context_text, scenario, prompt_generate_complex_multi_queries_wr,
                QueryType.COMPLEX_MULTI, NUM_QUERIES_COMPLEX_WR_PER_TYPE, reference_chunks
            ))
            tasks.append(self._call_llm_and_parse_async(
                context_text, scenario, prompt_generate_complex_comp_queries_wr,
                QueryType.COMPLEX_COMP, NUM_QUERIES_COMPLEX_WR_PER_TYPE, reference_chunks
            ))
            tasks.append(self._call_llm_and_parse_async(
                context_text, scenario, prompt_generate_complex_infer_queries_wr,
                QueryType.COMPLEX_INFER, NUM_QUERIES_COMPLEX_WR_PER_TYPE, reference_chunks
            ))
            tasks.append(self._call_llm_and_parse_async(
                context_text, scenario, prompt_generate_complex_cond_queries_wr,
                QueryType.COMPLEX_COND, NUM_QUERIES_COMPLEX_WR_PER_TYPE, reference_chunks
            ))

        try:
            # [수정] asyncio.run() 제거 -> await asyncio.gather()
            results = await asyncio.gather(*tasks, return_exceptions=True)
        except Exception as e:
            logger.error(f"ComplexQueriesWR 비동기 실행 중 오류: {e}")
            return []
            
        # 결과 취합
        final_queries: List[Query] = []
        for result in results:
            if isinstance(result, list):
                final_queries.extend(result)
            elif isinstance(result, Exception):
                logger.warning(f"ComplexQueriesWR 작업 실패: {result}")

        return final_queries


    async def _generateSimpleQueriesNR(self, summaries: list[DocSummary], scenarios: list[Scenario]) -> list[Query]:
        """
        [비동기] (NR) **페이지 요약**과 시나리오를 받아 레퍼런스 없는 간단한 쿼리를 생성합니다.
        """
        if not summaries or not scenarios:
            return []
            
        tasks = []
        for doc_summary in summaries:
            for page_exp in doc_summary.pageExplanations:
                scenario = random.choice(scenarios)
                context_text = page_exp.explanation

                tasks.append(self._call_llm_and_parse_async(
                    context_text, scenario, prompt_generate_simple_search_queries_nr,
                    QueryType.SIMPLE_SEARCH, NUM_QUERIES_SIMPLE_NR_PER_TYPE, None
                ))
                tasks.append(self._call_llm_and_parse_async(
                    context_text, scenario, prompt_generate_simple_expln_queries_nr,
                    QueryType.SIMPLE_EXPLN, NUM_QUERIES_SIMPLE_NR_PER_TYPE, None
                ))
                tasks.append(self._call_llm_and_parse_async(
                    context_text, scenario, prompt_generate_simple_tf_queries_nr,
                    QueryType.SIMPLE_TF, NUM_QUERIES_SIMPLE_NR_PER_TYPE, None
                ))

        try:
            # [수정] asyncio.run() 제거 -> await asyncio.gather()
            results = await asyncio.gather(*tasks, return_exceptions=True)
        except Exception as e:
            logger.error(f"SimpleQueriesNR 비동기 실행 중 오류: {e}")
            return []

        # 결과 취합
        final_queries: List[Query] = []
        for result in results:
            if isinstance(result, list):
                final_queries.extend(result)
            elif isinstance(result, Exception):
                logger.warning(f"SimpleQueriesNR 작업 실패: {result}")
                
        return final_queries

    async def _generateComplexQueriesNR(self, summaries: list[DocSummary], scenarios: list[Scenario]) -> list[Query]:
        """
        [비동기] (NR) **문서 전체 요약**과 시나리오를 받아 레퍼런스 없는 복잡한 쿼리를 생성합니다.
        """
        if not summaries or not scenarios:
            return []

        tasks = []
        for doc_summary in summaries:
            doc_exp = doc_summary.docExplanation
            scenario = random.choice(scenarios)
            context_text = doc_exp.explanation

            tasks.append(self._call_llm_and_parse_async(
                context_text, scenario, prompt_generate_complex_multi_queries_nr,
                QueryType.COMPLEX_MULTI, NUM_QUERIES_COMPLEX_NR_PER_TYPE, None
            ))
            tasks.append(self._call_llm_and_parse_async(
                context_text, scenario, prompt_generate_complex_comp_queries_nr,
                QueryType.COMPLEX_COMP, NUM_QUERIES_COMPLEX_NR_PER_TYPE, None
            ))
            tasks.append(self._call_llm_and_parse_async(
                context_text, scenario, prompt_generate_complex_infer_queries_nr,
                QueryType.COMPLEX_INFER, NUM_QUERIES_COMPLEX_NR_PER_TYPE, None
            ))
            tasks.append(self._call_llm_and_parse_async(
                context_text, scenario, prompt_generate_complex_cond_queries_nr,
                QueryType.COMPLEX_COND, NUM_QUERIES_COMPLEX_NR_PER_TYPE, None
            ))

        try:
            # [수정] asyncio.run() 제거 -> await asyncio.gather()
            results = await asyncio.gather(*tasks, return_exceptions=True)
        except Exception as e:
            logger.error(f"ComplexQueriesNR 비동기 실행 중 오류: {e}")
            return []
            
        # 결과 취합
        final_queries: List[Query] = []
        for result in results:
            if isinstance(result, list):
                final_queries.extend(result)
            elif isinstance(result, Exception):
                logger.warning(f"ComplexQueriesNR 작업 실패: {result}")

        return final_queries


    async def _generateQueriesWithReference(self, all_chunks: list[Chunk], keyword_index: dict, scenarios: list[Scenario]) -> list[Query]:
        """
        [비동기] 레퍼런스 기반 쿼리 생성을 총괄합니다.
        """
        logger.info("레퍼런스 기반(WR) 쿼리 생성을 시작합니다...")
        
        # [수정] await 추가
        simple_queries_wr = await self._generateSimpleQueriesWR(all_chunks, scenarios)
        logger.info(f"  - 단순(WR) 쿼리 {len(simple_queries_wr)}개 생성 완료.")
        
        # [수정] await 추가
        complex_queries_wr = await self._generateComplexQueriesWR(all_chunks, keyword_index, scenarios)
        logger.info(f"  - 복잡(WR) 쿼리 {len(complex_queries_wr)}개 생성 완료.")

        return simple_queries_wr + complex_queries_wr


    async def _generateQueriesNoReference(self, summaries: list[DocSummary], scenarios: list[Scenario]) -> list[Query]:
        """
        [비동기] 레퍼런스 없는 쿼리 생성을 총괄합니다.
        """
        logger.info("레퍼런스 미기반(NR) 쿼리 생성을 시작합니다...")
        
        # [수정] await 추가
        simple_queries_nr = await self._generateSimpleQueriesNR(summaries, scenarios)
        logger.info(f"  - 단순(NR) 쿼리 {len(simple_queries_nr)}개 생성 완료.")
        
        # [수정] await 추가
        complex_queries_nr = await self._generateComplexQueriesNR(summaries, scenarios)
        logger.info(f"  - 복잡(NR) 쿼리 {len(complex_queries_nr)}개 생성 완료.")

        return simple_queries_nr + complex_queries_nr

    # [신규] 모든 비동기 작업을 실행할 내부 async 함수
    async def _async_generate_all(
        self, 
        all_chunks: list[Chunk], 
        summaries: list[DocSummary], 
        keyword_index: dict, 
        scenarios: list[Scenario]
    ) -> list[Query]:
        """
        [비동기] (Internal) 모든 비동기 생성 작업을 병렬로 실행합니다.
        """
        logger.info("내부 비동기 쿼리 생성 코어를 시작합니다...")
        
        # WR 작업과 NR 작업을 병렬로 실행
        results = await asyncio.gather(
            self._generateQueriesWithReference(all_chunks, keyword_index, scenarios),
            self._generateQueriesNoReference(summaries, scenarios),
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
    # [수정] Public 함수를 동기(def)로 변경하고, 내부에서 asyncio.run()을 "단 한번" 호출합니다.
    def generate_all_queries(
        self, 
        all_chunks: list[Chunk], 
        summaries: list[DocSummary], 
        keyword_index: dict, 
        scenarios: list[Scenario]
    ) -> list[Query]:
        """
        [동기] (Public) 모든 쿼리 생성 로직을 총괄 실행합니다.
        내부적으로 비동기 함수를 asyncio.run()으로 단 한번만 실행합니다.
        """
        logger.info("전체 쿼리 생성을 (동기 래퍼) 시작합니다...")
        
        try:
            # [수정] 모든 비동기 로직을 _async_generate_all로 옮기고,
            # 여기서 asyncio.run()을 "단 한 번만" 호출합니다.
            total_queries, wr_count, nr_count = asyncio.run(self._async_generate_all(
                all_chunks, summaries, keyword_index, scenarios
            ))
            
            logger.info(f"총 {len(total_queries)}개의 쿼리 생성 완료. (WR: {wr_count}, NR: {nr_count})")
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