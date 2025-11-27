"""
This file is the project's entry point.
Do not remove containers() function.
containers() should return a valid BaseContainer objects list.
"""

from ragang.container import RAGContainer
from ragang.core.bases.abstracts.base_container import BaseContainer
from ragang.metrics.builtin.retriever.non_llm_based import GeneralizedEmbeddingCoverageError
from ragang.metrics.builtin.generator.non_llm_based import AnswerContextSimilarity
from ragang.metrics.builtin.e2e.non_llm_based import AnswerQuerySimilarity

from modules.impls import *
from config.load_adapters import load
from settings import API_KEY


def containers() -> list[BaseContainer]:
    adapters: dict = load(API_KEY)

    db_adapter = adapters['vec']
    emb_adapter = adapters['emb']
    llm_adapter = adapters['llm']

    return [
        RAGContainer(
            flow_id="sample_rag",
            modules=[
                AcceptorModule(
                    'starter',
                    metrics=None,
                    is_starter=True
                ),
                MyRetrievalModule(
                    'ret',
                    linker=Linker('starter'),
                    metrics=[GeneralizedEmbeddingCoverageError(param_src=['starter.query', 'ret.ret_docs'],
                                                               embedding_adapter=emb_adapter,
                                                               llm_adapter=llm_adapter)],
                    embedding_adapter=emb_adapter,
                    vec_db_adapter=db_adapter,
                ),
                MyGenerationModule(
                    'output',
                    linker=Linker('ret'),
                    metrics=[AnswerContextSimilarity(param_src=['ret.ret_docs', 'output.gen'],
                                                   embedding_adapter=emb_adapter,
                                                   llm_adapter=llm_adapter)],
                    llm_adapter=llm_adapter
                ),
            ],
            e2e_metrics=[AnswerQuerySimilarity(param_src=['starter.query', 'output.gen'],
                                               embedding_adapter=emb_adapter,
                                               llm_adapter=llm_adapter)]
        )
    ]
