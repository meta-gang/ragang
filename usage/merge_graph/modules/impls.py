from modules import *


class AcceptorModule(CustomModule):  # 'starter'
    def execute(self, query: str):
        return {
            'query': query + '-starter'
        }


class MyBranchingModule(CustomModule):  # 'branch'
    def execute(self, query: str):
        return {
            'next': ['first_ret', 'second_ret'],
            'query': query + '-branch'
        }


class MyRetrievalModule(RetrievalModule):  # 'first_ret', 'second_ret'
    def execute(self, query: str):
        return {
            self.module_id: query + f'-{self.module_id}'
        }


class MyRerankingModule(CustomModule):  # 'rerank'
    def execute(self, first_ret: str, second_ret: str):
        data: str = f"[{first_ret} & {second_ret}]"
        return {
           'query': data
        }


class MyGenerationModule(GenerationModule):  # 'output'
    def execute(self, query: str):
        return {
            'gen': query + '-output',
        }
