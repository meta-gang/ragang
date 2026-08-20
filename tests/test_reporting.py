from __future__ import annotations

import json
import io
import unittest
from contextlib import redirect_stdout
from types import SimpleNamespace
from unittest.mock import patch

from ragang.comparison import compare_runs, summarize_run
from ragang.container import RAGContainer
from ragang.core.bases.abstracts.base_engine import FlowEngine
from ragang.core.bases.abstracts.base_metric import BaseMetric
from ragang.core.bases.datas.linker import Linker
from ragang.core.bases.datas.performance import Performance
from ragang.diagnostics import diagnose_state
from ragang.cli_script.compare.main import run as run_compare
from ragang.modules.custom import CustomModule


class Starter(CustomModule):
    async def execute(self, query: str):
        return {"query": query}


class Output(CustomModule):
    async def execute(self, query: str):
        return {"gen": f"answer:{query}"}


class SecretAdapter:
    def __init__(self):
        self.model_name = "judge-model"
        self.api_key = "must-never-be-serialized"
        self.headers = {"Authorization": "Bearer must-never-be-serialized"}


class ContentBearingModule(Output):
    def __init__(self, module_id: str, linker: Linker):
        super().__init__(module_id, linker=linker)
        self.top_k = 4
        self.documents = ["private document body"]
        self.prompt_template = "private prompt body"
        self.cache_path = "/private/local/cache"


class ExplodingJudgeMetric(BaseMetric):
    def __init__(self, param_src: list[str]):
        super().__init__(param_src)
        self.llm_adapter = SecretAdapter()

    def evaluate(self, value: str) -> Performance:
        raise ValueError("judge parse failed")


def _performance(metric: str, score: float | None, did_eval: bool, failure_type: str | None = None):
    return Performance(
        score=0 if score is None else score,
        metric=metric,
        _eval=did_eval,
        failure={"type": failure_type, "message": "failed"} if failure_type else None,
    ).serialize()


def _state(*, score: float | None, did_eval: bool, latency: float, fingerprint: str, empty_docs: bool = False):
    return {
        "query": "question",
        "gen": "answer",
        "run_metadata": {"config_fingerprint": fingerprint},
        "snapshots": {
            "ret": [
                {
                    "data": {"ret_docs": [] if empty_docs else ["document"]},
                    "performances": [_performance("Context quality", score, did_eval, "parse_error" if not did_eval else None)],
                    "x_time": latency,
                }
            ],
        },
        "performances": [_performance("Answer quality", score, did_eval)],
    }


