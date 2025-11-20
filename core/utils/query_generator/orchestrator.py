import os
import logging
from typing import List, Union
from pathlib import Path
from datetime import datetime
from collections import Counter

# Configuration & Models
from core.utils.query_generator.config import LLM_MODEL, API_KEY, MAX_WORKERS, MAX_NUM_QUERIES, CHUNK_SIZE, CHUNK_OVERLAP, NUM_QUERIES_PER_PAGE, OUTPUT_PATH
from core.utils.query_generator.models import Chunk, Query

# Modules
from core.utils.query_generator.document_loader import DocumentProcessor
from core.utils.query_generator.content_analyzer import ContentAnalyzer
from core.utils.query_generator.scenario_generator import ScenarioGenerator
from core.utils.query_generator.query_generator import QueryGenerator

# Adapters (Assuming correct import path based on context)
from adapters.llm_adapter import OpenAIAdapter, GeminiAdapter

# Logging Setup
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class Orchestrator:
    """
    RAG 쿼리 생성 파이프라인 전체를 관장하는 Orchestrator 클래스.
    유저의 요청에 따라 문서 로딩부터 쿼리 생성, 저장까지의 흐름을 제어합니다.
    """

    def __init__(self):
        # 1. LLM Adapter 초기화
        # config.py의 설정을 사용하여 어댑터 생성
        self.llm_adapter = GeminiAdapter(model_name=LLM_MODEL, api_key=API_KEY)
        
        # 2. 하위 모듈 초기화 (Dependency Injection)
        self.processor = DocumentProcessor()
        self.analyzer = ContentAnalyzer(llm_adapter=self.llm_adapter)
        self.scenario_gen = ScenarioGenerator(llm_adapter=self.llm_adapter)
        self.query_gen = QueryGenerator(llm_adapter=self.llm_adapter)

    def generate_queries(
        self, 
        source: Union[str, List[Chunk]], 
    ) -> str:
        """
        전체 파이프라인을 실행하여 쿼리를 생성하고 저장합니다.

        Args:
            source (Union[str, List[Chunk]]): PDF 디렉토리 경로(str) 또는 청크 리스트(List[Chunk]).
            output_addr (str): 결과를 저장할 텍스트 파일 경로.
            num_queries_per_page (int): 페이지당 생성할 쿼리 개수.
            chunk_size (int): (PDF 로딩 시 사용) 청크 사이즈.
            chunk_overlap (int): (PDF 로딩 시 사용) 청크 오버랩.

        Returns:
            str: 저장된 파일의 경로.
        """
        
        all_chunks: List[Chunk] = []
        doc_names: List[str] = []

        # ---------------------------------------------------------
        # 1. Document Loading (입력 타입에 따른 분기)
        # ---------------------------------------------------------
        if isinstance(source, str):
            # Case A: 디렉토리 경로가 들어온 경우 -> 로더 실행
            logger.info(f"입력이 디렉토리 경로입니다: {source}")
            if not os.path.exists(source):
                raise FileNotFoundError(f"지정된 디렉토리를 찾을 수 없습니다: {source}")
            
            doc_names = [p.name for p in sorted(list(Path(source).glob('*.[pP][dD][fF]')))]
            all_chunks, lookup_index = self.processor.chunker(
                text_addr=source, 
                size=CHUNK_SIZE, 
                overlap=CHUNK_OVERLAP, 
                max_workers=MAX_WORKERS
            )
            
        elif isinstance(source, list):
            # Case B: 이미 처리된 청크 리스트가 들어온 경우 -> 로더 패스
            logger.info(f"입력이 청크 리스트({len(source)}개)입니다. DocumentProcessor를 건너뜁니다.")
            all_chunks = source
            unique_doc_indices = sorted(list(set(c.doc_idx for c in all_chunks)))
            doc_names = [f"doc_{i}" for i in unique_doc_indices]
            
        else:
            raise ValueError("source 인자는 '디렉토리 경로(str)' 또는 'Chunk 리스트(List[Chunk])'여야 합니다.")

        if not all_chunks:
            logger.warning("처리할 청크가 없습니다. 프로세스를 중단합니다.")
            return ""

        # ---------------------------------------------------------
        # *. Calculate Total Queries (페이지 수 기반 동적 계산)
        # ---------------------------------------------------------
        total_pages = len(set((c.doc_idx, c.page_idx) for c in all_chunks))
        num_total_queries = min(total_pages * NUM_QUERIES_PER_PAGE, MAX_NUM_QUERIES)
        logger.info(f"총 {total_pages} 페이지에 대해 약 {num_total_queries}개의 쿼리를 생성합니다.")

        # ---------------------------------------------------------
        # 2. Content Analysis (요약 및 키워드 추출)
        # ---------------------------------------------------------
        logger.info("ContentAnalyzer를 시작합니다 (요약 및 키워드 생성)...")
        summaries = self.analyzer.summarize_chunks(all_chunks, max_workers=MAX_WORKERS)
        keyword_index = self.analyzer.build_keyword_index(summaries)

        # ---------------------------------------------------------
        # 3. Scenario Generation (페르소나 및 시나리오 생성)
        # ---------------------------------------------------------
        logger.info("ScenarioGenerator를 시작합니다...")
        scenarios = self.scenario_gen.generate_scenarios(summaries)

        # ---------------------------------------------------------
        # 4. Query Generation (쿼리 생성)
        # ---------------------------------------------------------
        logger.info(f"QueryGenerator를 시작합니다 (목표 쿼리 수: {num_total_queries})...")
        # Orchestrator는 동기적으로 동작하므로 sync 래퍼 메서드 사용
        all_queries = self.query_gen.generate_all_queries_sync(
            all_chunks=all_chunks,
            summaries=summaries,
            keyword_index=keyword_index,
            scenarios=scenarios,
            num_total_queries=num_total_queries
        )

        # ---------------------------------------------------------
        # 5. Save Results (저장)
        # ---------------------------------------------------------
        logger.info(f"생성된 {len(all_queries)}개의 쿼리를 저장합니다: {OUTPUT_PATH}")
        self._save_results_to_txt(all_queries, doc_names, OUTPUT_PATH)
        
        logger.info("모든 작업이 완료되었습니다.")
        return OUTPUT_PATH

    def _save_results_to_txt(self, queries: List[Query], doc_names: List[str], output_path: str):
        """
        생성된 쿼리 리스트를 지정된 형식의 텍스트 파일로 저장합니다.
        파일 상단에 메타데이터를 포함합니다.
        """
        # 디렉토리가 없으면 생성
        output_dir = os.path.dirname(output_path)
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir)

        with open(output_path, "w", encoding="utf-8") as f:
            # --- 메타데이터 작성 ---
            f.write(f"# Generated from: {', '.join(doc_names)}\n")
            f.write(f"# Generated at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"# Total Queries: {len(queries)}\n")
            
            type_counts = Counter(q.type.value for q in queries)
            for q_type, count in sorted(type_counts.items()):
                f.write(f"#   - {q_type}: {count}\n")
            
            f.write("\n" + "="*40 + "\n\n")

            # --- 쿼리 데이터 작성 ---
            for i, q in enumerate(queries):
                f.write(f"# idx: {i+1}\n")
                f.write(f"# type: {q.type.value}\n")
                if q.reference:
                    f.write(f"# reference: {q.reference}\n")
                f.write(f"{q.query.replace('\n', ' ')}\n")
                if q.answer:
                    f.write(f"# answer: {q.answer.replace('\n', ' ')}\n")
