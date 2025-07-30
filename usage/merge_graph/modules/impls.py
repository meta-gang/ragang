from modules import *


class AcceptorModule(CustomModule):  # 'starter'
    def execute(self, query: str):
        return {
            'branch': {
                'data': f"{query} - starter"
            }
        }


class MyBranchingModule(CustomModule):  # 'branch'
    def execute(self, starter: dict):
        return {
            'first_ret': {
                'data': starter['data'] + ' - branch'
            },
            'second_ret': {
                'data': starter['data'] + ' - branch'
            }
        }


class MyRetrievalModule(RetrievalModule):  # 'first_ret', 'second_ret'
    def execute(self, branch: dict):
        return {
            'rerank': {
                'data': branch['data'] + f' - {self.module_id}'
            },
            'metric': {
                'ret_docs': branch['data'] + f' - {self.module_id}'
            }
        }


class MyRerankingModule(CustomModule):  # 'rerank'
    def execute(self, first_ret: dict, second_ret: dict):
        data: str = f"[{first_ret['data']} & {second_ret['data']}]"
        return {
            'output': {
                'data': f'{data} - rerank',
            },
            'metric': {
                'ret_docs': f'{data} - rerank',
            }
        }


class MyGenerationModule(GenerationModule):  # 'gen'
    def execute(self, rerank: dict):
        print('generation')
        return {
            'gen': rerank['data'] + ' - gen',
            'metric': {
                'gen': rerank['data'] + ' - gen'
            }
        }
