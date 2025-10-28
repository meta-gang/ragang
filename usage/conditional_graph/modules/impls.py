import random

from modules import *


class AcceptorModule(CustomModule):  # 'starter'
    def execute(self, query: str):
        return {
            'query': query + '-starter'
        }


class MyConditionalBranchModule(CustomModule):  # 'cond'
    def execute(self, query: str):
        if random.random() > 0.5:
            target: str = 'first_ret'
        else:
            target: str = 'second_ret'

        return {
            'next': [target],
            'query': query + '-cond',
            'a': 'for metric'
        }


class MyFirstRetrievalModule(RetrievalModule):  # 'first_ret'
    def execute(self, query: str):
        return {
            'query': query + '-first_ret'
        }


class MySecondRetrievalModule(RetrievalModule):  # 'second_ret'
    def execute(self, query: str):
        return {
            'query': query + '-second_ret'
        }


class MyMergeModule(CustomModule):  # 'merge'
    def execute(self, query: str):
        return {
            'query': query + '-merge'
        }


class MyGenerationModule(GenerationModule):  # 'output'
    def execute(self, query: str):
        return {
            'gen': query + '-output'
        }
