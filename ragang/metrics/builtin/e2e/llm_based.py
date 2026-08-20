from ragang.core.bases.datas.performance import Performance
from ragang.core.bases.abstracts.base_metric import BaseMetric
from ragang.adapters.llm_adapter import BaseLLMAdapter
from ragang.adapters.embedding_adapter import BaseEmbeddingAdapter
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np
import logging

logger = logging.getLogger(__name__)


class BaseBuiltinMetric(BaseMetric):
    def __init__(self, param_src: list[str], llm_adapter: BaseLLMAdapter = None, embedding_adapter: BaseEmbeddingAdapter = None):
        super().__init__(param_src)
        self.llm_adapter = llm_adapter
        self.embedding_adapter = embedding_adapter


class E2ESYNRelevancyMetric(BaseBuiltinMetric):
    """
    End to end relevancy metric via Yes/No judgement.

    :param llm_adapter: The LLM model to use
    :type llm_adapter: BaseLLMAdapter
    :ivar llm_adapter: Stores the LLM model to use
    :vartype llm_adapter: BaseLLMAdapter
    """

    def evaluate(self, query: str = None, gen: str = None) -> Performance:
        """
        Judges the relevancy of the generated answer to the query using a Yes/No response from an LLM.

        :param query: The input query string.
        :type query: str
        :param gen: The generated answer string.
        :type gen: str
        :returns: A Performance object with a score of 1 for "Yes" and 0 for "No", or np.nan on failure.
        :rtype: Performance
        """
        prompt = (
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

        try:
            response = self.llm_adapter.request(prompt, user_query)
            if "error" in response or not response.get("text"):
                return Performance(unit="binary", metric="Yes/No Relevancy", _eval=False)
            response_text = response["text"].strip().upper()
            if response_text == "Y":
                score = 1.0
            elif response_text == "N":
                score = 0.0
            else:
                logger.warning("LLM returned a value outside the Yes/No relevancy schema.")
                return Performance(unit="binary", metric="Yes/No Relevancy", _eval=False)
        except (KeyError, AttributeError):
            logger.error("Failed to parse the Yes/No relevancy response schema.")
            return Performance(unit="binary", metric="Yes/No Relevancy", _eval=False)
        return Performance(score=score, unit="binary", metric="Yes/No Relevancy")


class E2EScoringRelevancyMetric(BaseBuiltinMetric):
    """
    End to end relevancy metric via simple scoring.

    :param llm_adapter: The LLM model to use
    :type llm_adapter: BaseLLMAdapter
    :ivar llm_adapter: Stores the LLM model to use
    :vartype llm_adapter: BaseLLMAdapter
    """

    def evaluate(self, query: str = None, gen: str = None) -> Performance:
        """
        Scores the relevancy of the generated answer to the query on a scale of 0, 1, or 2.

        :param query: The input query string.
        :type query: str
        :param gen: The generated answer string.
        :type gen: str
        :returns: A Performance object with the relevancy score, or np.nan on failure.
        :rtype: Performance
        """
        prompt = (
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

        try:
            response = self.llm_adapter.request(prompt, user_query)
            if "error" in response or not response.get("text"):
                return Performance(unit="0 to 1", metric="Simple Score Relevancy", _eval=False)
            raw_score = float(response["text"])
            if raw_score not in {0.0, 1.0, 2.0}:
                return Performance(unit="0 to 1", metric="Simple Score Relevancy", _eval=False)
            score = raw_score / 2.0
        except (ValueError, KeyError, TypeError):
            logger.warning("Failed to parse the simple relevancy score schema.")
            return Performance(unit="0 to 1", metric="Simple Score Relevancy", _eval=False)
        return Performance(score=score, unit="0 to 1", metric="Simple Score Relevancy")


class E2EQGenRelevancyMetric(BaseBuiltinMetric):
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

    def evaluate(self, query: str = None, gen: str = None) -> Performance:
        """
        Calculates relevancy by generating questions from the answer and measuring their similarity to the original query.

        :param query: The input query string.
        :type query: str
        :param gen: The generated answer string.
        :type gen: str
        :returns: A Performance object with the mean cosine similarity score, or np.nan on failure.
        :rtype: Performance
        """
        prompt = (
            "You are given a final response generated by another LLM when a question is given.\n"
            "Your task is to generate three expected questions that would have resulted in such a response.\n"
            "Output only the expected questions, each on a new line, without any numbering or explanation.\n\n"

            "Example 1:\n"
            "Response:\nThe capital of France is Paris.\n"
            "Expected questions:\nWhat is the capital of France?\nWhat is France's capital city?\nWhich city is the capital of France?\n\n"

            "Example 2:\n"
            "Response:\nPhotosynthesis is the process by which green plants convert sunlight into energy.\n"
            "Expected questions:\nWhat is photosynthesis?\nHow do green plants get energy?\nDescribe the process of photosynthesis.\n\n"

        )
        user_query = f"Response:\n{gen}\nExpected questions:"

        try:
            response_data = self.llm_adapter.request(prompt, user_query)
            if "error" in response_data or not response_data.get("text"):
                return Performance(unit="-1 to 1", metric="Q-Gen Relevancy", _eval=False)
            responses = [line.strip() for line in response_data["text"].splitlines() if line.strip()]
            if not responses:
                logger.warning("LLM failed to generate any questions.")
                return Performance(unit="-1 to 1", metric="Q-Gen Relevancy", _eval=False)
        except (KeyError, AttributeError) as e:
            logger.error(f"Failed to parse LLM response for question generation: {e}")
            return Performance(unit="-1 to 1", metric="Q-Gen Relevancy", _eval=False)

        all_texts = [query] + responses

        try:
            embeddings = self.embedding_adapter.create_embeddings(all_texts)
            query_embedding = embeddings[0:1]
            generated_embeddings = embeddings[1:]

            if len(embeddings) != len(all_texts) or generated_embeddings.shape[0] == 0:
                return Performance(unit="-1 to 1", metric="Q-Gen Relevancy", _eval=False)

        except Exception as e:
            logger.error(f"An error occurred during embedding creation: {e}")
            return Performance(unit="-1 to 1", metric="Q-Gen Relevancy", _eval=False)

        similarity_scores = cosine_similarity(query_embedding, generated_embeddings)
        final_score = np.mean(similarity_scores) if similarity_scores.size > 0 else 0.0

        return Performance(score=float(final_score), unit="-1 to 1", metric="Q-Gen Relevancy")
