from core.bases.abstracts.base_engine import FlowEngine
from core.bases.datas.linker import Linker
from container import RAGContainer
from usage.merge_graph.modules.impls import *
from usage.merge_graph.metrics.impls import *

rag = RAGContainer(
    modules=[
        AcceptorModule('starter', metrics=None, is_starter=True),
        MyBranchingModule('branch', linker=Linker('starter'), metrics=None),
        MyRetrievalModule('first_ret', linker=Linker('branch'), metrics=[MyRetrievalMetric(['starter.query'])]),
        MyRetrievalModule('second_ret', linker=Linker('branch'), metrics=[MyRetrievalMetric(['starter.query'])]),
        MyRerankingModule('rerank', linker=Linker('first_ret') & Linker('second_ret'), metrics=[MyRerankingMetric(['starter.query'])]),
        MyGenerationModule('output', linker=Linker('rerank'), metrics=[MyGenerationMetric(['starter.query'], None)]),
    ],
    e2e_metrics=[MyE2EMetric([])]
)

engine: FlowEngine = FlowEngine([rag])

# answer = engine.invoke('Hello, Ragang')
# print(f'Answer: {answer}')
# engine.print_eval()

engine.invoke_batch([
    'Hello, Ragang',
    'Hello, Starbucks',
    'Hello, SKKU',
    'Hello, Metabuild'
])
engine.print_eval()