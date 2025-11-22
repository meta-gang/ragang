from ragang.core.bases.abstracts.base_engine import FlowEngine
from ragang.core.bases.datas.linker import Linker
from ragang.container import RAGContainer
from ragang.usage.linear_graph.metrics.impls import MyPreRetrievalMetric, MyRetrievalMetric, MyPostRetrievalMetric, \
    MyGenerationMetric, MyE2EMetric
from ragang.usage.linear_graph.modules.impls import AcceptorModule, MyPreRetrievalModule, MyRetrievalModule, \
    MyPostRetrievalModule, MyGenerationModule

rag = RAGContainer(
    flow_id="linear_graph",
    modules=[
        AcceptorModule('starter', is_starter=True),
        MyPreRetrievalModule('pre', linker=Linker('starter'), metrics=[MyPreRetrievalMetric(param_refs=['pre.query'])]),
        MyRetrievalModule('ret', linker=Linker('pre'), metrics=[MyRetrievalMetric(param_refs=['ret.ctx'])]),
        MyPostRetrievalModule('post', linker=Linker('ret'), metrics=[MyPostRetrievalMetric(param_refs=['ret.ctx'])]),
        MyGenerationModule('output', linker=Linker('post'), metrics=[MyGenerationMetric(['output.gen'], None)]),
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