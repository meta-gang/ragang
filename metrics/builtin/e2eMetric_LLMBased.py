from common.bases.datas.performance_dataclass import Performance
from common.bases.abstracts.base_metric import BaseMetric
from adapters.llm_adapter import BaseLLMAdapter
from adapters.embedding_adapter import BaseEmbeddingAdapter
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np
"""
Name : End to end relevancy metric via Yes/No judgement
Target : Answer-Query Relevancy
Type : End to end, LLM-as-a-judge
Explanation : 사용자 질문과 생성된 답안을 LLM에게 주어 relevancy를 기준으로 Yes/No를 답하는 메트릭입니다.
"""
class E2ESYNRelevancyMetric(BaseMetric):
    def __init__(self, llm_adapter : BaseLLMAdapter):
        self.llm_adapter = llm_adapter

    def evaluate(self, query: str, gen: str) -> Performance:

        prompt = (   #todo : prompt needs to be refined. especially the rubric has to be specified more.
            "You are given a question and a final response.\n"
            "Your task is to judge whether the response aligns with the intention of the question.\n"

            "Judge the response using the following rubric:\n\n"
            "Y → The response is fully relevant and well-aligned with the input question, addressing all the information required from the question directly and appropriately.\n\n"
            "N → The response is totally irrelevant or does not address the input question.\n"
            "Note that whether the answer itself to be correct or not is not a matter here."
            "The only factor you consider is whether the response correctly addresses the type of required information aksed in the question."
            "Output only the judgement without explanation.\n\n"
            
            "Example 1:\n"
            "Question:\nWhat is the capital of France?\n"
            "Response:\nIt's a man-made factor of production, meaning it's created by humans rather than being a natural resource\n"
            "Judgement: N\n\n"
            
            "Example 2:\n"
            "Question:\nWhat is the capital of France?\n"
            "Response:\nParis, Lyon, and Strasbourg are the most famous cities of France.\n"
            "Judgement: N\n\n"
            
            "Example 3:\n"
            "Question:\nWhat is the capital of France?\n"
            "Response:\nThe capital of France is Paris.\n"
            "Judgement: Y\n\n"
        )
        user_query = f"Question:\n{query}\n\nResponse:\n{gen}\nJudgement: "


        response = self.llm_adapter.request(prompt, user_query)
        try:
            score = 1 if response["text"].strip().upper() == "Y" else 0
        except (KeyError, AttributeError):
            score = 0.0  # Default to 0 if the response is not in the expected format
        return Performance(score=score, unit="", metric="Yes/No Relevancy")



"""
Name : End to end relevancy metric via simple scoring
Target : Answer-Query Relevancy
Type : End to end, LLM-as-a-judge
Explanation : 사용자 질문과 생성된 답안을 LLM에게 주어 relevancy를 기준으로 0, 1, 2점 중에 채점하게 하는 간단한 메트릭입니다.
"""
class E2EScoringRelevancyMetric(BaseMetric):
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
        except (ValueError, KeyError, TypeError):
            score = 0.0  # Default to 0 if the response is not a valid number
        return Performance(score=score, unit="", metric="Simple Score Relevancy")



