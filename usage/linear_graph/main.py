from common.bases.datas.linker import Linker
from container import RAGContainer
from usage.linear_graph.metrics.impls import MyPreRetrievalMetric, MyRetrievalMetric, MyPostRetrievalMetric, \
    MyGenerationMetric, MyE2EMetric
from usage.linear_graph.modules.impls import AcceptorModule, MyPreRetrievalModule, MyRetrievalModule, \
    MyPostRetrievalModule, MyGenerationModule

rag = RAGContainer(
    u_fid='unique_flow_id',
    modules=[
        AcceptorModule('starter', metric=None, is_starter=True),
        MyPreRetrievalModule('pre', linker=Linker('starter'), metric=MyPreRetrievalMetric()),
        MyRetrievalModule('ret', linker=Linker('pre'), metric=MyRetrievalMetric()),
        MyPostRetrievalModule('post', linker=Linker('ret'), metric=MyPostRetrievalMetric()),
        MyGenerationModule('gen', linker=Linker('post'), metric=MyGenerationMetric(None)),
    ],
    e2e_metric=MyE2EMetric()
)

# answer = rag.invoke('Hello, Ragang')
# print(f'Answer: {answer}')
# rag.print_eval()

rag.invoke_batch([
    'Hello, Ragang',
    'Hello, SKKU',
    'Hello, Metabuild'
])
rag.print_eval()