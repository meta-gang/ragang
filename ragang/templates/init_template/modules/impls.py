import asyncio

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
        query_vector = await asyncio.to_thread(self.embedding_adapter.create_embeddings, [query])
        if query_vector.size == 0:
            raise RuntimeError("Embedding request failed. Check the local embedding model and endpoint.")
        retrieval_raw = await asyncio.to_thread(self.milvus_adapter.retrieve, 'test', query_vector, top_k=3)
        if retrieval_raw is None:
            raise RuntimeError("Vector DB retrieval failed. Check that Milvus is running "
                               "(config/docker-compose.yml) and the collection exists.")
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
        if not ret_docs:
            return {'gen': '검색된 근거가 없어 답변할 수 없습니다.'}
        if self.llm_adapter is None:
            return {'gen': f'오프라인 연결 확인용 문서 발췌: {ret_docs[0][:400]}'}
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
        response = await asyncio.to_thread(self.llm_adapter.request, prompt=prompt, query=input_query)
        if 'error' in response:
            raise RuntimeError(f"LLM request failed: {response['error']}")
        if not isinstance(response.get('text'), str) or not response['text'].strip():
            raise RuntimeError('The local model returned an empty answer')
        return {
            'gen': response['text'],
        }
