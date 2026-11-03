"""Real WebSocket acceptance for idempotent, correlated on-prem dashboard requests."""
import asyncio
import json
import os
import tempfile
import unittest
import warnings
from pathlib import Path
from unittest.mock import patch

import websockets

from ragang.container import RAGContainer
from ragang.core.bases.abstracts.base_engine import FlowEngine
from ragang.core.bases.datas.linker import Linker
from ragang.core.network.runner import Runner
from ragang.core.network.socket_handler import SocketHandler
from ragang.core.network.socket_sender import SocketSender
from ragang.core.network.request_context import current_request
from ragang.modules.custom import CustomModule
from tests.test_core_regressions import Starter


class ProbeOutput(CustomModule):
    gate = None
    calls = []

    async def execute(self, query):
        self.__class__.calls.append(query)
        if query == 'wait':
            await self.__class__.gate.wait()
        if query == 'bad':
            raise RuntimeError('synthetic module failure')
        return {'gen': f'answer:{query}'}


def engine():
    return FlowEngine([RAGContainer('flow', [Starter('starter', is_starter=True),
                       ProbeOutput('output', linker=Linker('starter'))])])


class RequestCorrelationTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.previous = os.getcwd()
        os.chdir(self.temp.name)
        ProbeOutput.gate = asyncio.Event()
        ProbeOutput.calls = []
        self.engine = engine()
        self.handler = SocketHandler()
        self.engine.set_ws_sender(SocketSender(self.handler))
        self.runner = Runner(self.handler, self.engine, 'flow')
        self.handler.on_message = self.runner.dispatch
        self.server = await websockets.serve(self.handler.handle_connection, '127.0.0.1', 0)
        self.url = f'ws://127.0.0.1:{self.server.sockets[0].getsockname()[1]}'
        self.clients = []
        self.events = {}
        self.warning = warnings.catch_warnings()
        self.warning.__enter__()
        warnings.simplefilter('ignore', RuntimeWarning)

    async def asyncTearDown(self):
        await self.runner.shutdown()
        for client in self.clients:
            await client.close()
        self.server.close()
        await self.server.wait_closed()
        self.warning.__exit__(None, None, None)
        os.chdir(self.previous)
        self.temp.cleanup()

    async def connect(self, subscribe=True):
        client = await websockets.connect(self.url)
        self.clients.append(client)
        self.events[client] = []
        if subscribe:
            await self.send(client, topic='subscribe', topics=['rag-on', 'module-statu', 'ended-query', 'rag-result-data', 'error', 'request-status'])
        return client

    async def send(self, client, **message):
        await client.send(json.dumps(message))

    async def receive(self, client, predicate):
        async with asyncio.timeout(4):
            while True:
                message = json.loads(await client.recv())
                self.events[client].append(message)
                if predicate(message):
                    return message

    async def status(self, client, request_id, status):
        return await self.receive(client, lambda m: m['topic'] == 'request-status' and m['request_id'] == request_id and m['status'] == status)

    async def request(self, client, request_id, query='good'):
        await self.send(client, topic='test-query', request_id=request_id, query=query)

    async def test_two_clients_same_text_queue_duplicate_and_correlated_events(self):
        first, second = await self.connect(), await self.connect()
        await self.request(first, 'first', 'wait')
        await self.receive(first, lambda m: m['topic'] == 'module-statu' and m.get('module') == 'output' and m['statu'] == 'running')
        await self.request(second, 'second', 'wait')
        await self.status(second, 'second', 'queued')
        self.assertFalse(any(m['topic'] == 'rag-on' and m.get('request_id') == 'second' for m in self.events[second]))
        await self.request(second, 'first', 'different text is still a duplicate')
        await self.status(second, 'first', 'running')
        self.assertEqual(ProbeOutput.calls, ['wait'])
        ProbeOutput.gate.set()
        one = await self.status(first, 'first', 'completed')
        two = await self.status(second, 'second', 'completed')
        self.assertNotEqual(one['query_ids'], two['query_ids'])
        self.assertNotEqual(one['run_ids'], two['run_ids'])
        self.assertTrue(one['persisted'] and two['persisted'])
        self.assertEqual(ProbeOutput.calls, ['wait', 'wait'])
        for request_id in ('first', 'second'):
            events = [m for m in self.events[second] if m.get('request_id') == request_id]
            self.assertEqual(sum(m['topic'] == 'rag-on' for m in events), 1)
            result = next(m for m in events if m['topic'] == 'rag-result-data')
            self.assertTrue(all(state['query'] == 'wait' and state['run_metadata']['request_id'] == request_id
                                for state in result['storage']['states'].values()))
            self.assertTrue(any(m['topic'] == 'ended-query' for m in events))
        await self.request(first, 'first')
        await self.status(first, 'first', 'completed')
        self.assertEqual(len(ProbeOutput.calls), 2)
        self.assertIsNone(current_request.get())

    async def test_partial_batch_and_raised_failure_preserve_request_in_history_and_errors(self):
        base = Path('datas/queries/custom')
        base.mkdir(parents=True)
        (base / 'questions.txt').write_text('good\nbad\n')
        client = await self.connect()
        await self.send(client, topic='run-rag-file-query', request_id='batch', settings={'file_name': 'questions.txt'})
        record = await self.status(client, 'batch', 'failed')
        self.assertTrue(record['persisted'])
        self.assertEqual(len(record['query_ids']), 2)
        states = next(m for m in self.events[client] if m['topic'] == 'rag-result-data')['storage']['states']
        self.assertEqual({state['run_metadata']['request_id'] for state in states.values()}, {'batch'})
        self.assertEqual(sum(state['execution_summary']['terminated'] for state in states.values()), 1)
        await self.request(client, 'failure', 'bad')
        await self.status(client, 'failure', 'failed')
        self.assertTrue(any(m['topic'] == 'error' and m.get('request_id') == 'failure' for m in self.events[client]))
        await self.request(client, 'invalid-query', '')
        invalid = await self.status(client, 'invalid-query', 'failed')
        self.assertFalse(invalid['persisted'])
        self.assertEqual(invalid['query_ids'], [])

    async def test_disconnected_request_continues_and_new_process_recovers_exact_history_id(self):
        client = await self.connect()
        await self.request(client, 'recover', 'wait')
        await self.receive(client, lambda m: m['topic'] == 'module-statu' and m.get('module') == 'output' and m['statu'] == 'running')
        await client.close()
        replacement = await self.connect(subscribe=False)
        await self.send(replacement, topic='get-request-status', request_id='recover')
        await self.status(replacement, 'recover', 'running')
        ProbeOutput.gate.set()
        async with asyncio.timeout(4):
            while self.runner._requests['recover']['status'] not in ('completed', 'failed'):
                await asyncio.sleep(.005)
        fresh_engine = engine()
        fresh_engine.set_ws_sender(SocketSender(self.handler))
        self.runner = Runner(self.handler, fresh_engine, 'flow')
        self.handler.on_message = self.runner.dispatch
        await self.send(replacement, topic='get-request-status', request_id='recover')
        recovered = await self.status(replacement, 'recover', 'completed')
        self.assertTrue(recovered['persisted'])
        self.assertEqual(len(recovered['query_ids']), 1)
        await self.request(replacement, 'recover', 'must never execute')
        await self.status(replacement, 'recover', 'completed')
        self.assertEqual(ProbeOutput.calls, ['wait'])
        self.assertEqual(fresh_engine.containers['flow'].storage.results, {})

    async def test_status_is_direct_and_malformed_frames_and_ids_leave_connection_usable(self):
        requester, observer = await self.connect(), await self.connect()
        for raw in ('not json', '[]', '{"topic":[]}'):
            await requester.send(raw)
        await self.send(requester, topic='get-request-status', request_id='unknown')
        await self.status(requester, 'unknown', 'unknown')
        with self.assertRaises(asyncio.TimeoutError):
            await asyncio.wait_for(observer.recv(), .05)
        for invalid in (None, {}, [], True, '', '../private', '비공개', 'x' * 129):
            await self.request(requester, invalid)
            error = await self.receive(requester, lambda m: m['topic'] == 'error')
            self.assertEqual(error['code'], 'invalid_request_id')
            self.assertIsNone(error['request_id'])
            self.assertNotIn('../private', json.dumps(error))
        await self.send(requester, topic='test-query', query='legacy')
        accepted = await self.receive(requester, lambda m: m['topic'] == 'request-status' and m['status'] == 'queued')
        self.assertEqual(len(accepted['request_id']), 36)
        await self.status(requester, accepted['request_id'], 'completed')

    async def test_registry_evicts_only_persisted_terminal_and_never_reexecutes_evicted_id(self):
        self.runner.max_request_records = 1
        client = await self.connect()
        for request_id in ('one', 'two'):
            await self.request(client, request_id)
            await self.status(client, request_id, 'completed')
        self.assertNotIn('one', self.runner._requests)
        await self.request(client, 'one')
        await self.status(client, 'one', 'completed')
        self.assertEqual(ProbeOutput.calls, ['good', 'good'])
        await self.request(client, 'protected-failure', '')
        await self.status(client, 'protected-failure', 'failed')
        await self.request(client, 'over-capacity')
        error = await self.receive(client, lambda m: m['topic'] == 'error' and m.get('request_id') == 'over-capacity')
        self.assertEqual(error['code'], 'request_capacity')
        self.assertEqual(ProbeOutput.calls, ['good', 'good'])
        await self.request(client, 'protected-failure')
        await self.status(client, 'protected-failure', 'failed')
        self.assertEqual(ProbeOutput.calls, ['good', 'good'])

    async def test_unreadable_history_fails_closed_and_shutdown_persists_cancelled_partial_state(self):
        client = await self.connect()
        with patch('ragang.core.network.runner.get_history', side_effect=ValueError('synthetic history failure')):
            await self.request(client, 'no-history')
            error = await self.receive(client, lambda m: m['topic'] == 'error')
            self.assertEqual(error['code'], 'history_unavailable')
        self.assertEqual(ProbeOutput.calls, [])
        await self.request(client, 'cancel', 'wait')
        await self.receive(client, lambda m: m['topic'] == 'module-statu' and m.get('module') == 'output' and m['statu'] == 'running')
        await self.runner.shutdown()
        cancelled = await self.status(client, 'cancel', 'failed')
        self.assertTrue(cancelled['persisted'])
        state = self.engine.containers['flow'].storage.results[cancelled['query_ids'][0]]
        self.assertEqual(state.run_metadata['request_id'], 'cancel')
        self.assertEqual(state.execution_summary['termination_reason'], 'cancelled')
        self.assertEqual(len(self.runner._request_tasks), 0)


    async def test_generated_batch_and_persistence_failure_keep_the_same_request(self):
        base = Path('datas/queries/generated')
        base.mkdir(parents=True)
        (base / 'questions.json').write_text(json.dumps({'query': [{'query': 'good'}, {'query': 'also good'}]}))
        client = await self.connect()
        await self.send(client, topic='run-rag-llm-query', request_id='generated', settings={'file_name': 'questions.json'})
        record = await self.status(client, 'generated', 'completed')
        self.assertEqual(len(record['query_ids']), 2)
        self.assertEqual(sum(m['topic'] == 'rag-on' and m.get('request_id') == 'generated' for m in self.events[client]), 1)
        with patch('ragang.core.network.runner.update_history', side_effect=OSError('synthetic disk failure')):
            await self.request(client, 'unsaved')
            failed = await self.status(client, 'unsaved', 'failed')
        self.assertFalse(failed['persisted'])
        result = next(m for m in self.events[client] if m['topic'] == 'rag-result-data' and m.get('request_id') == 'unsaved')
        self.assertFalse(result['persisted'])
        self.assertTrue(all(state['run_metadata']['request_id'] == 'unsaved' for state in result['storage']['states'].values()))
        previous_calls = len(ProbeOutput.calls)
        await self.request(client, 'unsaved')
        await self.status(client, 'unsaved', 'failed')
        self.assertEqual(len(ProbeOutput.calls), previous_calls)

    async def test_shutdown_before_a_task_starts_retains_failed_duplicate_protection(self):
        await self.runner.dispatch({'topic': 'test-query', 'request_id': 'not-started', 'query': 'good'}, None)
        await self.runner.shutdown()
        record = self.runner._requests['not-started']
        self.assertEqual(record['status'], 'failed')
        self.assertFalse(record['persisted'])
        self.assertNotIn('_ws', record)
        self.assertEqual(ProbeOutput.calls, [])
        self.assertEqual(len(self.runner._request_tasks), 0)
        client = await self.connect()
        await self.request(client, 'not-started')
        await self.status(client, 'not-started', 'failed')
        self.assertEqual(ProbeOutput.calls, [])

    async def test_worker_reads_disk_only_and_nonexecution_errors_are_not_misattributed(self):
        client, observer = await self.connect(), await self.connect()
        main_thread = __import__('threading').get_ident()
        snapshot_threads = []
        original = self.runner._memory_request
        def snapshot(request_id):
            snapshot_threads.append(__import__('threading').get_ident())
            return original(request_id)
        with patch.object(self.runner, '_memory_request', side_effect=snapshot):
            await self.request(client, 'snapshot')
            await self.status(client, 'snapshot', 'completed')
        self.assertEqual(snapshot_threads, [main_thread])
        async def invalid_operation(msg, ws):
            raise ValueError('synthetic non-execution error')
        self.runner.topic_map['invalid-operation'] = invalid_operation
        await self.send(client, topic='invalid-operation')
        error = await self.receive(client, lambda m: m['topic'] == 'error')
        self.assertNotIn('request_id', error)
        self.assertIsNone(current_request.get())


    async def test_simultaneous_duplicate_acceptance_is_atomic(self):
        first, second = await self.connect(), await self.connect()
        await asyncio.gather(self.request(first, 'shared-id'), self.request(second, 'shared-id'))
        async with asyncio.timeout(4):
            while self.runner._requests.get('shared-id', {}).get('status') not in ('completed', 'failed'):
                await asyncio.sleep(.005)
        for client in (first, second):
            await self.send(client, topic='get-request-status', request_id='shared-id')
            status = await self.status(client, 'shared-id', 'completed')
            self.assertEqual(len(status['query_ids']), 1)
        self.assertEqual(ProbeOutput.calls, ['good'])
