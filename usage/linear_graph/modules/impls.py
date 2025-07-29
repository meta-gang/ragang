from modules import *


class AcceptorModule(CustomModule):
    def execute(self, query: str):
        return {
            'pre': {
                'data': f"{query} - starter"
            }
        }


class MyPreRetrievalModule(PreRetrievalModule):
    def execute(self, starter: dict):
        return {
            'ret': {
                'data': starter['data'] + ' - pre'
            },
            'metric': {
                'query': 'dldldl'
            }
        }


class MyRetrievalModule(RetrievalModule):
    def execute(self, pre: dict):
        return {
            'post': {
                'data': pre['data'] + ' - ret'
            },
            'metric': {
                'context': 'dldldl'
            }
        }


class MyPostRetrievalModule(PostRetrievalModule):
    def execute(self, ret: dict):
        return {
            'gen': {
                'data': ret['data'] + ' - post'
            },
            'metric': {
                'context': 'dldldl'
            }
        }


class MyGenerationModule(GenerationModule):
    def execute(self, post: dict):
        return {
            'answer': post['data'] + ' - gen',
            'metric': {
                'answer': post['data'] + ' - gen'
            }
        }
