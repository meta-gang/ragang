from common.bases.datas.linker import Linker
from container import RAGContainer
from usage.conditional_graph.modules.impls import *
from usage.conditional_graph.metrics.impls import *

rag = RAGContainer(
    u_fid='unique_flow_id',
    modules=[
        AcceptorModule('starter', metric=None, is_starter=True),
        MyConditionalBranchModule('cond', linker=Linker('starter')),
        MyFirstRetrievalModule('first_ret', linker=Linker('cond'), metric=MyRetrievalMetric()),
        MySecondRetrievalModule('second_ret', linker=Linker('cond'), metric=MyRetrievalMetric()),
        MyMergeModule('merge', linker=Linker('first_ret') | Linker('second_ret'), metric=MyMergeModuleMetric()),
        MyGenerationModule('gen', linker=Linker('merge'), metric=MyGenerationMetric(None)),
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