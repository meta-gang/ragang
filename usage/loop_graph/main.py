from core.bases.datas.linker import Linker
from container import RAGContainer
from usage.loop_graph.modules.impls import *
from usage.loop_graph.metrics.impls import *

rag = RAGContainer(
    u_fid='unique_flow_id',
    modules=[
        AcceptorModule('starter', metrics=None, is_starter=True),
        MyRetrievalModule('ret', linker=Linker('starter') | Linker('post'), metrics=[MyRetrievalMetric()]),
        MyPostRetrievalModule('post', linker=Linker('ret'), metrics=[MyPostRetrievalMetric(), MySecondPostRetrievalMetric()]),
        MyGenerationModule('output', linker=Linker('post'), metrics=[MyGenerationMetric(None)]),
    ],
    e2e_metrics=[MyE2EMetric()]
)

# answer = rag.invoke('Hello, Ragang')
# print(f'Answer: {answer}')
# rag.print_eval()

rag.invoke_batch([
    'Hello, Ragang',
    'Hello, Starbucks',
    'Hello, SKKU',
    'Hello, Metabuild'
])
rag.print_eval()