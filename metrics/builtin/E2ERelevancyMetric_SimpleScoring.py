from common.bases.datas.performance_dataclass import Performance
from common.bases.abstracts.base_metric import BaseMetric
from adapters.llm_adapter import BaseLLMAdapter

"""
Target : Q-A Relevancy
Type : End to end, LLM-as-a-judge
Explanation : 사용자 질문과 생성된 답안을 LLM에게 주어 relevancy를 기준으로 0, 1, 2점 중에 채점하게 하는 간단한 메트릭입니다.
"""


class E2ESimpleRelevancyMetric(BaseMetric):
    def __init__(self, llm_adapter : BaseLLMAdapter):
        self.llm_adapter = llm_adapter

    def evaluate(self, query: str, gen: str) -> Performance:

        prompt = (   #todo : prompt needs to be refined. especially the rubric has to be specified more.
            "You are given a question and a final response.\n"
            "Your task is to evaluate how well the response aligns with the intention of the question.\n"
            "Score the response using the following rubric:\n\n"
            "0 → The response is irrelevant or does not address the input question.\n"
            "1 → The response partially aligns with the input question but is vague, incomplete, or misses key aspects.\n"
            "2 → The response is fully relevant and well-aligned with the input question, addressing all the information required from the question directly and appropriately.\n\n"
            "Note that whether the answer itself to be correct or not is not a matter here."
            "The only factor you consider is whether the response correctly addresses the type of required information aksed in the question."
            "Output only the score (0, 1, or 2) without explanation.\n\n"
            
            "Example 1:\n"
            "Question:\nWhat is the capital of France?\n"
            "Response:\nIt's a man-made factor of production, meaning it's created by humans rather than being a natural resource\n"
            "Score: 0\n\n"
            
            "Example 2:\n"
            "Question:\nWhat is the capital of France?\n"
            "Response:\nParis, Lyon, and Strasbourg are the most famous cities of France.\n"
            "Score: 1\n\n"
            
            "Example 3:\n"
            "Question:\nWhat is the capital of France?\n"
            "Response:\nThe capital of France is Paris.\n"
            "Score: 2\n\n"
        )
        user_query = f"Question:\n{query}\n\nResponse:\n{gen}\nScore: "


        response = self.llm_adapter.request(prompt, user_query)
        try:
            score = float(response["text"])/2
        except ValueError:
            score = 0.0  # Default to 0 if the response is not a valid number
        return Performance(score=score, unit="", metric="A2Q Relevancy")