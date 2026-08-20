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

    def test_status_cycle_search_terminates_when_target_is_absent(self):
        status = Status([("a", "b"), ("b", "a")])
        self.assertIsNone(status.find_loop_before_mid("a", ["not-in-graph"]))


if __name__ == "__main__":
    unittest.main()
