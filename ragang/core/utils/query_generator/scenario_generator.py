import asyncio
import random
import logging
from typing import List, Tuple

# LLM 어댑터 및 모델 임포트
from ragang.adapters.llm_adapter import BaseLLMAdapter
from ragang.core.utils.query_generator.models import DocSummary, Explanation, Scenario
from ragang.core.utils.query_generator.prompts import prompt_match_jobs

NUM_OF_SCENARIOS_PER_DOC = 5

logger = logging.getLogger(__name__)


# --- 프롬프트 정의 ---


class ScenarioGenerator:
    """
    🎭 ScenarioGenerator 클래스
    역할 (Responsibility): 분석된 문서 요약(DocSummary)을 바탕으로 쿼리 생성의 맥락이 될 페르소나와 시나리오를 생성합니다.
    """

    # --- 1. 데이터 목록 (이전과 동일) ---
    NAME_GENDER_LIST: List[Tuple[str, str]] = [
        ("김철수", "남성"), ("이영희", "여성"), ("박준호", "남성"),
        ("최지우", "여성"), ("정재훈", "남성"), ("윤숙희", "여성"),
        ("강시원", "남성"), ("송정아", "여성"), ("한도윤", "남성"),
        ("임지윤", "여성")
    ]
    AGE_LIST: List[str] = ["10대", "20대", "30대", "40대", "50대", "60대 이상"]
    PERSONALITY_TRAITS: List[str] = [
        "잘 적응하는", "모험심이 강한", "다정한", "경계심이 강한", "야심만만한",
        "분석적인", "고마워할 줄 아는", "대범한", "침착한", "조심성이 많은",
        "중심이 잡힌", "매력적인", "자신감 있는", "협조적인", "용기 있는",
        "예의 바른", "창조적인", "호기심이 많은", "결단력 있는", "협상에 능한",
        "절제력이 있는", "신중한", "느긋한", "효율적인", "공감을 잘하는",
        "열정적인", "외향적인", "대담한", "몰입하는",
        "우호적인", "재미있는", "관대한", "온화한", "행복해하는",
        "정직한", "명예를 중시하는", "환대하는", "겸손한", "이상주의적인",
        "상상력이 풍부한", "독립적인", "부지런한", "순수한", "영감을 주는",
        "지적인", "내성적인", "정의로운", "친절한", "충직한",
        "어른스러운", "자비로운", "꼼꼼한", "자연주의적인", "잘 보살피는",
        "순종적인", "객관적인", "관찰력이 뛰어난", "낙천적인", "조직적인",
        "참을성이 많은", "애국적인", "사색적인", "통찰력 있는",
        "끈기 있는", "설득력 있는", "철학적인", "놀기 좋아하는", "개인적인",
        "주도적인", "전문적인", "정확한", "보호본능이 강한",
        "지략이 풍부한", "책임감 있는", "양식 있는", "관능적인", "감성이 풍부한",
        "소박한", "사회적 인식이 높은", "교양 있는", "영적인", "즉흥적인",
        "혈기가 왕성한", "학구적인", "조력적인", "재능 있는", "알뜰한",
        "관용적인", "보수적인", "잘 믿는", "자유분방한", "사심이 없는",
        "기발한", "건전한", "현명한", "재치 있는", "일중독인",
        "아니꼬운", "무관심한", "냉담함", "완벽주의인",
        "심술궂음", "어린아이 같은", "거만한", "대립을 일삼는",
        "비겁한", "냉소적인", "방어적인", "비이성적인"
                               "기만적인", "정직하지 못한", "불충한", "체계적이지 못한",
        "낭비벽이 있는", "엉뚱한",
        "어리석은", "잘 잊어버리는", "경박함", "깐깐한",
        "탐욕스러운", "퉁명스러운", "잘 속는", "오만한", "적대적인",
        "재미없는", "위선적인", "무식한", "충동적인",
        "부주의한", "우유부단한", "융통성이 없는",
        "무책임한", "질투심이 강한", "비판적인", "뭐든 아는 체하는",
        "게으른", "조종하는", "물질만능주의인",
        "감정과잉인", "짓궂은", "잔소리가 심한",
        "오지랖이 넓은", "집착이 강한", "비관적인", "소유욕이 강한", "편파적인", "허세를 부리는",
        "강압적인", "반항적인", "원망하는",
        "말썽을 피우는", "산만한", "방종하는", "이기적인",
        "추잡함", "응석을 부리는", "인색한", "고집불통인", "비굴한",
        "미신을 믿는", "의심이 많은", "눈치 없는", "변덕스러운", "소심한",
        "지나치게 말수가 적은", "비협조적인", "상스러운", "비윤리적인", "고마워할 줄 모르는",
        "우둔한", "허영심이 강한",
        "다혈질인", "의지박약인", "불평이 많은", "움츠러드는",
        "사서 걱정하는"
    ]
    BASE_JOB_LIST: List[str] = [
        "방산연구원", "소방관", "간호사", "대학생", "고등학생", "가정주부",
        "소프트웨어 개발자", "기획자", "마케터", "데이터 분석가", "교사",
        "공무원", "변호사", "의사", "회계사", "금융 전문가", "CEO",
        "자영업자", "프리랜서", "예술가", "디자이너", "기자", "PD",
        "건설 노동자", "요리사", "농부", "군인", "경찰관", "운동선수",
        "약사", "수의사", "건축가", "승무원", "미용사",
        "작가", "운전기사", "교수", "사회복지사", "영양사",
        "심리상담사", "크리에이터", "통번역가", "사서", "큐레이터",
        "노무사", "관세사", "비행기 조종사", "모델", "전기 기술자"
    ]
    DOMAIN_KNOWLEDGE_LIST: List[str] = [
        "아는 것이 전무한 단계", "입문", "초급", "중급", "고급", "전문가 수준"
    ]
    TONE_POLITENESS: List[str] = ["존댓말", "반말"]
    TONE_STYLE: List[str] = ["키워드 위주", "온전한 문장 구사"]
    KEY_TASK_LIST: List[str] = [
        "특정 주제에 대한 개요를 빠르게 파악하기",
        "내 주장을 뒷받침할 정확한 인용구나 데이터 찾기",
        "새로운 아이디어 얻기",
        "특정 개념에 대한 구체적이고 상세한 설명 듣기",
        "개인적인 호기심 해결하기",
        "보고서 작성을 위한 자료조사",
        "논쟁적인 주장에 대한 팩트체크"
    ]

    # --- 2. 클래스 초기화 ---
    def __init__(self, llm_adapter: BaseLLMAdapter):
        self.llm_adapter = llm_adapter

    # --- 3. Private Methods (Async) ---

    async def _call_llm_single(self, prompt: str) -> dict:
        """ [비동기] 단일 프롬프트를 비동기적으로 전송하고 결과를 반환합니다. """
        try:
            results = await self.llm_adapter.request_async_batch([prompt], [""], max_workers=1)
            if not results:
                raise ValueError("LLM 어댑터가 빈 결과를 반환했습니다.")

            result = results[0]
            if isinstance(result, Exception):
                raise result
            return result

        except Exception as e:
            logger.error(f"단일 LLM 호출 중 예외 발생: {e}")
            return {"text": ""}

    def _parse_job_list_from_response(self, response_text: str, doc_index: int) -> List[str]:
        """ [동기] LLM 응답 텍스트를 파싱하여 직업 리스트를 반환합니다. """
        relevant_jobs = []
        if response_text:
            relevant_jobs = [job.strip() for job in response_text.split(',') if job.strip()]

            if len(relevant_jobs) > 10:
                relevant_jobs = relevant_jobs[:10]
            elif 0 < len(relevant_jobs) < 10:
                needed = 10 - len(relevant_jobs)
                base_jobs_filtered = [j for j in self.BASE_JOB_LIST if j not in relevant_jobs]

                if len(base_jobs_filtered) >= needed:
                    relevant_jobs.extend(random.sample(base_jobs_filtered, needed))
                else:
                    relevant_jobs.extend(base_jobs_filtered)

        if not relevant_jobs:
            logger.warning(f"LLM으로부터 관련 직업을 받지 못했습니다. (Doc: {doc_index}) 기본 직업 목록에서 10개를 랜덤 샘플링합니다.")
            relevant_jobs = random.sample(self.BASE_JOB_LIST, 10)

        return relevant_jobs

    async def _get_job_list_for_doc_async(self, doc_explanation: Explanation) -> List[str]:
        """ [비동기] (gather의 대상) 단일 문서를 받아 LLM을 호출하고 파싱된 직업 리스트를 반환합니다. """

        base_job_list_str = ", ".join(self.BASE_JOB_LIST)
        prompt = prompt_match_jobs.format(
            doc_summary_text=doc_explanation.explanation,
            base_job_list=base_job_list_str
        )

        llm_response = await self._call_llm_single(prompt)
        response_text = llm_response.get("text", "").strip()

        return self._parse_job_list_from_response(response_text, doc_explanation.index)

    async def _get_all_job_lists_async(self, doc_explanations: List[Explanation]) -> List[List[str]]:
        """ [비동기] 모든 문서의 요약본을 받아, 병렬로 LLM을 호출하고 모든 직업 리스트를 반환합니다. """

        # 병렬로 실행할 작업(LLM 호출) 목록 생성
        tasks = [
            self._get_job_list_for_doc_async(exp)
            for exp in doc_explanations
        ]

        # asyncio.gather를 통해 모든 작업을 동시에 실행하고 결과를 순서대로 받음
        all_job_lists = await asyncio.gather(*tasks, return_exceptions=True)

        # 예외 처리: 만약 특정 작업이 실패했다면, 해당 문서는 기본 직업 목록으로 대체
        final_job_lists = []
        for i, result in enumerate(all_job_lists):
            if isinstance(result, Exception):
                logger.error(f"Doc {doc_explanations[i].index}의 직업 생성 중 예외 발생: {result}. 기본 목록으로 대체합니다.")
                final_job_lists.append(random.sample(self.BASE_JOB_LIST, 10))
            else:
                final_job_lists.append(result)

        return final_job_lists

    # --- 4. Private Methods (Sync) ---

    def _generate_scenarios_for_doc_sync(self, doc_index: int, relevant_jobs: List[str]) -> List[Scenario]:
        """
        [동기] 미리 받아온 직업 리스트를 바탕으로 한 문서에 대한 3개의 페르소나와 시나리오를 생성합니다.
        (이 함수는 LLM 호출을 하지 않습니다.)
        """
        generated_scenarios_for_doc: List[Scenario] = []

        if not relevant_jobs:  # 비어있는 리스트가 넘어온 경우에 대한 방어
            logger.warning(f"Doc {doc_index}에 대한 직업 목록이 비어있습니다. 기본 목록을 사용합니다.")
            relevant_jobs = random.sample(self.BASE_JOB_LIST, 10)

        for _ in range(NUM_OF_SCENARIOS_PER_DOC):
            name, gender = random.choice(self.NAME_GENDER_LIST)
            age = random.choice(self.AGE_LIST)
            job = random.choice(relevant_jobs)  # 미리 받아온 리스트에서 선택

            pers_traits = random.sample(self.PERSONALITY_TRAITS, min(3, len(self.PERSONALITY_TRAITS)))
            knowledge = random.choice(self.DOMAIN_KNOWLEDGE_LIST)
            polite = random.choice(self.TONE_POLITENESS)
            style = random.choice(self.TONE_STYLE)

            persona_str = (
                f"이름: {name}, 성별: {gender}, 연령: {age}, 직업: {job}, "
                f"성격: {pers_traits}, 도메인지식: {knowledge}, 말투: [{polite}, {style}]"
            )

            task = random.choice(self.KEY_TASK_LIST)

            generated_scenarios_for_doc.append(
                Scenario(persona=persona_str, scenarios=[task])
            )

        return generated_scenarios_for_doc

    # --- 5. Public Method ---

    def generate_scenarios(self, summaries: List[DocSummary]) -> List[Scenario]:
        """
        [동기] (Public) 전체 문서 요약 리스트를 받아, 각 문서에 대한 페르소나와 
        구체적인 시나리오를 생성합니다.
        
        동작:
        1. (Async) 모든 문서의 직업 리스트를 LLM으로 병렬 조회합니다.
        2. (Sync) 조회된 직업 리스트를 바탕으로 페르소나와 시나리오를 동기적으로 조합합니다.
        """
        if not summaries:
            logger.warning("입력된 요약 리스트(summaries)가 비어있습니다.")
            return []

        doc_explanations = [s.docExplanation for s in summaries]
        if not doc_explanations:
            return []

        # 1. (Async) 모든 직업 리스트를 병렬로 가져옴
        try:
            all_job_lists = asyncio.run(self._get_all_job_lists_async(doc_explanations))
        except Exception as e:
            logger.error(f"시나리오 생성 비동기 작업(asyncio.run) 실행 중 최상위 오류 발생: {e}")
            return []

        # 2. (Sync) 가져온 리스트를 바탕으로 페르소나 동기적 조합
        output_scenarios: List[Scenario] = []
        for i, doc_summary in enumerate(summaries):
            doc_index = doc_summary.docExplanation.index
            jobs_for_this_doc = all_job_lists[i]

            scenarios_for_this_doc = self._generate_scenarios_for_doc_sync(
                doc_index,
                jobs_for_this_doc
            )

            output_scenarios.extend(scenarios_for_this_doc)

        return output_scenarios