class ReportingTests(unittest.TestCase):
    def test_metric_summary_reports_coverage_range_and_variation(self):
        states = {
            "q1": _state(score=20, did_eval=True, latency=0.1, fingerprint="same"),
            "q2": _state(score=40, did_eval=True, latency=0.1, fingerprint="same"),
            "q3": _state(score=None, did_eval=False, latency=0.1, fingerprint="same"),
        }

        summary = summarize_run(states)
        context = next(
            value for key, value in summary["metrics"].items()
            if key[2] == "Context quality"
        )

        self.assertEqual(context["evaluated"], 2)
        self.assertEqual(context["not_evaluated"], 1)
        self.assertAlmostEqual(context["coverage"], 2 / 3)
        self.assertEqual(context["minimum"], 20)
        self.assertEqual(context["maximum"], 40)
        self.assertEqual(context["population_stddev"], 10)

    def test_engine_attaches_safe_evaluator_provenance_and_failure(self):
        metric = ExplodingJudgeMetric(["output.gen"])
        container = RAGContainer(
            "health",
            [
                Starter("starter", is_starter=True),
                Output("output", linker=Linker("starter"), metrics=[metric]),
            ],
        )
        engine = FlowEngine([container])

        result = engine.invoke("hello")
        query_id = next(iter(result["health"]))
        state = engine.get_result("health", query_id)
        performance = state.snapshots["output"][0].performances[0]
        serialized = state.serialize()
        serialized_text = json.dumps(serialized)

        self.assertFalse(performance.did_eval)
        self.assertEqual(performance.failure["type"], "ValueError")
        self.assertEqual(performance.evaluator["adapters"][0]["model"], "judge-model")
        self.assertIn("implementation_fingerprint", performance.evaluator)
        self.assertNotIn("must-never-be-serialized", serialized_text)
        self.assertIn("config_fingerprint", serialized["run_metadata"])
        self.assertIn("evaluator_health", serialized["diagnosis"])

    def test_config_fingerprint_is_deterministic_for_same_flow(self):
        def make_container():
            return RAGContainer(
                "same",
                [Starter("starter", is_starter=True), Output("output", linker=Linker("starter"))],
            )

        first = FlowEngine([make_container()])
        second = FlowEngine([make_container()])
        first_result = first.invoke("one")
        second_result = second.invoke("two")
        first_id = next(iter(first_result["same"]))
        second_id = next(iter(second_result["same"]))

        self.assertEqual(
            first.get_result("same", first_id).run_metadata["config_fingerprint"],
            second.get_result("same", second_id).run_metadata["config_fingerprint"],
        )

    def test_config_fingerprint_changes_with_public_module_setting(self):
        first_container = RAGContainer(
            "setting",
            [Starter("starter", is_starter=True), Output("output", linker=Linker("starter"))],
        )
        second_container = RAGContainer(
            "setting",
            [Starter("starter", is_starter=True), Output("output", linker=Linker("starter"))],
        )
        first_container.modules["output"].top_k = 1
        second_container.modules["output"].top_k = 2

        first = FlowEngine([first_container]).run_metadata["setting"]
        second = FlowEngine([second_container]).run_metadata["setting"]

        self.assertNotEqual(first["config_fingerprint"], second["config_fingerprint"])

    def test_run_metadata_excludes_content_and_local_paths(self):
        container = RAGContainer(
            "bounded",
            [
                Starter("starter", is_starter=True),
                ContentBearingModule("output", linker=Linker("starter")),
            ],
        )

        metadata = FlowEngine([container]).run_metadata["bounded"]
        serialized = json.dumps(metadata)
        output_settings = metadata["configuration"]["modules"][1]["settings"]

        self.assertEqual(output_settings["top_k"], 4)
        self.assertNotIn("private document body", serialized)
        self.assertNotIn("private prompt body", serialized)
        self.assertNotIn("/private/local/cache", serialized)

    def test_diagnosis_separates_observations_from_inferences(self):
        report = diagnose_state(_state(
            score=None,
            did_eval=False,
            latency=0.2,
            fingerprint="same",
            empty_docs=True,
        ))

        observation_codes = {item["code"] for item in report["observations"]}
        inference_codes = {item["code"] for item in report["inferences"]}
        self.assertIn("retrieval.empty", observation_codes)
        self.assertIn("evaluator.not_evaluated", observation_codes)
        self.assertIn("answer_without_retrieved_evidence", inference_codes)
        self.assertTrue(all("confidence" in item for item in report["inferences"]))

    def test_compare_runs_uses_only_evaluated_common_metrics(self):
        baseline = {
            "q1": _state(score=40, did_eval=True, latency=0.4, fingerprint="baseline"),
            "q2": _state(score=None, did_eval=False, latency=0.2, fingerprint="baseline"),
        }
        candidate = {
            "q1": _state(score=60, did_eval=True, latency=0.2, fingerprint="candidate"),
            "q2": _state(score=80, did_eval=True, latency=0.2, fingerprint="candidate"),
        }

        report = compare_runs(baseline, candidate)
        context_metric = next(item for item in report["metrics"] if item["metric"] == "Context quality")

        self.assertEqual(context_metric["baseline"]["evaluated"], 1)
        self.assertEqual(context_metric["candidate"]["evaluated"], 2)
        self.assertEqual(context_metric["delta"], 30.0)
        self.assertEqual(report["evaluator_health"]["baseline"]["not_evaluated"], 2)
        self.assertEqual(report["evaluator_health"]["candidate"]["not_evaluated"], 0)
        self.assertAlmostEqual(report["latency_seconds"]["baseline_mean"], 0.3)
        self.assertAlmostEqual(report["latency_seconds"]["candidate_mean"], 0.2)
        self.assertFalse(report["configuration"]["match"])
        self.assertTrue(report["warnings"])

    def test_compare_cli_defaults_to_latest_two_runs(self):
        history = {
            "260101000000": {"q": _state(score=20, did_eval=True, latency=0.3, fingerprint="same")},
            "260102000000": {"q": _state(score=30, did_eval=True, latency=0.2, fingerprint="same")},
            "260103000000": {"q": _state(score=40, did_eval=True, latency=0.1, fingerprint="same")},
        }
        args = SimpleNamespace(
            flow_id="flow",
            baseline=None,
            candidate=None,
            json_output=True,
        )
        output = io.StringIO()

        with patch("ragang.cli_script.compare.main.get_history", return_value=history), redirect_stdout(output):
            report = run_compare(args)

        self.assertEqual(report["baseline_run"], "260102000000")
        self.assertEqual(report["candidate_run"], "260103000000")
        self.assertTrue(report["configuration"]["match"])
        self.assertIn('"candidate_run": "260103000000"', output.getvalue())

    def test_summarize_multi_runs_aggregates_trials_and_computes_variance(self):
        from ragang.comparison import summarize_multi_runs

        run1 = {
            "q1": _state(score=80.0, did_eval=True, latency=0.2, fingerprint="fp1"),
            "q2": _state(score=90.0, did_eval=True, latency=0.4, fingerprint="fp1"),
        }
        run2 = {
            "q1": _state(score=85.0, did_eval=True, latency=0.3, fingerprint="fp1"),
            "q2": _state(score=95.0, did_eval=True, latency=0.3, fingerprint="fp1"),
        }
        run3 = {
            "q1": _state(score=75.0, did_eval=True, latency=0.2, fingerprint="fp1"),
            "q2": _state(score=85.0, did_eval=True, latency=0.4, fingerprint="fp1"),
        }

        report = summarize_multi_runs([run1, run2, run3])

        self.assertEqual(report["trial_count"], 3)
        self.assertEqual(report["total_queries"], 6)
        self.assertTrue(report["configuration"]["consistent"])
        self.assertEqual(report["configuration"]["fingerprints"], ["fp1"])
        self.assertEqual(len(report["warnings"]), 0)

        # Check aggregated metrics
        context_m = next(m for m in report["metrics"] if m["metric"] == "Context quality")
        self.assertEqual(context_m["evaluated"], 6)
        self.assertEqual(context_m["not_evaluated"], 0)
        self.assertEqual(context_m["coverage"], 1.0)
        self.assertEqual(len(context_m["trial_means"]), 3)
        self.assertAlmostEqual(context_m["mean"], 85.0)  # (85.0 + 90.0 + 80.0) / 3
        self.assertIsNotNone(context_m["between_run_stddev"])
        self.assertAlmostEqual(context_m["min_trial_mean"], 80.0)
        self.assertAlmostEqual(context_m["max_trial_mean"], 90.0)

    def test_summarize_multi_runs_flags_inconsistent_fingerprints(self):
        from ragang.comparison import summarize_multi_runs

        run1 = {"q1": _state(score=80.0, did_eval=True, latency=0.2, fingerprint="fp_a")}
        run2 = {"q1": _state(score=85.0, did_eval=True, latency=0.3, fingerprint="fp_b")}

        report = summarize_multi_runs([run1, run2])
        self.assertFalse(report["configuration"]["consistent"])
        self.assertEqual(report["configuration"]["fingerprints"], ["fp_a", "fp_b"])
        self.assertTrue(len(report["warnings"]) > 0)


if __name__ == "__main__":
    unittest.main()
