import fitz  # PyMuPDF
import os
import logging
from pathlib import Path
from collections import defaultdict
from typing import List, Dict, Tuple, Optional
import concurrent.futures
from core.utils.query_generator.models import Chunk

def _worker_pdfReader(doc_path: Path) -> List[str]:
    """
    [워커] 단일 PDF 파일의 경로(Path 객체)를 받아, 페이지별 텍스트 리스트를 반환합니다.
    (Process-safe하게 만들기 위해 클래스 밖으로 분리)
    """
    logger = logging.getLogger("_worker_pdfReader")
    pages_text: List[str] = []
    try:
        document = fitz.open(doc_path)
        for page in document:
            pages_text.append(page.get_text())
        document.close()
    except Exception as e:
        logger.error(f"PDF 파일을 읽는 중 오류 발생 ({doc_path.name}): {e}")
    return pages_text

def _worker_process_document(doc_info: Tuple[int, Path], 
                             size: int, 
                             overlap: int
                             ) -> Optional[Tuple[int, List[Chunk], Dict]]:
    
    logger = logging.getLogger(f"_worker_doc_{doc_info[0]}")
    doc_idx, doc_path = doc_info
    doc_name = doc_path.name
    logger.info(f"  -> [PID: {os.getpid()}] 처리 시작: '{doc_name}' (Doc_ID: {doc_idx})")

    try:
        pages = _worker_pdfReader(doc_path)
        if not pages:
            logger.warning(f"'{doc_name}'에서 텍스트를 추출하지 못했습니다. 건너뜁니다.")
            return None

        doc_chunks: List[Chunk] = []
        
        doc_lookup_part: Dict[int, Dict[int, Dict[int, Chunk]]] = {}
        
        step = size - overlap

        for page_idx, page_text in enumerate(pages):
            
            doc_lookup_part[page_idx] = {}
            
            paragraphs = [p for p in page_text.split('. \n') if p.strip()]
            
            for para_idx, para_text in enumerate(paragraphs):
                
                doc_lookup_part[page_idx][para_idx] = {}
                
                sentences = [s.strip() for s in para_text.split('. ') if s.strip()]

                # 문장 분리 결과가 없으면, 문단 전체를 하나의 문장으로 취급
                if not sentences:
                    if para_text.strip(): # 문단에 내용이 있을 경우에만
                        sentences = [para_text.strip()]
                    else: # 내용 없는 문단이면 건너뜀
                        continue

                if not sentences:
                    continue
                    
                for i in range(0, len(sentences), step):
                    sentence_idx = i
                    chunk_sentences = sentences[i : i + size]
                    chunk_text = ". ".join(chunk_sentences)

                    chunk = Chunk(
                        chunk_idx=-1, 
                        doc_idx=doc_idx,
                        page_idx=page_idx,
                        para_idx=para_idx,
                        sentence_idx=sentence_idx,
                        text=chunk_text
                    )
                    doc_chunks.append(chunk)
                    
                    doc_lookup_part[page_idx][para_idx][sentence_idx] = chunk

        logger.info(f"  <- [PID: {os.getpid()}] 처리 완료: '{doc_name}' (청크 {len(doc_chunks)}개 생성)")
        return (doc_idx, doc_chunks, doc_lookup_part)

    except Exception as e:
        logger.error(f"'{doc_name}' (Doc_ID: {doc_idx}) 처리 중 심각한 오류 발생: {e}")
        return None

# -------------------------------------------------
# 2. DocumentProcessor 클래스
# -------------------------------------------------
class DocumentProcessor:
    """
    파일 시스템에서 원시 PDF 문서를 읽어,
    프로그램이 사용할 수 있는 list[Chunk]와 lookup_index로 변환(전처리)합니다.
    """

    def __init__(self):
        """
        DocumentProcessor를 초기화하고 로거를 설정합니다.
        """
        self.logger = logging.getLogger(self.__class__.__name__)
        if not self.logger.hasHandlers():
            logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

        self.logger.info("DocumentProcessor가 초기화되었습니다.")


    # -------------------------------------------------
    # 2. Public Method
    # -------------------------------------------------
    def chunker(self, text_addr: str, size: int, overlap: int, max_workers: Optional[int] = None) -> Tuple[List[Chunk], Dict]:
        """
        설명: 문서들이 있는 디렉토리 주소를 받아, 모든 문서를 청크 단위로 나눕니다.
              (pathlib 및 ProcessPoolExecutor 병렬 처리 적용됨)
        """
        
        if overlap >= size:
            raise ValueError(f"overlap({overlap})은 size({size})보다 작아야 합니다.")

        all_chunks: List[Chunk] = []
        lookup_index = defaultdict(lambda: defaultdict(lambda: defaultdict(dict)))
        global_chunk_idx: int = 0
        
        if max_workers is None:
            max_workers = os.cpu_count() or 4 

        try:
            dir_path = Path(text_addr)
            if not dir_path.is_dir():
                self.logger.error(f"디렉토리를 찾을 수 없습니다 -> {text_addr}")
                return [], {}
            
            pdf_files = sorted(list(dir_path.glob('*.[pP][dD][fF]')))
            
            if not pdf_files:
                self.logger.warning(f"'{text_addr}' 디렉토리에 PDF 파일이 없습니다.")
                return [], {}
                
        except Exception as e:
            self.logger.error(f"파일 목록을 가져오는 중 오류 발생: {e}")
            return [], {}
        
        self.logger.info(f"총 {len(pdf_files)}개의 PDF 파일을 병렬 처리합니다 (Max Workers: {max_workers})...")

        tasks = list(enumerate(pdf_files)) # [(0, Path(...)), (1, Path(...)), ...]
        results = [] 

        with concurrent.futures.ProcessPoolExecutor(max_workers=max_workers) as executor:
            
            futures = {executor.submit(_worker_process_document, task, size, overlap): task for task in tasks}
            
            for future in concurrent.futures.as_completed(futures):
                try:
                    result = future.result()
                    if result:
                        results.append(result)
                except Exception as e:
                    doc_info = futures[future]
                    self.logger.error(f"'{doc_info[1].name}' (Doc_ID: {doc_info[0]})를 처리하는 프로세스에서 예외 발생: {e}")

        results.sort(key=lambda x: x[0]) # doc_idx 기준 정렬

        self.logger.info("모든 프로세스 작업 완료. 결과 취합 중...")

        for (doc_idx, doc_chunks, doc_lookup_part) in results:
            lookup_index[doc_idx] = doc_lookup_part
            
            for chunk in doc_chunks:
                chunk.chunk_idx = global_chunk_idx
                all_chunks.append(chunk)
                global_chunk_idx += 1

        self.logger.info(f"처리 완료. 총 {global_chunk_idx}개의 청크를 생성했습니다.")
        
        return all_chunks, dict(lookup_index)