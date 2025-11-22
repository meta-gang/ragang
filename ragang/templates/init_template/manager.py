"""
This file is the project's entry point.
Do not remove containers() function.
containers() should return a valid BaseContainer objects list.
"""

from ragang.container import RAGContainer
from ragang.core.bases.abstracts.base_container import BaseContainer
from ragang.core.bases.datas.linker import Linker

from metrics.impls import *
from modules.impls import *


def containers() -> list[BaseContainer]:
    return [
        RAGContainer(
            flow_id="loop_graph",
            modules=[
                AcceptorModule(
                    'starter',
                    metrics=None,
                    is_starter=True
                ),
                MyRetrievalModule(
                    'ret',
                    linker=Linker('starter') | Linker('post'),
                    metrics=[MyRetrievalMetric(['starter.query'])]
                ),
                MyPostRetrievalModule(
                    'post',
                    linker=Linker('ret'),
                    metrics=[MyPostRetrievalMetric(['starter.query']),
                             MySecondPostRetrievalMetric(['starter.query'])]
                ),
                MyGenerationModule(
                    'output',
                    linker=Linker('post'),
                    metrics=[MyGenerationMetric(['starter.query'], None)]
                ),
            ],
            e2e_metrics=[MyE2EMetric([])]
        )
    ]
