from container import LinearRagContainer
from usage.linear.custom_metric import MyAccuracyMetric, MyF1ScoreMetric
from usage.linear.module_impls import MyRetrievalModule, MyGenerationModule

rag = MyRetrievalModule(metric=MyAccuracyMetric()) >> MyGenerationModule(metric=MyAccuracyMetric())

rag_container = LinearRagContainer(
    modules=[
        MyRetrievalModule(metric=MyAccuracyMetric()),
        MyGenerationModule(metric=MyF1ScoreMetric()),
        MyRetrievalModule(),
        MyGenerationModule(metric=MyAccuracyMetric()),
    ],
    )

rag_container.print_eval()
print(f"Result: {rag_container.run("Hello Framework!")}")
