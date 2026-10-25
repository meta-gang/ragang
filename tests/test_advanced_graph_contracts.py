"""Combined graph/cycle contracts using deterministic, completely offline inputs."""

from contextlib import redirect_stdout
import copy
import importlib.util
import io
from pathlib import Path
import unittest
import warnings

from ragang.container import RAGContainer
from ragang.comparison import compare_runs
from ragang.core.bases.abstracts.base_engine import FlowEngine
from ragang.core.bases.datas.linker import Linker
from ragang.core.bases.datas.performance import Performance
from ragang.exceptions.frameworks.engine import FlowExecutionLimitException
from ragang.metrics.custom import CustomMetric
from ragang.modules.custom import CustomModule


class RoundInput(CustomModule):
    async def execute(self, query):
        return {"round": 0, "next": ["a", "b"]}


class RefreshA(CustomModule):
    async def execute(self, round):
        round += 1
        return {"round": round, "a": round, "next": ["a", "join"] if round == 1 else ["join"]}


class StaticB(CustomModule):
    async def execute(self, round):
        return {"b": 7}


class JoinValues(CustomModule):
    async def execute(self, a, b):
        return {"observed_a": a, "b": b}


class CollectTwo(CustomModule):
    async def execute(self, observed_a, b):
        if len(self.lazy_state.snapshots.get("collect", [])) == 1:
            return {"gen": str(observed_a)}
        return {"terminal": False, "next": []}


class BindingMatch(CustomMetric):
    def evaluate(self, source_value, observed_value):
        return Performance(score=int(source_value == observed_value), metric="Input binding match", unit="binary")


