# ==============================================================================
# 1. 문서 요약 프롬프트
# ==============================================================================

prompt_summarize_chunks = '''
{text}
[지시 사항]
위 텍스트는 어떤 문서의 일부분이다.
텍스트를 분석하여 다음 두 가지 작업을 수행하라.

페이지 요약 (5문장 이내):
텍스트의 핵심 주장, 근거, 그리고 결론의 논리적 흐름이 명확히 드러나야 한다.
단순히 주제를 나열하는 것이 아니라, 내용이 어떻게 전개되는지 요약해야 한다.
반드시 5문장 이내로 간결하게 작성하라.

핵심 키워드 (5개):
나중에 이 문서를 검색하거나 색인(Index)하는 데 사용할 수 있는 대표적인 키워드 5개를 선정하라.
주로 명사, 고유 명사, 전문 용어 또는 핵심 개념을 위주로 선정하라.

[출력 형식]
결과는 다음 형식을 정확히 지켜서 응답하라.
요약: 요약 내용
키워드: [키워드1, 키워드2, ...]'''

prompt_summarize_summaries = '''
{text}
[지시 사항]
위 텍스트는 어떤 문서를 페이지 별로 요약한 것이다.
텍스트를 분석하여 다음 두 가지 작업을 수행하라.

페이지 요약 (10문장 이내):
텍스트의 핵심 주장, 근거, 그리고 결론의 논리적 흐름이 명확히 드러나야 한다.
단순히 주제를 나열하는 것이 아니라, 내용이 어떻게 전개되는지 요약해야 한다.
반드시 10문장 이내로 간결하게 작성하라.

핵심 키워드 (10개):
나중에 이 문서를 검색하거나 색인(Index)하는 데 사용할 수 있는 대표적인 키워드 10개를 선정하라.
주로 명사, 고유 명사, 전문 용어 또는 핵심 개념을 위주로 선정하라.

[출력 형식]
결과는 다음 형식을 정확히 지켜서 응답하라.
요약: 요약 내용
키워드: [키워드1, 키워드2, ...]
'''

prompt_match_jobs = """
문서 요약:
---
{doc_summary_text}
---

기본 직업 목록:
---
{base_job_list}
---

위 문서 요약본을 읽을 가능성이 높은 사람들의 직업 10개를 위 '기본 직업 목록' 중에서 골라주세요.
만약 목록에 적절한 직업이 없다면, 문서 내용과 관련성이 높은 직업을 새로 제안해도 좋습니다.

출력 형식: 10개의 직업을 쉼표(,)로 구분된 단일 문자열로 반환해주세요. (예: 직업1, 직업2, 직업3, ...)
"""

# ==============================================================================
# 2. 쿼리 생성 공통 템플릿
# ==============================================================================

# WR (With Reference): 정답(Gold)과 근거 포함
TEMPLATE_WR = '''
[페르소나]
{persona}

[수행 작업]
{task}

[발췌]
{context}

[지시]
당신은 RAG 시스템을 테스트하기 위한 질의응답(Q&A) 세트를 생성하는 AI입니다.
위 [페르소나]를 가진 사용자가 RAG 이용 시 할 법한 질문과 정답을 {num_queries} 개 생성하시오.

[질문 조건]
1. **[발췌] 언급 금지:** [발췌]은 질문 생성을 위한 구체적인 정보 습득, 맥락 파악을 위해서만 사용하세요. 질문자는 [발췌]에 대해 알지 못한다고 가정합니다. 질문에 "문서에 따르면", "본문에서 언급된" "이 문서" 같은 표현을 절대 사용하지 마십시오. 
2. **자연스러운 어투:** RAG 이용자가 질문 시 사용하는 어투를 사용하세요. "야", "어이" 금지
3. **명확한 정답:** 질문은 모호하지 않아야 하며, 반드시 [발췌] 내에서 명확한 근거를 찾을 수 있어야 합니다.
4. **유형 준수:** 아래 [쿼리 유형]에 맞는 질문만 생성하세요.

[쿼리 유형]
{instruction}

[출력 포맷]
반드시 아래 JSON 포맷(List of Objects)으로만 응답하세요. 다른 설명은 포함하지 마세요.
[
  {{{{
    "question": "생성된 질문",
    "answer": "질문에 대한 정답 (본문 내용을 바탕으로 요약)"
  }}}},
  ...
]
'''

# NR (No Reference): 정답 없이 질문(String)만 생성
TEMPLATE_NR = '''
[페르소나]
{persona}

[수행 작업]
{task}

[문서 내용 요약]
{context}

[지시]
당신은 RAG 시스템을 테스트하기 위한 질의응답(Q&A) 세트를 생성하는 AI입니다.
위 [페르소나]를 가진 사용자가 RAG 이용 시 할 법한 질문을 생성하시오.
위 [문서 내용 요약]을 참고하여 자연스러운 질문을 {num_queries}개 생성하세요.

[질문 조건]
1. **관련성:** 문서가 다루는 주제와 관련이 있어야 합니다.
2. **탐색적 성격:** 문서 내부에 꼭 명확한 답이 있지 않아도 됩니다. (사용자의 호기심이나 일반적인 검색 의도 반영)
3. **[문서 내용 요약] 언급 금지:** 질문자는 [문서 내용 요약] 자체에 대해선 알지 못한다고 가정합니다. 질문 생성을 위한 구체적인 정보 습득, 맥락 파악을 위해서만 사용하세요. "요약문에 따르면", "여기서 언급된", "이 문서" 같은 표현을 쓰지 마세요. 
4. **자연스러운 어투:** RAG 이용자가 질문 시 사용하는 어투를 사용하세요. "야", "어이" 금지
5. **유형 준수:** 아래 [쿼리 유형]에 맞는 질문만 생성하세요.

[쿼리 유형]
{instruction}

[출력 포맷]
반드시 아래 JSON 문자열 리스트(List of Strings) 형식으로만 응답하세요.
["질문 1", "질문 2", ...]
'''

