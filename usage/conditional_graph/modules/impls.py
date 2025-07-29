import random

from modules import *


class AcceptorModule(CustomModule):  # 'starter'
    def execute(self, query: str):
        return {
            'cond': {
                'data': f"{query} - starter"
            }
        }


class MyConditionalBranchModule(CustomModule):  # 'cond'
    def execute(self, starter: dict):
        if random.random() > 0.5:
            target: str = 'first_ret'
        else:
            target: str = 'second_ret'

        return {
            target: {
                'data': starter['data'] + ' - cond'
            }
        }


class MyFirstRetrievalModule(RetrievalModule):  # 'first_ret'
    def execute(self, cond: dict):
        return {
            'merge': {
                'data': cond['data'] + ' - first_ret'
            },
            'metric': {
                'context': cond['data'] + ' - first_ret'
            }
        }


class MySecondRetrievalModule(RetrievalModule):  # 'second_ret'
    def execute(self, cond: dict):
        return {
            'merge': {
                'data': cond['data'] + ' - second_ret'
            },
            'metric': {
                'context': cond['data'] + ' - second_ret'
            }
        }


class MyMergeModule(CustomModule):  # 'merge'
    def execute(self, first_ret: dict = None, second_ret: dict = None):
        input_data: dict = first_ret or second_ret

        return {
            'gen': {
                'data': input_data['data'] + ' - merge',
            },
            'metric': {
                'retrieved': input_data['data'] + ' - merge'
            }
        }


class MyGenerationModule(GenerationModule):  # 'gen'
    def execute(self, merge: dict):
        return {
            'answer': merge['data'] + ' - gen',
            'metric': {
                'answer': merge['data'] + ' - gen'
            }
        }
