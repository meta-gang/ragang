'''
1. Extract summary and keyword from raw chunks
2. Extract summary and keyword from summaries
3. Generate persona
4. Generate scenarios
5. Generate simple queries with references
6. Generate complex queries with references
7. Generate simple queries without references
8. Generate complex queries without references
'''
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
prompt_generate_persona = ''''''
prompt_generate_scenarios = ''''''
prompt_generate_simple_queries_wr = ''''''
prompt_generate_complex_queries_wr = ''''''
prompt_generate_simple_queries_nr = ''''''
prompt_generate_complex_queries_nr = ''''''