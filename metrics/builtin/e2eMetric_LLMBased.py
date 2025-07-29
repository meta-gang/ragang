from common.bases.datas.performance_dataclass import Performance
from common.bases.abstracts.base_metric import BaseMetric
from adapters.llm_adapter import BaseLLMAdapter
from adapters.embedding_adapter import BaseEmbeddingAdapter
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np

class E2ESYNRelevancyMetric(BaseMetric):
    """
    End to end relevancy metric via Yes/No judgement.

    :param llm_adapter: The LLM model to use
    :type llm_adapter: BaseLLMAdapter
    :ivar llm_adapter: Stores the LLM model to use
    :vartype llm_adapter: BaseLLMAdapter
    """
    def __init__(self, llm_adapter : BaseLLMAdapter):
        self.llm_adapter = llm_adapter

    def evaluate(self, query: str, gen: str) -> Performance:
        """
        Judges the relevancy of the generated answer to the query using a Yes/No response from an LLM.

        :param query: The input query string.
        :type query: str
        :param gen: The generated answer string.
        :type gen: str
        :returns: A Performance object with a score of 1 for "Yes" and 0 for "No".
        :rtype: Performance
        """
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



class E2EScoringRelevancyMetric(BaseMetric):
    """
    End to end relevancy metric via simple scoring.

    :param llm_adapter: The LLM model to use
    :type llm_adapter: BaseLLMAdapter
    :ivar llm_adapter: Stores the LLM model to use
    :vartype llm_adapter: BaseLLMAdapter
    """
    def __init__(self, llm_adapter : BaseLLMAdapter):
        self.llm_adapter = llm_adapter

    def evaluate(self, query: str, gen: str) -> Performance:
        """
        Scores the relevancy of the generated answer to the query on a scale of 0, 1, or 2.

        :param query: The input query string.
        :type query: str
        :param gen: The generated answer string.
        :type gen: str
        :returns: A Performance object with the relevancy score.
        :rtype: Performance
        """
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



class E2EQGenRelevancyMetric(BaseMetric):
    """
    End to end relevancy metric via question generation.

    :param llm_adapter: The LLM model to use for generating questions.
    :type llm_adapter: BaseLLMAdapter
    :ivar llm_adapter: Stores the LLM model.
    :vartype llm_adapter: BaseLLMAdapter
    :param embedding_adapter: The embedding model to use for calculating similarity.
    :type embedding_adapter: BaseEmbeddingAdapter
    :ivar embedding_adapter: Stores the embedding model.
    :vartype embedding_adapter: BaseEmbeddingAdapter
    """
    def __init__(self, llm_adapter: BaseLLMAdapter, embedding_adapter: BaseEmbeddingAdapter):
        self.llm_adapter = llm_adapter
        self.embedding_adapter = embedding_adapter

    def evaluate(self, query: str, gen: str) -> Performance:
        """
        Calculates relevancy by generating questions from the answer and measuring their similarity to the original query.

        :param query: The input query string.
        :type query: str
        :param gen: The generated answer string.
        :type gen: str
        :returns: A Performance object with the mean cosine similarity score.
        :rtype: Performance
        """
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
    




