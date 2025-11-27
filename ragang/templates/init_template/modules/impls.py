from ragang.modules import *
from ragang.adapters.llm_adapter import BaseLLMAdapter
from ragang.core.bases.abstracts.base_metric import BaseMetric
from ragang.core.bases.datas.linker import Linker
from ragang.modules.custom import CustomModule


class AcceptorModule(CustomModule):
    async def execute(self, query: str):
        return {
            'query': query
        }


class MyRetrievalModule(RetrievalModule):
    def __init__(self, module_id, linker, embedding_adapter, vec_db_adapter, metrics=None):
        super().__init__(module_id, linker, metrics, False)
        self.embedding_adapter = embedding_adapter
        self.milvus_adapter = vec_db_adapter

    async def execute(self, query: str):
        query_vector = self.embedding_adapter.create_embeddings([query])
        retrieval_raw = self.milvus_adapter.retrieve('test', query_vector, top_k=3)
        retrieval = [ret for sublist in retrieval_raw for ret in sublist]

        return {
            'query': query,
            'ret_docs': retrieval
        }


class MyGenerationModule(GenerationModule):
    def __init__(self, module_id: str, linker: Linker = None, metrics: BaseMetric = None, is_starter: bool = False,
                 llm_adapter: BaseLLMAdapter = None):
        super().__init__(module_id, linker, metrics, is_starter)
        self.llm_adapter = llm_adapter

    async def execute(self, query: str, ret_docs: list[str]):
        ret_docs = "\n".join(f'{i + 1}. {doc}' for i, doc in enumerate(ret_docs))
        prompt = ("""
            You are a highly knowledgeable and reliable assistant that answers questions using only the information provided in the context below.

            Your task is to read the given context documents carefully and generate a helpful, accurate, and well-structured answer to the user's question.  
            Do not include information that is not explicitly supported by the context. If the context does not contain sufficient information to answer the question, respond with "I don’t know" or clearly indicate that the answer is not found in the provided context.

            Guidelines:
            - Base your answer strictly on the provided context.
            - Do not make up facts or speculate.
            - If multiple relevant pieces of evidence exist, synthesize them into a clear and coherent answer.
            - If the context contains conflicting information, acknowledge it and explain carefully.
            - You may cite parts of the context explicitly if helpful for clarity.

            <example>
            question: 사과는 무슨 색인가?
            related documents:
            1. 사과는 빨간색이다.
            2. 바나나는 노란색이다.
            3. 포도는 보라색이다.

            ---

            answer: 사과는 빨간색이다.
            <end of example>

            """
                  )
        input_query = (
            f"question: {query}\n" \
            f"related documents:\n{ret_docs}\n\n" \
            "---\n" \
            "answer: "
        )
        answer = self.llm_adapter.request(prompt=prompt, query=input_query)['text']
        return {
            'gen': answer,
        }
