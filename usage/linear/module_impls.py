from modules.linear import RetrievalModule, GenerationModule


class MyRetrievalModule(RetrievalModule):
    def execute(self, query: str) -> tuple[str, str]:
        return query, "RETRIEVED_CONTENT"


class MyGenerationModule(GenerationModule):
    def execute(self, data: tuple[str, str]) -> str:
        return f"Generated: {data[0]} + {data[1]}"