# ==============================================================================
# 3. 쿼리 유형별 지시사항 (Instruction)
# ==============================================================================

INST_SIMPLE_SEARCH = '''
- **단순 정보 검색 (Simple Search):** 육하원칙(누가, 언제, 어디서, 무엇을, 어떻게, 왜)에 해당하는 단순 사실을 묻는 질문.
- 예: "우리 회사의 2025년 총 매출액이 얼마야?", "삼성전자의 회장이 누구야?"
'''

INST_SIMPLE_EXPLN = '''
- **설명 요구 (Explanation):** 특정 개념, 프로세스, 정책, 원인 등에 대한 상세한 설명을 요구하는 질문.
- 예: "레지스탕스의 역사에 대해 자세히 설명해줘", "감사 절차가 어떻게 진행되는지 알려줘."
'''

INST_SIMPLE_TF = '''
- **사실 확인 (True/False):** 특정 진술이 맞는지 틀린지 확인하는 질문.
- 예: "BAYC가 2022년에 시작된 프로젝트 맞지?", "우황청심환은 부작용이 전혀 없어?"
'''

INST_COMPLEX_MULTI = '''
- **복합 추론 (Multi-hop):** 첫 번째 정보를 통해 두 번째 정보를 찾아야 하는 다단계 질문.
- 예: "현 구글 CEO가 최근 AI에 대해 언급한 인터뷰 내용을 찾아줘", "이 소설의 작가가 쓴 다른 작품들은 뭐야?"
'''

INST_COMPLEX_COMP = '''
- **비교 분석 (Comparison):** 두 개 이상의 대상을 특정 기준(가격, 성능, 특징 등)으로 비교하는 질문.
- 예: "삼성전자와 SK하이닉스의 HBM 기술 차이점을 비교해줘."
'''

INST_COMPLEX_INFER = '''
- **논리적 추론 (Inference):** 텍스트에 명시되지 않았지만, 정보를 종합하여 논리적으로 유추해야 하는 질문. (원인, 영향, 의도 등)
- 예: "아편전쟁 당시 청나라의 대응이 미흡했던 근본적인 이유가 뭐라고 생각해?"
'''

INST_COMPLEX_COND = '''
- **조건부 검색 (Conditional):** 하나 이상의 제약 조건(시간, 장소, 수치 등)을 만족하는 정보를 찾는 질문.
- 예: "서울 시내 보증금 2000 이하, 월세 100 이하인 원룸만 찾아줘."
'''

# ==============================================================================
# 4. 최종 프롬프트 조립
# ==============================================================================

# With Reference (Gold O)
prompt_generate_simple_search_queries_wr = TEMPLATE_WR.format(instruction=INST_SIMPLE_SEARCH, persona='{persona}', task='{task}', context='{context}', num_queries='{num_queries}')
prompt_generate_simple_expln_queries_wr = TEMPLATE_WR.format(instruction=INST_SIMPLE_EXPLN, persona='{persona}', task='{task}', context='{context}', num_queries='{num_queries}')
prompt_generate_simple_tf_queries_wr = TEMPLATE_WR.format(instruction=INST_SIMPLE_TF, persona='{persona}', task='{task}', context='{context}', num_queries='{num_queries}')
prompt_generate_complex_multi_queries_wr = TEMPLATE_WR.format(instruction=INST_COMPLEX_MULTI, persona='{persona}', task='{task}', context='{context}', num_queries='{num_queries}')
prompt_generate_complex_comp_queries_wr = TEMPLATE_WR.format(instruction=INST_COMPLEX_COMP, persona='{persona}', task='{task}', context='{context}', num_queries='{num_queries}')
prompt_generate_complex_infer_queries_wr = TEMPLATE_WR.format(instruction=INST_COMPLEX_INFER, persona='{persona}', task='{task}', context='{context}', num_queries='{num_queries}')
prompt_generate_complex_cond_queries_wr = TEMPLATE_WR.format(instruction=INST_COMPLEX_COND, persona='{persona}', task='{task}', context='{context}', num_queries='{num_queries}')

# No Reference (Gold X)
prompt_generate_simple_search_queries_nr = TEMPLATE_NR.format(instruction=INST_SIMPLE_SEARCH, persona='{persona}', task='{task}', context='{context}', num_queries='{num_queries}')
prompt_generate_simple_expln_queries_nr = TEMPLATE_NR.format(instruction=INST_SIMPLE_EXPLN, persona='{persona}', task='{task}', context='{context}', num_queries='{num_queries}')
prompt_generate_simple_tf_queries_nr = TEMPLATE_NR.format(instruction=INST_SIMPLE_TF, persona='{persona}', task='{task}', context='{context}', num_queries='{num_queries}')
prompt_generate_complex_multi_queries_nr = TEMPLATE_NR.format(instruction=INST_COMPLEX_MULTI, persona='{persona}', task='{task}', context='{context}', num_queries='{num_queries}')
prompt_generate_complex_comp_queries_nr = TEMPLATE_NR.format(instruction=INST_COMPLEX_COMP, persona='{persona}', task='{task}', context='{context}', num_queries='{num_queries}')
prompt_generate_complex_infer_queries_nr = TEMPLATE_NR.format(instruction=INST_COMPLEX_INFER, persona='{persona}', task='{task}', context='{context}', num_queries='{num_queries}')
prompt_generate_complex_cond_queries_nr = TEMPLATE_NR.format(instruction=INST_COMPLEX_COND, persona='{persona}', task='{task}', context='{context}', num_queries='{num_queries}')