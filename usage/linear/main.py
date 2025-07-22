from container import LinearRagContainer
from usage.linear.custom_metric import MyAccuracyMetric
from usage.linear.module_impls import MyRetrievalModule, MyGenerationModule

rag = MyRetrievalModule(metric=MyAccuracyMetric()) >> MyGenerationModule(metric=MyAccuracyMetric())

rag_container = LinearRagContainer([
    MyRetrievalModule(metric=MyAccuracyMetric()),
    MyGenerationModule(metric=MyAccuracyMetric()),
    MyRetrievalModule(),
    MyGenerationModule(metric=MyAccuracyMetric()),
])

print(rag_container.run("Hello Framework!"))
rag_container.print_eval()
