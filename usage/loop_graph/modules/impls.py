import random

from modules import *


class AcceptorModule(CustomModule):  # 'starter'
    def execute(self, query: str):
        return {
            'query': query + '-starter'
        }


class MyRetrievalModule(RetrievalModule):  # 'ret'
    def execute(self, query: str):
        if query.count('-') == 1:
            my_data: str = query + '-ret1'
        else:
            my_data: str = query + str(int(query[-1]) + 1)
        return {
           'sfn_query': my_data
        }


class MyPostRetrievalModule(PostRetrievalModule):  # 'post'
    def execute(self, sfn_query: str):
        if int(sfn_query[-1]) >= 5:
            return {
                'next': ['output'],
                'result': sfn_query + '-post'
            }
        return {
            'next': ['ret'],
            'query': sfn_query
        }


class MyGenerationModule(GenerationModule):  # 'output'
    def execute(self, result: str):
        print([(p.metric,p.score) for p in self.get_performance('post')])
        return {
            'gen': result + '-output',
        }
