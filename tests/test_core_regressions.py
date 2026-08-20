from __future__ import annotations

import asyncio
import math
import unittest
import warnings

from ragang.container import RAGContainer
from ragang.core.bases.abstracts.base_engine import FlowEngine
from ragang.core.bases.abstracts.base_metric import BaseMetric
from ragang.core.bases.datas.linker import Linker
from ragang.core.bases.datas.performance import Performance
from ragang.core.bases.datas.status import Status
from ragang.exceptions.user.module import (
    DependencyConnectionException,
    DuplicateModuleIdException,
)
from ragang.exceptions.frameworks.engine import FlowExecutionLimitException
from ragang.exceptions.user.structure import RagangStructureException
from ragang.modules.custom import CustomModule


class Starter(CustomModule):
    async def execute(self, query: str):
        return {"query": query}


class PassThrough(CustomModule):
    async def execute(self, query: str):
        return {"query": query}


class Output(CustomModule):
    async def execute(self, query: str):
        return {"gen": f"answer:{query}"}


class Branch(CustomModule):
    async def execute(self, query: str):
        return {"left": query, "right": query}


class Left(CustomModule):
    async def execute(self, left: str):
        return {"left": f"{left}:left"}


class Right(CustomModule):
    async def execute(self, right: str):
        return {"right": f"{right}:right"}


class Merge(CustomModule):
    async def execute(self, left: str, right: str):
        return {"query": f"{left}|{right}"}


class Conditional(CustomModule):
    async def execute(self, query: str):
        destination = "positive" if query.startswith("yes") else "negative"
        return {"next": [destination], "query": query}


class ExplodingMetric(BaseMetric):
    def evaluate(self, value: str) -> Performance:
        raise ValueError("judge parse failed")


class ScoreMetric(BaseMetric):
    def __init__(self, param_src: list[str], score):
        super().__init__(param_src)
        self.result_score = score

    def evaluate(self, value: str) -> Performance:
        return Performance(score=self.result_score, metric="score")


class Rewrite(CustomModule):
    async def execute(self, query: str):
        return {"query": f"{query}:rewrite"}


class Critic(CustomModule):
    async def execute(self, query: str):
        destination = "output" if query.count(":rewrite") >= 2 else "rewrite"
        return {"next": [destination], "query": query}


class Forever(CustomModule):
    async def execute(self, query: str):
        return {"query": query}


class ExplodingModule(CustomModule):
    async def execute(self, query: str):
        raise RuntimeError("retriever unavailable")


