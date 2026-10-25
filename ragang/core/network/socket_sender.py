from ragang.core.network.socket_handler import SocketHandler


class SocketSender:
    def __init__(self, handler: SocketHandler):
        self.handler = handler

    async def send_module_status(self, mid: str, is_start: bool, *, query_id=None,
                                 execution_id=None, run_id=None, status=None):
        await self.handler.broadcast('module-statu', {
            'module': mid,
            'statu': status or ('start' if is_start else 'end'),
            'query_id': query_id,
            'execution_id': execution_id,
            'run_id': run_id,
        })

    async def send_rag_preparation_sig(self, n_query: int):
        await self.handler.broadcast('rag-on', {
            'query-num': n_query,
        })

    async def send_query_end(self, qid: str, *, run_id=None, status='completed'):
        await self.handler.broadcast('ended-query', {
            'end-query': qid,
            'run_id': run_id,
            'status': status,
        })
