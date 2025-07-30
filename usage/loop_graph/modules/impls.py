import random

from modules import *


class AcceptorModule(CustomModule):  # 'starter'
    def execute(self, query: str):
        return {
            'ret': {
                'data': f"{query} - starter"
            }
        }


class MyRetrievalModule(RetrievalModule):  # 'ret'
    def execute(self, starter: dict, post: dict):
        data: dict = starter or post
        string_data: str = data['data']

        if starter:
            my_data: str = string_data + ' - ret1'
        else:
            my_data: str = string_data + str(int(string_data[-1]) + 1)
        return {
            'post': {
                'data': my_data
            },
            'metric': {
                'context': my_data
            }
        }


class MyPostRetrievalModule(PostRetrievalModule):  # 'post'
    def execute(self, ret: dict):
        if int(ret['data'][-1]) >= 5:
            target: str = 'gen'
            data = ret['data'] + ' - post'
        else:
            target: str = 'ret'
            data = ret['data']
        return {
            target: {
                'data': data
            },
            'metric': {
                'retrieved': data
            }
        }


class MyGenerationModule(GenerationModule):  # 'gen'
    def execute(self, post: dict):
        return {
            'answer': post['data'] + ' - gen',
            'metric': {
                'answer': post['data'] + ' - gen'
            }
        }
