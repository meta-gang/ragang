from ragang.core.network.socket_handler import SocketHandler


class SocketSender:
    def __init__(self, handler: SocketHandler):
        self.handler = handler

    async def send_module_status(self, mid: str, is_start: bool):
        await self.handler.broadcast('module-statu', {
            'module': mid,
            'statu': 'start' if is_start else 'end'
        })

    async def send_rag_preparation_sig(self, n_query: int):
        await self.handler.broadcast('rag-on', {
            'query-num': n_query,
        })

    async def send_query_end(self, qid: str):
        await self.handler.broadcast('ended-query', {
            'end-query': qid,
        })
