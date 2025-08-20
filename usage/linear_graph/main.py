from core.bases.datas.linker import Linker
from container import RAGContainer
from usage.linear_graph.metrics.impls import MyPreRetrievalMetric, MyRetrievalMetric, MyPostRetrievalMetric, \
    MyGenerationMetric, MyE2EMetric
from usage.linear_graph.modules.impls import AcceptorModule, MyPreRetrievalModule, MyRetrievalModule, \
    MyPostRetrievalModule, MyGenerationModule

rag = RAGContainer(
    u_fid='unique_flow_id',
    modules=[
        AcceptorModule('starter', metrics=None, is_starter=True),
        MyPreRetrievalModule('pre', linker=Linker('starter'), metrics=[MyPreRetrievalMetric()]),
        MyRetrievalModule('ret', linker=Linker('pre'), metrics=[MyRetrievalMetric()]),
        MyPostRetrievalModule('post', linker=Linker('ret'), metrics=[MyPostRetrievalMetric()]),
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