class AdvancedGraphContractTests(unittest.TestCase):
    def setUp(self):
        self.warning_context = warnings.catch_warnings()
        self.warning_context.__enter__()
        warnings.simplefilter("ignore", RuntimeWarning)

    def tearDown(self):
        self.warning_context.__exit__(None, None, None)

    @staticmethod
    def demo():
        path = Path(__file__).resolve().parents[1] / "examples/advanced_graph_demo/manager.py"
        spec = importlib.util.spec_from_file_location("advanced_graph_demo_manager", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    @staticmethod
    def state(cont):
        return next(iter(cont.storage.results.values()))

    def assert_trace_consistent(self, cont, state):
        seen = set()
        allowed_edges = set(cont.storage.flow_graph)
        for event in state.execution_trace:
            self.assertNotIn(event["execution_id"], seen)
            self.assertTrue(set(event["parent_execution_ids"]).issubset(seen))
            self.assertGreaterEqual(event["latency_seconds"], 0)
            for next_module in event["next_modules"]:
                self.assertIn((event["module_id"], next_module), allowed_edges)
            self.assertNotIn("input_values", event)
            self.assertNotIn("output_values", event)
            seen.add(event["execution_id"])
        self.assertEqual(state.execution_summary["total_executions"], len(seen))
        for module_id, packets in state.snapshots.items():
            events = [e for e in state.execution_trace if e["module_id"] == module_id]
            self.assertEqual(len(packets), len(events))
            self.assertEqual([p.execution_id for p in packets], [e["execution_id"] for e in events])

    def test_file_backed_linear_cycle_and_graph_module_examples_execute(self):
        expected_steps = {"linear": 3, "hybrid_cycle": 14, "graph_module": 3}
        for cont in self.demo().containers():
            with self.subTest(flow=cont.flow_id):
                FlowEngine([cont]).invoke("배포 점검 절차")
                state = self.state(cont)
                self.assertTrue(state.execution_summary["success"])
                self.assertEqual(len(state.execution_trace), expected_steps[cont.flow_id])
                self.assertIn("로컬 문서 발췌", state.gen)
                self.assert_trace_consistent(cont, state)

    def test_two_retriever_merge_draft_critic_rewrite_cycle_has_fresh_rounds(self):
        cont = next(c for c in self.demo().containers() if c.flow_id == "hybrid_cycle")
        FlowEngine([cont]).invoke("배포 점검 절차")
        state = self.state(cont)
        self.assertEqual([p.data["round_keyword"] for p in state.snapshots["keyword"]], [0, 1])
        self.assertEqual([p.data["round_graph"] for p in state.snapshots["graph_search"]], [0, 1])
        self.assertEqual([p.data["round"] for p in state.snapshots["merge"]], [0, 1])
        self.assertTrue(all(not p.is_answer for p in state.snapshots["draft"]))
        merges = [e for e in state.execution_trace if e["module_id"] == "merge"]
        self.assertEqual([e["parent_execution_ids"] for e in merges], [["exec-3", "exec-4"], ["exec-9", "exec-10"]])
        self.assertEqual(state.snapshots["draft"][1].performances[0].scope["input_execution_ids"],
                         {"merge.ret_docs": "exec-11", "draft.gen": "exec-12"})
        self.assertEqual(state.execution_trace[-1]["module_id"], "final")
        self.assertEqual(state.execution_summary["module_revisits"], 6)

    def test_combined_cycle_limit_preserves_all_attempted_steps_without_final_answer(self):
        cont = next(c for c in self.demo().containers() if c.flow_id == "hybrid_cycle")
        cont.max_steps = 10
        with self.assertRaises(FlowExecutionLimitException):
            FlowEngine([cont]).invoke("배포 점검 절차")
        state = self.state(cont)
        self.assertEqual(len(state.execution_trace), 10)
        self.assertEqual(state.execution_summary["termination_reason"], "max_steps")
        self.assertIsNone(state.gen)
        self.assertNotIn("final", state.snapshots)
        self.assert_trace_consistent(cont, state)

    def test_queued_join_metric_uses_its_parent_packet_not_future_global_latest(self):
        cont = RAGContainer("queued", [
            RoundInput("starter", is_starter=True),
            RefreshA("a", linker=Linker("starter") | Linker("a")),
            StaticB("b", linker=Linker("starter")),
            JoinValues("join", linker=Linker("a") & Linker("b"),
                       metrics=[BindingMatch(["a.a", "join.observed_a"])]),
            CollectTwo("collect", linker=Linker("join")),
        ])
        FlowEngine([cont]).invoke("q")
        state = self.state(cont)
        self.assertEqual([p.data["observed_a"] for p in state.snapshots["join"]], [1, 2])
        self.assertEqual([p.performances[0].score for p in state.snapshots["join"]], [1, 1])
        self.assertEqual([p.performances[0].scope["input_execution_ids"]["a.a"]
                          for p in state.snapshots["join"]], ["exec-2", "exec-4"])
        self.assertEqual(state.snapshots["join"][0].performances[0].evaluator["parameter_binding_version"],
                         "ancestry-first-v1")
        self.assert_trace_consistent(cont, state)

    def test_explicit_nonancestor_metric_reference_keeps_latest_access_and_records_source(self):
        class Input(CustomModule):
            async def execute(self, query):
                return {"query": query, "next": ["reference", "side"]}
        class Reference(CustomModule):
            async def execute(self, query):
                return {"value": 7, "next": []}
        class Side(CustomModule):
            async def execute(self, query):
                return {"query": query}
        class Output(CustomModule):
            async def execute(self, query):
                return {"gen": query}
        class Observe(CustomMetric):
            def evaluate(self, value):
                return Performance(score=value, metric="Observed reference value", unit="count")
        cont = RAGContainer("nonancestor", [Input("starter", is_starter=True),
                            Reference("reference", linker=Linker("starter")),
                            Side("side", linker=Linker("starter")),
                            Output("output", linker=Linker("side"), metrics=[Observe(["reference.value"])])])
        FlowEngine([cont]).invoke("q")
        state = self.state(cont)
        performance = state.snapshots["output"][0].performances[0]
        self.assertEqual(performance.score, 7)
        self.assertEqual(performance.scope["input_execution_ids"], {"reference.value": "exec-2"})
        self.assertEqual(state.execution_trace[-1]["parent_execution_ids"], ["exec-3"])

    def test_retry_predecessor_wins_regardless_of_or_linker_declaration_order(self):
        class Input(CustomModule):
            async def execute(self, query):
                return {"round": 0}
        class Loop(CustomModule):
            async def execute(self, round):
                return {"round": round + 1, "next": ["loop" if round < 1 else "out"]}
        class Final(CustomModule):
            async def execute(self, round):
                return {"gen": str(round)}
        for reverse in [False, True]:
            linker = Linker("loop") | Linker("starter") if reverse else Linker("starter") | Linker("loop")
            cont = RAGContainer("order", [Input("starter", is_starter=True), Loop("loop", linker=linker),
                                          Final("out", linker=Linker("loop"))], max_steps=5)
            FlowEngine([cont]).invoke("q")
            state = self.state(cont)
            self.assertEqual(state.gen, "2")
            self.assertEqual([p.data["round"] for p in state.snapshots["loop"]], [1, 2])
            self.assertEqual(state.execution_trace[2]["parent_execution_ids"], ["exec-1", "exec-2"])

    def test_two_independent_cycles_can_converge_before_and_merge(self):
        class BranchInput(CustomModule):
            async def execute(self, query):
                return {"a_round": 0, "b_round": 0, "next": ["a", "b"]}
        class CycleA(CustomModule):
            async def execute(self, a_round):
                a_round += 1
                return {"a_round": a_round, "next": ["a" if a_round < 2 else "join"]}
        class CycleB(CustomModule):
            async def execute(self, b_round):
                b_round += 1
                return {"b_round": b_round, "next": ["b" if b_round < 3 else "join"]}
        class Join(CustomModule):
            async def execute(self, a_round, b_round):
                return {"gen": f"{a_round},{b_round}"}
        cont = RAGContainer("independent", [
            BranchInput("starter", is_starter=True),
            CycleA("a", linker=Linker("a") | Linker("starter")),
            CycleB("b", linker=Linker("b") | Linker("starter")),
            Join("join", linker=Linker("a") & Linker("b")),
        ], max_steps=10)
        FlowEngine([cont]).invoke("q")
        state = self.state(cont)
        self.assertEqual(state.gen, "2,3")
        self.assertEqual(len(state.snapshots["join"]), 1)
        self.assertEqual(len(state.execution_trace), 7)
        self.assertEqual(state.execution_trace[-1]["parent_execution_ids"], ["exec-4", "exec-6"])
        self.assert_trace_consistent(cont, state)

    def test_independent_refreshes_have_explicit_combine_latest_and_semantics(self):
        class RefreshB(CustomModule):
            async def execute(self, round):
                round += 1
                return {"round": round, "b": round, "next": ["b", "join"] if round == 1 else ["join"]}
        class CollectThree(CustomModule):
            async def execute(self, observed_a, b):
                if len(self.lazy_state.snapshots.get("collect", [])) == 2:
                    return {"gen": f"{observed_a},{b}"}
                return {"next": [], "terminal": False}
        cont = RAGContainer("latest", [
            RoundInput("starter", is_starter=True),
            RefreshA("a", linker=Linker("starter") | Linker("a")),
            RefreshB("b", linker=Linker("starter") | Linker("b")),
            JoinValues("join", linker=Linker("a") & Linker("b")),
            CollectThree("collect", linker=Linker("join")),
        ], max_steps=15)
        FlowEngine([cont]).invoke("q")
        state = self.state(cont)
        pairs = [(p.data["observed_a"], p.data["b"]) for p in state.snapshots["join"]]
        self.assertEqual(pairs, [(1, 1), (2, 1), (2, 2)])
        join_parents = [tuple(e["parent_execution_ids"]) for e in state.execution_trace if e["module_id"] == "join"]
        self.assertEqual(len(join_parents), len(set(join_parents)))
        self.assertEqual(state.gen, "2,2")
        self.assert_trace_consistent(cont, state)

    def test_child_in_place_changes_do_not_modify_upstream_or_sibling_input(self):
        class Docs(CustomModule):
            async def execute(self, query):
                return {"ret_docs": ["original"], "next": ["mutate", "observe"]}
        class Mutate(CustomModule):
            async def execute(self, ret_docs):
                ret_docs.append("changed")
                return {"ret_docs": ret_docs, "next": []}
        class Observe(CustomModule):
            async def execute(self, ret_docs):
                return {"gen": ",".join(ret_docs)}
        cont = RAGContainer("immutable", [Docs("starter", is_starter=True),
                            Mutate("mutate", linker=Linker("starter")), Observe("observe", linker=Linker("starter"))])
        FlowEngine([cont]).invoke("q")
        state = self.state(cont)
        self.assertEqual(state.snapshots["starter"][0].data["ret_docs"], ["original"])
        self.assertEqual(state.snapshots["mutate"][0].data["ret_docs"], ["original", "changed"])
        self.assertEqual(state.gen, "original")

    def test_reused_adapter_output_buffer_cannot_rewrite_previous_snapshots(self):
        buffer = []
        class Input(CustomModule):
            async def execute(self, query):
                return {"round": 0}
        class Producer(CustomModule):
            async def execute(self, round):
                round += 1
                buffer[:] = [round]
                return {"round": round, "ret_docs": buffer, "next": ["producer" if round < 2 else "out"]}
        class Final(CustomModule):
            async def execute(self, ret_docs):
                return {"gen": str(ret_docs[0])}
        cont = RAGContainer("buffer", [Input("starter", is_starter=True),
                            Producer("producer", linker=Linker("starter") | Linker("producer")),
                            Final("out", linker=Linker("producer"))])
        FlowEngine([cont]).invoke("q")
        state = self.state(cont)
        self.assertEqual([p.data["ret_docs"] for p in state.snapshots["producer"]], [[1], [2]])
        self.assertEqual(state.gen, "2")

    def test_graph_retriever_records_actual_bounded_traversal_without_claiming_kg_accuracy(self):
        cont = next(c for c in self.demo().containers() if c.flow_id == "graph_module")
        FlowEngine([cont]).invoke("배포 점검 절차")
        state = self.state(cont)
        packet = state.snapshots["graph_search"][0]
        self.assertEqual(packet.data["retrieved_node_ids"], ["deployment", "operations", "rollback"])
        self.assertEqual(packet.data["traversed_edges"], [["deployment", "operations"], ["operations", "rollback"]])
        self.assertEqual(packet.performances[0].score, 3)
        self.assertEqual(packet.performances[0].unit, "documents")
        self.assertNotIn("kg_accuracy", packet.data)
        self.assertEqual(state.execution_trace[1]["output_keys"], sorted(packet.data))

    def test_binding_version_change_blocks_a_numeric_comparison(self):
        # Use a real evaluated demo score and emulate its documented old binding descriptor.
        demo = next(c for c in self.demo().containers() if c.flow_id == "linear")
        FlowEngine([demo]).invoke("배포 점검 절차")
        current = self.state(demo).serialize()
        previous = copy.deepcopy(current)
        for packets in previous["snapshots"].values():
            for packet in packets:
                for performance in packet["performances"]:
                    descriptor = performance["_Performance__evaluator"]
                    descriptor.pop("parameter_binding_version", None)
                    descriptor["fingerprint"] = "legacy-binding"
        report = compare_runs({"before": previous}, {"after": current})
        self.assertTrue(report["metrics"])
        self.assertTrue(all(row["delta"] is None for row in report["metrics"]))
        self.assertTrue(all("evaluator_configuration_mismatch" in row["comparison_notes"] for row in report["metrics"]))

    def test_cli_default_output_uses_question_numbers_without_query_identifiers(self):
        cont = next(c for c in self.demo().containers() if c.flow_id == "linear")
        FlowEngine([cont]).invoke("배포 점검 절차")
        state = self.state(cont)
        output = io.StringIO()
        with redirect_stdout(output):
            cont.print_eval()
        self.assertIn("질문 1: 배포 점검 절차", output.getvalue())
        self.assertNotIn(state.q_id, output.getvalue())