class CoreRegressionTests(unittest.TestCase):
    def test_linker_operators_do_not_pollute_each_other(self):
        and_dep = (Linker("a") & Linker("b")).build("target-a")
        or_dep = (Linker("c") | Linker("d")).build("target-b")

        self.assertFalse(and_dep.is_or)
        self.assertTrue(or_dep.is_or)
        with self.assertRaises(DependencyConnectionException):
            Linker("e") | (Linker("f") & Linker("g"))

    def test_module_with_no_metrics_serializes(self):
        module = Starter("starter", metrics=None, is_starter=True)
        self.assertEqual(module.to_dict()["metrics"], [])

    def test_container_requires_exactly_one_starter(self):
        with self.assertRaisesRegex(RagangStructureException, "no starter"):
            RAGContainer("missing", [Starter("module")])

    def test_duplicate_module_error_names_the_duplicate(self):
        with self.assertRaisesRegex(DuplicateModuleIdException, "duplicate"):
            RAGContainer(
                "duplicate",
                [Starter("duplicate", is_starter=True), Starter("duplicate")],
            )

    def test_linear_graph_executes_end_to_end(self):
        container = RAGContainer(
            "linear",
            [
                Starter("starter", is_starter=True),
                PassThrough("middle", linker=Linker("starter")),
                Output("output", linker=Linker("middle")),
            ],
        )
        result = FlowEngine([container]).invoke("hello")
        answer = next(iter(result["linear"].values()))["answer"]
        self.assertEqual(answer, "answer:hello")

    def test_and_merge_graph_waits_for_both_branches(self):
        container = RAGContainer(
            "merge",
            [
                Starter("starter", is_starter=True),
                Branch("branch", linker=Linker("starter")),
                Left("left", linker=Linker("branch")),
                Right("right", linker=Linker("branch")),
                Merge("merge", linker=Linker("left") & Linker("right")),
                Output("output", linker=Linker("merge")),
            ],
        )
        result = FlowEngine([container]).invoke("hello")
        answer = next(iter(result["merge"].values()))["answer"]
        self.assertEqual(answer, "answer:hello:left|hello:right")

    def test_conditional_graph_executes_only_selected_branch(self):
        container = RAGContainer(
            "conditional",
            [
                Starter("starter", is_starter=True),
                Conditional("conditional", linker=Linker("starter")),
                Output("positive", linker=Linker("conditional")),
                Output("negative", linker=Linker("conditional")),
            ],
        )
        engine = FlowEngine([container])
        result = engine.invoke("yes please")
        qid = next(iter(result["conditional"]))
        state = engine.get_result("conditional", qid)
        self.assertIn("positive", state.snapshots)
        self.assertNotIn("negative", state.snapshots)

    def test_metric_exception_becomes_explicit_not_evaluated_result(self):
        container = RAGContainer(
            "metric-error",
            [
                Starter("starter", is_starter=True),
                Output(
                    "output",
                    linker=Linker("starter"),
                    metrics=[ExplodingMetric(["output.gen"])],
                ),
            ],
        )
        engine = FlowEngine([container])

        result = engine.invoke("hello")
        qid = next(iter(result["metric-error"]))
        performance = engine.get_result("metric-error", qid).snapshots["output"][0].performances[0]
        self.assertFalse(performance.did_eval)

    def test_valid_zero_score_remains_evaluated(self):
        container = RAGContainer(
            "zero-score",
            [
                Starter("starter", is_starter=True),
                Output(
                    "output",
                    linker=Linker("starter"),
                    metrics=[ScoreMetric(["output.gen"], 0.0)],
                ),
            ],
        )
        engine = FlowEngine([container])

        result = engine.invoke("hello")
        qid = next(iter(result["zero-score"]))
        performance = engine.get_result("zero-score", qid).snapshots["output"][0].performances[0]

        self.assertTrue(performance.did_eval)
        self.assertEqual(performance.score, 0.0)

    def test_non_finite_evaluated_score_becomes_not_evaluated(self):
        container = RAGContainer(
            "nan-score",
            [
                Starter("starter", is_starter=True),
                Output(
                    "output",
                    linker=Linker("starter"),
                    metrics=[ScoreMetric(["output.gen"], math.nan)],
                ),
            ],
        )
        engine = FlowEngine([container])

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            result = engine.invoke("hello")
        qid = next(iter(result["nan-score"]))
        state = engine.get_result("nan-score", qid)
        performance = state.snapshots["output"][0].performances[0]

        self.assertFalse(performance.did_eval)
        self.assertEqual(performance.failure["type"], "ValueError")
        self.assertEqual(state.diagnosis["evaluator_health"]["coverage"], 0.0)

    def test_self_corrective_cycle_executes_and_records_parentage(self):
        container = RAGContainer(
            "cycle",
            [
                Starter("starter", is_starter=True),
                Rewrite("rewrite", linker=Linker("starter") | Linker("critic")),
                Critic("critic", linker=Linker("rewrite")),
                Output("output", linker=Linker("critic")),
            ],
            max_steps=10,
        )
        engine = FlowEngine([container])

        result = engine.invoke("hello")
        qid = next(iter(result["cycle"]))
        state = engine.get_result("cycle", qid)

        self.assertEqual(
            [event["module_id"] for event in state.execution_trace],
            ["starter", "rewrite", "critic", "rewrite", "critic", "output"],
        )
        self.assertEqual(state.execution_trace[3]["execution_index"], 2)
        self.assertEqual(state.execution_trace[3]["parent_execution_ids"], ["exec-1", "exec-3"])
        self.assertEqual(state.execution_summary["module_revisits"], 2)
        self.assertTrue(state.diagnosis["graph_health"]["cycle_or_retry_observed"])

    def test_max_steps_terminates_non_converging_cycle_and_preserves_state(self):
        container = RAGContainer(
            "bounded-cycle",
            [
                Starter("starter", is_starter=True),
                Forever("forever", linker=Linker("starter") | Linker("forever")),
            ],
            max_steps=3,
        )
        engine = FlowEngine([container])

        with self.assertRaises(FlowExecutionLimitException):
            engine.invoke("hello")

        state = next(iter(container.storage.results.values()))
        self.assertEqual(state.execution_summary["total_executions"], 3)
        self.assertEqual(state.execution_summary["termination_reason"], "max_steps")
        self.assertTrue(state.execution_summary["terminated"])
        self.assertIn(
            "graph.max_steps_reached",
            {item["code"] for item in state.diagnosis["observations"]},
        )

    def test_module_failure_records_failed_node_and_causal_path(self):
        container = RAGContainer(
            "failed-trace",
            [
                Starter("starter", is_starter=True),
                ExplodingModule("retriever", linker=Linker("starter")),
            ],
        )
        engine = FlowEngine([container])

        with self.assertRaisesRegex(RuntimeError, "retriever unavailable"):
            engine.invoke("hello")

        state = next(iter(container.storage.results.values()))
        failed = state.execution_trace[-1]
        observation = next(
            item for item in state.diagnosis["observations"]
            if item["code"] == "graph.execution_failed"
        )
        self.assertEqual(failed["status"], "failed")
        self.assertEqual(failed["parent_execution_ids"], ["exec-1"])
        self.assertEqual(observation["path"], ["starter#1", "retriever#1"])

    def test_batch_keeps_successes_but_raises_when_every_query_fails(self):
        engine = object.__new__(FlowEngine)
        engine.ws_sender = None
        engine.containers = {"flow": object()}

        async def fake_run_query(query: str, flow_id: str):
            if query == "bad":
                raise RuntimeError("boom")
            return {flow_id: {query: {"query": query, "answer": "ok"}}}

        engine._FlowEngine__run_query = fake_run_query
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            mixed = asyncio.run(engine._FlowEngine__run_container("flow", ["good", "bad"]))
            self.assertIn("good", mixed["flow"])
            self.assertNotIn("bad", mixed["flow"])
            with self.assertRaisesRegex(RuntimeError, "boom"):
                asyncio.run(engine._FlowEngine__run_container("flow", ["bad"]))

    def test_non_finite_scores_serialize_to_strict_json_values(self):
        self.assertIsNone(Performance(score=math.nan).serialize()["_Performance__score"])
        self.assertIsNone(Performance(score=math.inf).serialize()["_Performance__score"])

    def test_performance_text_separates_named_units_and_preserves_metric_identity(self):
        self.assertEqual(str(Performance(score=0.25, unit="0 to 1", metric="ACS")), "ACS: 0.25 0 to 1")
        self.assertEqual(str(Performance(score=25, unit="%", metric="Coverage")), "Coverage: 25.00%")
        self.assertEqual(
            str(Performance(score=0, unit="0 to 1", metric="Faithfulness", _eval=False)),
            "Faithfulness: not evaluated",
        )

    def test_status_cycle_search_terminates_when_target_is_absent(self):
        status = Status([("a", "b"), ("b", "a")])
        self.assertIsNone(status.find_loop_before_mid("a", ["not-in-graph"]))

    def test_status_optimization_terminates_on_existing_cycle(self):
        status = Status([("a", "b"), ("b", "a")])
        status.x_status = [("a", "b"), ("b", "a")]

        status.optimize_n_add_xs([("a", "b")])

        self.assertEqual(status.x_status, [("a", "b")])

    def test_container_rejects_invalid_max_steps(self):
        with self.assertRaisesRegex(ValueError, "positive integer"):
            RAGContainer("invalid-limit", [Starter("starter", is_starter=True)], max_steps=0)


if __name__ == "__main__":
    unittest.main()
