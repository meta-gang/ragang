from core.bases.datas.linker import Linker
from container import RAGContainer
from usage.merge_graph.modules.impls import *
from usage.merge_graph.metrics.impls import *

rag = RAGContainer(
    u_fid='unique_flow_id',
    modules=[
        AcceptorModule('starter', metrics=None, is_starter=True),
        MyBranchingModule('branch', linker=Linker('starter'), metrics=None),
        MyRetrievalModule('first_ret', linker=Linker('branch'), metrics=[MyRetrievalMetric()]),
        MyRetrievalModule('second_ret', linker=Linker('branch'), metrics=[MyRetrievalMetric()]),
        MyRerankingModule('rerank', linker=Linker('first_ret') & Linker('second_ret'), metrics=[MyRerankingMetric()]),
        MyGenerationModule('output', linker=Linker('rerank'), metrics=[MyGenerationMetric(None)]),
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