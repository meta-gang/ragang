from core.bases.abstracts.base_engine import FlowEngine
from core.bases.datas.linker import Linker
from container import RAGContainer
from usage.loop_graph.modules.impls import *
from usage.loop_graph.metrics.impls import *

rag = RAGContainer(
    flow_id="loop_graph",
    modules=[
        AcceptorModule('starter', metrics=None, is_starter=True),
        MyRetrievalModule('ret', linker=Linker('starter') | Linker('post'), metrics=[MyRetrievalMetric(['starter.query'])]),
        MyPostRetrievalModule('post', linker=Linker('ret'), metrics=[MyPostRetrievalMetric(['starter.query']), MySecondPostRetrievalMetric(['starter.query'])]),
        MyGenerationModule('output', linker=Linker('post'), metrics=[MyGenerationMetric(['starter.query'], None)]),
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