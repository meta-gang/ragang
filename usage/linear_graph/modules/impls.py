from modules import *


class AcceptorModule(CustomModule):  # starter
    def execute(self, query: str):
        return {
            'some': query,
            'thing': "[advanced]"
        }


class MyPreRetrievalModule(PreRetrievalModule):  # pre
    def execute(self, some: str, thing: str):
        return {
            'query': some,
            'advanced_q': some + thing
        }


class MyRetrievalModule(RetrievalModule):  # ret
    def execute(self, advanced_q: str):
        return {
            'ctx': [advanced_q],
        }


class MyPostRetrievalModule(PostRetrievalModule):  # post
    def execute(self, ctx: list[str]):
        return {
            'ret': ' '.join(ctx),
        }


class MyGenerationModule(GenerationModule):  # output
    def execute(self, ret: str):
        return {
            'gen': ret
        }
