"""User-facing execution contracts: terminal answers, routing, failure and timing."""

import asyncio
from contextlib import redirect_stdout
import io
import threading
import time
import unittest
from unittest.mock import patch
import warnings

from ragang.container import RAGContainer
from ragang.core.bases.abstracts.base_engine import FlowEngine
from ragang.core.bases.datas.linker import Linker
from ragang.core.bases.datas.performance import Performance
from ragang.exceptions.user.module import FlowOutputException, ModuleOutputException
from ragang.metrics.custom import CustomMetric
from ragang.modules.custom import CustomModule
from tests.test_core_regressions import Starter, Output, PassThrough


class Draft(CustomModule):
    async def execute(self, query):
        return {"query": query, "gen": "draft"}


class Review(CustomModule):
    async def execute(self, query, gen):
        return {"gen": f"reviewed:{gen}:{query}"}


class OnlySide(CustomModule):
    async def execute(self, query):
        return {"next": ["side"], "query": query}


class SlowModule(CustomModule):
    async def execute(self, query):
        await asyncio.sleep(10)
        return {"gen": query}


class EngineAcceptanceTests(unittest.TestCase):
    def setUp(self):
        self.warning_context = warnings.catch_warnings()
        self.warning_context.__enter__()
        warnings.simplefilter("ignore", RuntimeWarning)

    def tearDown(self):
        self.warning_context.__exit__(None, None, None)

    @staticmethod
    def stored(container):
        return next(iter(container.storage.results.values()))

    def test_draft_generation_continues_to_review_and_records_final_answer(self):
        cont = RAGContainer("draft", [
            Starter("starter", is_starter=True),
            Draft("draft", linker=Linker("starter")),
            Review("review", linker=Linker("draft")),
        ])
        FlowEngine([cont]).invoke("question")
        state = self.stored(cont)
        self.assertEqual(state.gen, "reviewed:draft:question")
        self.assertEqual([e["module_id"] for e in state.execution_trace], ["starter", "draft", "review"])
        self.assertFalse(state.snapshots["draft"][0].is_answer)
        self.assertEqual(state.execution_trace[-1]["parent_execution_ids"], ["exec-2"])

    def test_explicit_terminal_can_end_before_a_declared_successor(self):
        class Final(CustomModule):
            async def execute(self, query):
                return {"gen": "final", "terminal": True}
        cont = RAGContainer("explicit", [
            Starter("starter", is_starter=True), Final("final", linker=Linker("starter")),
            Output("unused", linker=Linker("final")),
        ])
        FlowEngine([cont]).invoke("q")
        self.assertEqual(self.stored(cont).gen, "final")
        self.assertNotIn("unused", self.stored(cont).snapshots)
        self.assertEqual(self.stored(cont).execution_trace[-1]["next_modules"], [])

    def test_explicit_nonterminal_leaf_is_not_fabricated_as_a_final_answer(self):
        class NotFinal(CustomModule):
            async def execute(self, query):
                return {"gen": "draft", "terminal": False}
        cont = RAGContainer("unfinished", [NotFinal("draft", is_starter=True)])
        with self.assertRaises(FlowOutputException):
            FlowEngine([cont]).invoke("q")
        state = self.stored(cont)
        self.assertIsNone(state.gen)
        self.assertEqual(state.execution_summary["termination_reason"], "missing_output")
        self.assertTrue(state.execution_summary["terminated"])

    def test_invalid_output_shapes_are_failed_and_persisted(self):
        for output in [None, [], {"next": "out"}, {"next": ["out", "out"]},
                       {"terminal": "true", "gen": "draft"}, {"terminal": True},
                       {"gen": ""}, {"gen": 7}, {"gen": "final", "terminal": True, "next": ["out"]}]:
            with self.subTest(output=output):
                class Invalid(CustomModule):
                    async def execute(self, query):
                        return output
                cont = RAGContainer("invalid", [
                    Invalid("starter", is_starter=True), Output("out", linker=Linker("starter")),
                ])
                with self.assertRaises(ModuleOutputException):
                    FlowEngine([cont]).invoke("q")
                state = self.stored(cont)
                self.assertEqual(state.execution_trace[-1]["status"], "failed")
                self.assertEqual(state.execution_trace[-1]["failure"]["type"], "ModuleOutputException")
                self.assertFalse(state.gen)

    def test_inactive_and_dependency_stays_unsatisfied_with_preserved_state(self):
        cont = RAGContainer("inactive", [
            Starter("starter", is_starter=True), OnlySide("route", linker=Linker("starter")),
            PassThrough("side", linker=Linker("route")),
            Output("join", linker=Linker("route") & Linker("side")),
        ])
        with self.assertRaises(FlowOutputException):
            FlowEngine([cont]).invoke("q")
        state = self.stored(cont)
        self.assertEqual(state.execution_trace[1]["next_modules"], ["side"])
        self.assertEqual([e["module_id"] for e in state.execution_trace], ["starter", "route", "side"])
        self.assertEqual(state.execution_summary["termination_reason"], "missing_output")

    def test_or_join_uses_only_actually_selected_incoming_edges(self):
        cont = RAGContainer("or_join", [
            Starter("starter", is_starter=True), OnlySide("route", linker=Linker("starter")),
            PassThrough("side", linker=Linker("route")),
            Output("join", linker=Linker("route") | Linker("side")),
        ])
        FlowEngine([cont]).invoke("q")
        state = self.stored(cont)
        self.assertEqual(state.gen, "answer:q")
        self.assertEqual(state.execution_trace[-1]["parent_execution_ids"], ["exec-3"])

    def test_scheduler_failure_preserves_completed_output_and_failure_metadata(self):
        cont = RAGContainer("schedule", [
            Starter("starter", is_starter=True), Output("output", linker=Linker("starter")),
        ])
        engine = FlowEngine([cont])
        with patch.object(engine, "_FlowEngine__schedule_next_module", side_effect=RuntimeError("schedule failed")):
            with self.assertRaisesRegex(RuntimeError, "schedule failed"):
                engine.invoke("q")
        state = self.stored(cont)
        self.assertIn("starter", state.snapshots)
        self.assertEqual(state.execution_trace[-1]["status"], "failed")
        self.assertEqual(state.execution_trace[-1]["failure"]["type"], "RuntimeError")
        self.assertEqual(state.execution_summary["termination_reason"], "scheduler_error")

    def test_deepcopy_failure_is_recorded_as_a_module_failure(self):
        class Uncopyable(CustomModule):
            def __deepcopy__(self, memo):
                raise RuntimeError("cannot copy integration")
            async def execute(self, query):
                return {"gen": query}
        cont = RAGContainer("copy", [Uncopyable("starter", is_starter=True)])
        with self.assertRaisesRegex(RuntimeError, "cannot copy"):
            FlowEngine([cont]).invoke("q")
        self.assertEqual(self.stored(cont).execution_trace[-1]["failure"]["type"], "RuntimeError")

    def test_module_timeout_preserves_the_failed_attempt(self):
        cont = RAGContainer("timeout", [SlowModule("slow", is_starter=True)], module_timeout_seconds=0.01)
        with self.assertRaises(TimeoutError):
            FlowEngine([cont]).invoke("q")
        state = self.stored(cont)
        self.assertEqual(state.execution_trace[-1]["failure"]["type"], "TimeoutError")
        self.assertTrue(state.execution_summary["terminated"])
        self.assertGreater(state.total_wall_seconds, 0)

    def test_cancelled_query_preserves_the_failed_attempt(self):
        cont = RAGContainer("cancel", [SlowModule("slow", is_starter=True)])
        async def scenario():
            task = asyncio.create_task(FlowEngine([cont]).async_invoke("q"))
            await asyncio.sleep(0.01)
            task.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await task
        asyncio.run(scenario())
        state = self.stored(cont)
        self.assertEqual(state.execution_summary["termination_reason"], "cancelled")
        self.assertEqual(state.execution_trace[-1]["failure"]["type"], "CancelledError")

    def test_sync_judge_does_not_block_the_event_loop_and_has_separate_timing(self):
        started, release = threading.Event(), threading.Event()
        class BlockingJudge(CustomMetric):
            def evaluate(self, value):
                started.set()
                if not release.wait(2):
                    raise TimeoutError("test judge was never released")
                return Performance(score=1, metric="judge", unit="0 to 1")
        cont = RAGContainer("responsive", [
            Starter("starter", is_starter=True),
            Output("output", linker=Linker("starter"), metrics=[BlockingJudge(["output.gen"])]),
        ])
        async def scenario():
            task = asyncio.create_task(FlowEngine([cont]).async_invoke("q"))
            try:
                self.assertTrue(await asyncio.to_thread(started.wait, 1))
                await asyncio.sleep(0.01)
                self.assertFalse(task.done())
            finally:
                release.set()
            await task
        asyncio.run(scenario())
        state = self.stored(cont)
        self.assertGreater(state.execution_summary["evaluator_latency_seconds"], 0)
        self.assertGreater(state.total_wall_seconds, state.execution_summary["total_latency_seconds"])
        self.assertEqual(state.evaluation_summary["attempted"], 1)
        self.assertEqual(state.evaluation_summary["evaluated"], 1)

    def test_failed_query_is_printable_and_reports_unreached_e2e_metrics(self):
        class Broken(CustomModule):
            async def execute(self, query):
                raise RuntimeError("retriever unavailable")
        class Metric(CustomMetric):
            def evaluate(self, *values):
                return Performance(score=1)
        cont = RAGContainer("print", [Broken("broken", is_starter=True)],
                            e2e_metrics=[Metric(["starter.query", "output.gen"])])
        with self.assertRaises(RuntimeError):
            FlowEngine([cont]).invoke("q")
        capture = io.StringIO()
        with redirect_stdout(capture):
            cont.print_eval()
        self.assertIn("Execution failed", capture.getvalue())
        self.assertEqual(self.stored(cont).evaluation_summary["not_reached_e2e_metrics"], 1)
        self.assertEqual(self.stored(cont).evaluation_summary["attempted"], 0)

    def test_one_run_identity_per_batch_and_new_identity_on_next_invocation(self):
        cont = RAGContainer("runs", [Output("output", is_starter=True)])
        engine = FlowEngine([cont])
        engine.invoke_batch(["one", "two"])
        first_states = list(cont.storage.results.values())
        self.assertEqual(len({s.run_metadata["run_id"] for s in first_states}), 1)
        self.assertEqual(len({s.run_metadata["started_at"] for s in first_states}), 1)
        engine.invoke("three")
        self.assertNotEqual(first_states[0].run_metadata["run_id"], list(cont.storage.results.values())[-1].run_metadata["run_id"])

    def test_batch_respects_configured_query_concurrency(self):
        counts = {"active": 0, "maximum": 0}
        class Counted(CustomModule):
            async def execute(self, query):
                counts["active"] += 1
                counts["maximum"] = max(counts["maximum"], counts["active"])
                await asyncio.sleep(0.01)
                counts["active"] -= 1
                return {"gen": query}
        cont = RAGContainer("bounded", [Counted("output", is_starter=True)], max_concurrency=2)
        FlowEngine([cont]).invoke_batch(["a", "b", "c", "d", "e"])
        self.assertEqual(counts["maximum"], 2)
        self.assertEqual(len(cont.storage.results), 5)

    def test_stateful_e2e_metric_is_serialized_across_concurrent_queries(self):
        class StatefulJudge(CustomMetric):
            busy = False
            def evaluate(self, query, answer):
                if self.busy:
                    raise RuntimeError("concurrent use of stateful judge")
                self.busy = True
                try:
                    time.sleep(0.01)
                    return Performance(score=1, metric="stateful judge")
                finally:
                    self.busy = False
        cont = RAGContainer("shared_e2e", [Output("output", is_starter=True)],
                            e2e_metrics=[StatefulJudge(["starter.query", "output.gen"])],
                            max_concurrency=4)
        FlowEngine([cont]).invoke_batch(["one", "two", "three", "four"])
        self.assertEqual(len(cont.storage.results), 4)
        self.assertTrue(all(state.performances[0].did_eval for state in cont.storage.results.values()))

    def test_e2e_cancellation_records_cancelled_instead_of_engine_error(self):
        started, release = threading.Event(), threading.Event()
        class Judge(CustomMetric):
            def evaluate(self, query, answer):
                started.set()
                release.wait(2)
                return Performance(score=1)
        cont = RAGContainer("cancel_e2e", [Output("output", is_starter=True)],
                            e2e_metrics=[Judge(["starter.query", "output.gen"])])
        async def scenario():
            task = asyncio.create_task(FlowEngine([cont]).async_invoke("q"))
            try:
                self.assertTrue(await asyncio.to_thread(started.wait, 1))
                task.cancel()
                with self.assertRaises(asyncio.CancelledError):
                    await task
            finally:
                release.set()
        asyncio.run(scenario())
        state = self.stored(cont)
        self.assertEqual(state.execution_summary["termination_reason"], "cancelled")
        self.assertFalse(state.execution_summary["success"])
        self.assertEqual(state.evaluation_summary["not_reached_e2e_metrics"], 1)

    def test_status_events_identify_queries_executions_and_failed_completion(self):
        from ragang.core.network.socket_sender import SocketSender
        events = []
        class Handler:
            async def broadcast(self, topic, payload):
                events.append((topic, payload))
        class Broken(CustomModule):
            async def execute(self, query):
                raise RuntimeError("synthetic failure")
        cont = RAGContainer("events", [Starter("starter", is_starter=True),
                                      Broken("broken", linker=Linker("starter"))])
        engine = FlowEngine([cont])
        engine.set_ws_sender(SocketSender(Handler()))
        with self.assertRaises(RuntimeError):
            engine.invoke("q")
        state = self.stored(cont)
        module_events = [p for topic, p in events if topic == "module-statu"]
        self.assertEqual([p["statu"] for p in module_events], ["running", "completed", "running", "failed"])
        self.assertEqual({p["query_id"] for p in module_events}, {state.q_id})
        self.assertEqual({p["run_id"] for p in module_events}, {state.run_metadata["run_id"]})
        self.assertEqual([p["execution_id"] for p in module_events], ["exec-1", "exec-1", "exec-2", "exec-2"])
        completions = [p for topic, p in events if topic == "ended-query"]
        self.assertEqual(len(completions), 1)
        self.assertEqual(completions[0]["status"], "failed")
        self.assertEqual(completions[0]["end-query"], state.q_id)
        self.assertEqual(completions[0]["run_id"], state.run_metadata["run_id"])

    def test_container_rejects_invalid_execution_limits(self):
        for value in [0, -1, True, float("inf"), float("nan"), "1"]:
            with self.subTest(timeout=value), self.assertRaises(ValueError):
                RAGContainer("bad", [Starter("starter", is_starter=True)], module_timeout_seconds=value)
        for value in [0, -1, True, 1.5]:
            with self.subTest(concurrency=value), self.assertRaises(ValueError):
                RAGContainer("bad", [Starter("starter", is_starter=True)], max_concurrency=value)
