from core.bases.abstracts.base_engine import FlowEngine
from core.bases.datas.linker import Linker
from container import RAGContainer
from usage.conditional_graph.modules.impls import *
from usage.conditional_graph.metrics.impls import *

rag = RAGContainer(
    flow_id='conditional_graph',
    modules=[
        AcceptorModule('starter', metrics=None, is_starter=True),
        MyConditionalBranchModule('cond', linker=Linker('starter')),
        MyFirstRetrievalModule('first_ret', linker=Linker('cond'), metrics=[MyRetrievalMetric(['cond.a'])]),
        MySecondRetrievalModule('second_ret', linker=Linker('cond'), metrics=[MyRetrievalMetric(['cond.a'])]),
        MyMergeModule('merge', linker=Linker('first_ret') | Linker('second_ret'), metrics=[MyMergeModuleMetric(['cond.a'])]),
        MyGenerationModule('output', linker=Linker('merge'), metrics=[MyGenerationMetric(['cond.a'],None)]),
    ],
    e2e_metrics=[MyE2EMetric([])]
)

engine: FlowEngine = FlowEngine([rag])

# answer = engine.invoke('Hello, Ragang')
# print(f'Answer: {answer}')
# engine.print_eval()

# engine.invoke_batch([
#     'Hello, Ragang',
#     'Hello, Starbucks',
#     'Hello, SKKU',
#     'Hello, Metabuild'
# ])
# engine.print_eval()