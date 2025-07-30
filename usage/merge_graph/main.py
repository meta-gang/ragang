from common.bases.datas.linker import Linker
from container import RAGContainer
from usage.merge_graph.modules.impls import *
from usage.merge_graph.metrics.impls import *

rag = RAGContainer(
    u_fid='unique_flow_id',
    modules=[
        AcceptorModule('starter', metric=None, is_starter=True),
        MyBranchingModule('branch', linker=Linker('starter'), metric=None),
        MyRetrievalModule('first_ret', linker=Linker('branch'), metric=MyRetrievalMetric()),
        MyRetrievalModule('second_ret', linker=Linker('branch'), metric=MyRetrievalMetric()),
        MyRerankingModule('rerank', linker=Linker('first_ret') & Linker('second_ret'), metric=MyRerankingMetric()),
        MyGenerationModule('gen', linker=Linker('rerank'), metric=MyGenerationMetric(None)),
    ],
    e2e_metric=MyE2EMetric()
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