"""
Name : End to end relevancy metric via question generation
Target : Answer-Query Relevancy
Type : End to end, LLM generation, cosine-similarity
Explanation : 생성된 답안을 기반으로 LLM에게 예상 질문 3개를 생성하게 합니다. 생성된 예상 질문을 실제 질문과 코사인 유사도를 기준으로 비교합니다.
"""
class E2EQGenRelevancyMetric(BaseMetric):
    def __init__(self, llm_adapter: BaseLLMAdapter, embedding_adapter: BaseEmbeddingAdapter):
        self.llm_adapter = llm_adapter
        self.embedding_adapter = embedding_adapter

    def evaluate(self, query: str, gen: str) -> Performance:
        prompt = (  # todo : prompt needs to be refined.

            "You are given a final response generated by other LLM when a question is given.\n"
            "Your task is to generate the expected question that would have resulted in such a response.\n"
            "Output only the expected question without explanation.\n\n"
            
            "Example 1:\n"
            "Response:\nThe capital of France is Paris.\n"
            "Expected question:\nWhat is the capital of France?\n\n"
            
            "Example 2:\n"
            "Response:\nPhotosynthesis is the process by which green plants convert sunlight into energy.\n"
            "Expected question:\nWhat is photosynthesis?\n\n"
            
            "Example 3:\n"
            "Response:\nYes, the Great Wall of China is visible from space under certain conditions.\n"
            "Expected question:\nIs the Great Wall of China visible from space?\n\n"
        )
        user_query = f"Response:\n{gen}\nExpected question: "

        responses = []
        for _ in range(3):
            response_data = self.llm_adapter.request(prompt, user_query)
            if "text" in response_data and response_data["text"]:
                responses.append(response_data["text"].strip())

        if not responses:
            # If no questions were generated, relevancy is 0
            return Performance(score=0.0, unit="", metric="Q-Gen Relevancy")

        all_texts = [query] + responses

        try:
            # Create embeddings using the provided adapter
            embeddings = self.embedding_adapter.create_embeddings(all_texts)

            # The first vector is the original query, the rest are for the generated questions
            query_embedding = embeddings[0:1]
            generated_embeddings = embeddings[1:]

            if generated_embeddings.shape[0] == 0:
                return Performance(score=0.0, unit="", metric="Q-Gen Relevancy")

        except Exception as e:
            # Handle potential errors from the embedding adapter
            print(f"An error occurred during embedding creation: {e}")
            return Performance(score=0.0, unit="", metric="Q-Gen Relevancy")

        # Calculate cosine similarity
        similarity_scores = cosine_similarity(query_embedding, generated_embeddings)

        # The final score is the average of the similarity scores
        final_score = np.mean(similarity_scores) if similarity_scores.size > 0 else 0.0

        return Performance(score=float(final_score), unit="", metric="Q-Gen Relevancy")
    


"""
Name : End to end consistenct metric
Target : Answer-Query consistency
Type : End to end, cosine-similarity
Explanation : 생성된 답변들 간의 코사인 유사도를 측정한다. 
"""
class e2eCosineConsistencyMetric(BaseMetric):
    def __init__(self, embedding_adapter : BaseEmbeddingAdapter):
        self.embedding_adapter = embedding_adapter

    def evaluate(self, gens: list[str]) -> Performance:
        if len(gens) < 2:
            return Performance(score=1.0, unit="", metric="E2E Consistency")

        try:
            gen_vectors = self.embedding_adapter.create_embeddings(gens)
            
            similarity_matrix = cosine_similarity(gen_vectors)
            
            num_gens = len(gens)
            # Sum of the upper triangle, excluding the diagonal
            indices = np.triu_indices(num_gens, k=1)
            total_cos = np.sum(similarity_matrix[indices])
            num_pairs = len(indices[0])

            if num_pairs == 0:
                return Performance(score=1.0, unit="", metric="E2E Consistency")

            score = total_cos / num_pairs
        except Exception as e:
            print(f"An error occurred during consistency calculation: {e}")
            score = 0.0

        return Performance(score=float(score), unit="", metric="E2E Consistency")


"""
Name : End to end consistenct metric
Target : Answer-Query consistency
Type : End to end, cosine-similarity
Explanation : 입력된 쿼리와 생성된 답변들 간의 코사인 유사도의 분산을 구한다.
"""
class e2eCovarianceConsistencyMetric(BaseMetric):
    def __init__(self, embedding_adapter : BaseEmbeddingAdapter):
        self.embedding_adapter = embedding_adapter

    def evaluate(self, query : str, gens: list[str]) -> Performance:
        if not gens:
            return Performance(score=0.0, unit="", metric="E2E Query-Answer Consistency Variance")
        
        try:
            all_texts = [query] + gens
            embeddings = self.embedding_adapter.create_embeddings(all_texts)

            query_vector = embeddings[0:1]
            gen_vectors = embeddings[1:]

            if gen_vectors.shape[0] == 0:
                return Performance(score=0.0, unit="", metric="E2E Query-Answer Consistency Variance")

            cos_sims = cosine_similarity(query_vector, gen_vectors)[0]
            
            consistency_score = float(np.var(cos_sims))
        except Exception as e:
            print(f"An error occurred during consistency variance calculation: {e}")
            consistency_score = 0.0

        return Performance(score=consistency_score, unit="", metric="E2E Query-Answer Consistency Variance")