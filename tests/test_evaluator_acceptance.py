"""Offline acceptance cases for evaluator trust and paired comparisons."""
from __future__ import annotations

import json
import unittest

from ragang.comparison import compare_runs, summarize_run
from ragang.counterfactual import compare_counterfactual_runs
from ragang.core.bases.datas.performance import Performance
from ragang.diagnostics import diagnose_state
from ragang.evaluator import evaluator_provenance
from ragang.metrics.builtin.generator.llm_based import (
    A2RHybridFaithfulnessMetric, A2RYNFaithfulnessMetricSingleCall,
    A2RYNFaithfulnessMetric, A2RSimpleScoringFaithfulnessMetric,
    A2RTruthfulFaithfulnessMetric, A2RHallucinationFaithfulnessMetric,
)
from tests.fakes import ConstantLLMAdapter, SequenceLLMAdapter


def metric(response):
    return A2RYNFaithfulnessMetricSingleCall(
        ["ret.docs", "output.gen"], llm_adapter=ConstantLLMAdapter({"text": response}))


def state(query, score, *, evaluated=True, evaluator=None, sample_id=None):
    p = Performance(score, unit="0 to 1", metric="Grounding", _eval=evaluated,
                    evaluator=evaluator).serialize()
    result = {"query": query, "gen": "answer", "snapshots": {}, "performances": [p],
              "run_metadata": {"config_fingerprint": "same"}}
    if sample_id is not None:
        result["sample_id"] = sample_id
    return result


class JudgeAcceptanceTests(unittest.TestCase):
    def test_schema_defects_are_not_numeric_fallbacks(self):
        defects = [
            [{"claim": "c"}], [{"claim": "c", "grounded": "true"}],
            [{"claim": "c", "grounded": 1}], [{"grounded": True}],
            [{"claim": "", "grounded": True}], [{"claim": None, "grounded": True}],
            [1], [{"claim": "c", "grounded": True}] * 2,
            {"claim": "c", "grounded": True}, [],
        ]
        for value in defects:
            with self.subTest(value=value):
                result = metric(json.dumps(value)).evaluate(["document"], "answer")
                self.assertFalse(result.did_eval)
                self.assertEqual(result.failure["type"], "invalid_judge_output")

    def test_valid_false_stays_zero_and_retains_scope_and_evidence(self):
        result = metric('[{"claim":"unsupported claim","grounded":false,"reason":"No supporting source.","source_document_indices":[]}]').evaluate(
            ["doc"] * 6, "answer" * 400)
        self.assertTrue(result.did_eval)
        self.assertEqual(result.score, 0)
        self.assertEqual(result.scope["documents_evaluated"], 5)
        self.assertTrue(result.scope["documents_truncated"])
        self.assertEqual(result.scope["answer_chars_evaluated"], 2000)
        self.assertTrue(result.scope["answer_truncated"])
        self.assertEqual(result.evidence[0]["claim_id"], "claim-1")
        self.assertFalse(result.evidence[0]["source_attribution_verified"])
        self.assertEqual(result.metric_version, "2")

    def test_complete_fenced_json_handles_brackets_in_claims(self):
        result = metric('```json\n[{"claim":"array [one] has a bracket","grounded":true}]\n```').evaluate(["doc"], "answer")
        self.assertTrue(result.did_eval)
        self.assertEqual(result.score, 1)
        self.assertFalse(metric('prose [{"claim":"c","grounded":true}]').evaluate(["doc"], "answer").did_eval)

    def test_invalid_sources_fail_validation(self):
        for indices in ([True], [-1], [1], [0, 0], "0"):
            with self.subTest(indices=indices):
                result = metric(json.dumps([{"claim": "c", "grounded": True,
                                             "source_document_indices": indices}])).evaluate(["doc"], "answer")
                self.assertFalse(result.did_eval)

    def test_empty_and_unsupported_inputs_do_not_call_judge(self):
        class MustNotCall:
            def request(self, *args):
                raise AssertionError("Invalid input reached judge")
        for cls in (A2RYNFaithfulnessMetricSingleCall, A2RHybridFaithfulnessMetric,
                    A2RYNFaithfulnessMetric, A2RSimpleScoringFaithfulnessMetric,
                    A2RTruthfulFaithfulnessMetric):
            judge = cls(["ret.docs", "output.gen"], llm_adapter=MustNotCall())
            for docs, answer in (([], "answer"), (["doc"], ""), ([""], "answer"), ("doc", "answer"), ([1], "answer")):
                with self.subTest(cls=cls.__name__, docs=docs):
                    self.assertFalse(judge.evaluate(docs, answer).did_eval)
        judge = A2RHallucinationFaithfulnessMetric(["starter.query", "ret.docs", "output.gen"], llm_adapter=MustNotCall())
        self.assertFalse(judge.evaluate("query", [], "answer").did_eval)

    def test_adapter_failure_type_survives_without_response_body(self):
        result = A2RYNFaithfulnessMetricSingleCall(["ret.docs", "out.gen"],
            llm_adapter=ConstantLLMAdapter({"error": "ReadTimeout", "body": "private-content"})).evaluate(["doc"], "answer")
        self.assertFalse(result.did_eval)
        self.assertEqual(result.failure["type"], "ReadTimeout")
        self.assertNotIn("private-content", json.dumps(result.serialize()))

    def test_hybrid_rejects_replaced_duplicated_and_missing_claims(self):
        for verdicts in ([{"claim": "different", "grounded": True}],
                         [{"claim": "first", "grounded": True}] * 2,
                         [{"claim": "first", "grounded": "true"}], []):
            with self.subTest(verdicts=verdicts):
                judge = A2RHybridFaithfulnessMetric(["ret.docs", "out.gen"], llm_adapter=SequenceLLMAdapter([
                    {"text": '["first"]'}, {"text": json.dumps(verdicts)}]))
                result = judge.evaluate(["doc"], "answer")
                self.assertFalse(result.did_eval)
                self.assertEqual(result.failure["type"], "invalid_judge_output")

    def test_hybrid_reorders_valid_exact_claims_and_keeps_all_batches(self):
        judge = A2RHybridFaithfulnessMetric(["ret.docs", "out.gen"], claims_batch_size=2,
            llm_adapter=SequenceLLMAdapter([
                {"text": '["first","second","third"]'},
                {"text": '[{"claim":"second","grounded":false},{"claim":"first","grounded":true}]'},
                {"text": '[{"claim":"third","grounded":true}]'},
            ]))
        result = judge.evaluate(["doc"], "answer")
        self.assertTrue(result.did_eval)
        self.assertAlmostEqual(result.score, 2 / 3)
        self.assertEqual([e["claim"] for e in result.evidence], ["first", "second", "third"])
        self.assertEqual([e["claim_id"] for e in result.evidence], ["claim-1", "claim-2", "claim-3"])

    def test_hybrid_partial_batch_failure_is_not_a_partial_numeric_score(self):
        judge = A2RHybridFaithfulnessMetric(["ret.docs", "out.gen"], claims_batch_size=1,
            llm_adapter=SequenceLLMAdapter([
                {"text": '["first","second"]'},
                {"text": '[{"claim":"first","grounded":true}]'}, {"error": "TimeoutError"}]))
        result = judge.evaluate(["doc"], "answer")
        self.assertFalse(result.did_eval)
        self.assertEqual(result.failure["type"], "TimeoutError")

    def test_invalid_limits_and_claim_extraction_are_rejected(self):
        for value in (0, -1, True):
            with self.subTest(value=value):
                self.assertFalse(metric('[{"claim":"c","grounded":true}]').evaluate(["doc"], "answer", max_docs=value).did_eval)
                with self.assertRaises(ValueError):
                    A2RHybridFaithfulnessMetric(["ret.docs", "out.gen"], claims_batch_size=value)
        for claims in ('["first",42]', '["first","first"]', '[" "]'):
            judge = A2RHybridFaithfulnessMetric(["ret.docs", "out.gen"], llm_adapter=ConstantLLMAdapter({"text": claims}))
            self.assertFalse(judge.evaluate(["doc"], "answer").did_eval)

    def test_duplicate_json_field_names_are_not_silently_overwritten(self):
        result = metric('[{"claim":"c","grounded":false,"grounded":true}]').evaluate(["doc"], "answer")
        self.assertFalse(result.did_eval)
        self.assertEqual(result.failure["type"], "invalid_judge_output")

    def test_text_metric_input_contract_is_checked_before_adapter_calls(self):
        from ragang.metrics.builtin.retriever.non_llm_based import KeywordMatchingMetric, CosineSimilarityMetric, PrecisionMetric
        from ragang.metrics.builtin.generator.non_llm_based import AnswerContextSimilarity
        from ragang.metrics.builtin.e2e.non_llm_based import AnswerQuerySimilarity, e2eCosineConsistencyMetric
        from ragang.metrics.builtin.e2e.llm_based import E2ESYNRelevancyMetric
        class MustNotCall:
            def request(self, *args):
                raise AssertionError("Invalid input reached judge")
            def create_embeddings(self, *args):
                raise AssertionError("Invalid input reached embeddings")
        adapter = MustNotCall()
        examples = [
            (KeywordMatchingMetric(["q.text", "r.docs"]), ("   ", ["doc"])),
            (KeywordMatchingMetric(["q.text", "r.docs"]), ("query", [" "])),
            (CosineSimilarityMetric(["q.text", "r.docs"], embedding_adapter=adapter), ("query", "single document")),
            (PrecisionMetric(["r.docs", "g.docs"]), (["doc"], [""])),
            (AnswerContextSimilarity(["r.docs", "o.gen"], embedding_adapter=adapter), (["doc"], "")),
            (AnswerQuerySimilarity(["q.text", "o.gen"], embedding_adapter=adapter), (None, "answer")),
            (e2eCosineConsistencyMetric(["q.text", "o.gen"], embedding_adapter=adapter), (None, ["first", " "])),
            (E2ESYNRelevancyMetric(["q.text", "o.gen"], llm_adapter=adapter), ("", "answer")),
        ]
        for judge, inputs in examples:
            with self.subTest(metric=type(judge).__name__, inputs=inputs):
                result = judge.evaluate(*inputs)
                self.assertFalse(result.did_eval)
                self.assertEqual(result.failure["type"], "invalid_metric_input")
        zero = KeywordMatchingMetric(["q.text", "r.docs"]).evaluate("absent", ["different"])
        self.assertTrue(zero.did_eval)
        self.assertEqual(zero.score, 0)


class PairedComparisonAcceptanceTests(unittest.TestCase):
    def test_unrelated_questions_never_produce_delta(self):
        report = compare_runs({"a": state("hard query", .1)}, {"b": state("easy query", .9)})
        self.assertEqual(report["pairing"]["paired_query_count"], 0)
        self.assertIsNone(report["metrics"][0]["delta"])
        self.assertTrue(report["warnings"])
        self.assertNotIn("hard query", json.dumps(report))

    def test_only_common_valid_pairs_contribute_to_delta(self):
        report = compare_runs({"a": state("one", .4), "b": state("two", 0, evaluated=False)},
                              {"c": state("one", .6), "d": state("two", .8)})
        result = report["metrics"][0]
        self.assertEqual(result["delta"], .2)
        self.assertEqual(result["paired"]["evaluated"], 1)
        self.assertEqual(result["paired"]["coverage"], .5)
        self.assertIn("incomplete_paired_evaluation", result["comparison_notes"])

    def test_changed_evaluator_blocks_delta_even_when_labels_match(self):
        report = compare_runs({"a": state("q", .1, evaluator={"model": "old"})},
                              {"b": state("q", .9, evaluator={"model": "new"})})
        self.assertIsNone(report["metrics"][0]["delta"])
        self.assertFalse(report["metrics"][0]["comparable"])
        self.assertIn("evaluator_configuration_mismatch", report["metrics"][0]["comparison_notes"])

    def test_stable_sample_id_content_change_is_not_a_pair(self):
        report = compare_runs({"a": state("old", .1, sample_id="sample")},
                              {"b": state("changed", .9, sample_id="sample")})
        self.assertEqual(report["pairing"]["sample_id_content_mismatches"], 1)
        self.assertIsNone(report["metrics"][0]["delta"])

    def test_counterfactual_delta_uses_actual_common_pairs(self):
        report = compare_counterfactual_runs(
            {"a": state("same", .1), "x": state("removed", 0)},
            {"b": state("same", .2), "y": state("added", 1)},
            perturbation={"kind": "retrieval_shuffle"})
        self.assertEqual(report["counterfactual"]["paired_query_count"], 1)
        self.assertEqual(report["metrics"][0]["delta"], .1)

    def test_final_query_mean_is_separate_from_execution_mean(self):
        low = state("low", 0)
        high = state("high", 1)
        low["snapshots"] = {"ret": [{"performances": low["performances"], "x_time": 0}] * 9}
        high["snapshots"] = {"ret": [{"performances": high["performances"], "x_time": 0}]}
        low["performances"] = high["performances"] = []
        result = summarize_run({"a": low, "b": high})["metrics"][("module", "ret", "Grounding", "0 to 1")]
        self.assertEqual(result["mean"], .1)
        self.assertEqual(result["query_final_mean"], .5)
        self.assertEqual(result["evaluated"], 10)
        self.assertEqual(result["query_final_evaluated"], 2)

    def test_imported_invalid_flags_and_mixed_evaluators_are_not_averaged(self):
        first, second = state("q1", .1, evaluator={"model": "one"}), state("q2", .9, evaluator={"model": "two"})
        result = summarize_run({"a": first, "b": second})
        self.assertIsNone(next(iter(result["metrics"].values()))["mean"])
        first["performances"][0]["_Performance__did_eval"] = "false"
        self.assertEqual(summarize_run({"a": first})["evaluator_health"]["evaluated"], 0)

    def test_duplicate_explicit_sample_ids_are_excluded(self):
        report = compare_runs({"a": state("same", .1, sample_id="duplicate"),
                               "b": state("same", .2, sample_id="duplicate")},
                              {"c": state("same", .9, sample_id="duplicate")})
        self.assertEqual(report["pairing"]["duplicate_sample_ids"], 1)
        self.assertIsNone(report["metrics"][0]["delta"])


class ProvenanceAndDiagnosisAcceptanceTests(unittest.TestCase):
    def test_explicit_versions_and_adapter_decoding_change_identity_without_content(self):
        first, second = metric("[]"), metric("[]")
        first.prompt, second.prompt = "private text A", "private text B"
        first.prompt_version, second.prompt_version = "one", "two"
        self.assertNotEqual(evaluator_provenance(first)["fingerprint"], evaluator_provenance(second)["fingerprint"])
        text = json.dumps(evaluator_provenance(first))
        self.assertNotIn("private text A", text)
        first.llm_adapter.temperature = 0
        before = evaluator_provenance(first)["fingerprint"]
        first.llm_adapter.temperature = .5
        self.assertNotEqual(before, evaluator_provenance(first)["fingerprint"])

    def test_stateless_and_raising_adapter_properties_do_not_break_provenance(self):
        class SlotAdapter:
            __slots__ = ()
            @property
            def model_name(self):
                raise ValueError("unavailable")
        judge = metric("[]")
        judge.llm_adapter = SlotAdapter()
        self.assertIn("fingerprint", evaluator_provenance(judge))

    def test_non_boolean_evaluation_flags_are_isolated_by_engine(self):
        from ragang.container import RAGContainer
        from ragang.core.bases.abstracts.base_engine import FlowEngine
        from ragang.core.bases.abstracts.base_metric import BaseMetric
        from ragang.core.bases.datas.linker import Linker
        from tests.test_core_regressions import Starter, Output
        class InvalidFlagMetric(BaseMetric):
            def __init__(self, flag):
                super().__init__(["output.gen"])
                self.flag = flag
            def evaluate(self, answer):
                return Performance(score=1, _eval=self.flag)
        for flag in ("false", 1, None):
            with self.subTest(flag=flag):
                container = RAGContainer("flag", [Starter("starter", is_starter=True),
                    Output("output", linker=Linker("starter"), metrics=[InvalidFlagMetric(flag)])])
                engine = FlowEngine([container])
                result = engine.invoke("q")
                query_id = next(iter(result["flag"]))
                performance = engine.get_result("flag", query_id).snapshots["output"][0].performances[0]
                self.assertIs(performance.did_eval, False)
                self.assertEqual(performance.failure["type"], "ValueError")

    def test_invalid_metric_metadata_is_isolated_before_serialization(self):
        from ragang.container import RAGContainer
        from ragang.core.bases.abstracts.base_engine import FlowEngine
        from ragang.core.bases.abstracts.base_metric import BaseMetric
        from ragang.core.bases.datas.linker import Linker
        from tests.test_core_regressions import Starter, Output
        class InvalidMetadataMetric(BaseMetric):
            def __init__(self, metadata):
                super().__init__(["output.gen"])
                self.metadata = metadata
            def evaluate(self, answer):
                return Performance(score=1, **self.metadata)
        cases = [
            {"metric": {}}, {"metric": " "}, {"unit": {}},
            {"direction": []}, {"direction": " "}, {"metric_version": 2},
            {"evidence": {}}, {"evidence": [True]}, {"scope": []},
            {"scope": {"unsupported": object()}}, {"evaluator": []},
            {"failure": {"type": []}},
        ]
        for metadata in cases:
            with self.subTest(fields=list(metadata)):
                container = RAGContainer("metadata", [Starter("starter", is_starter=True),
                    Output("output", linker=Linker("starter"), metrics=[InvalidMetadataMetric(metadata)])])
                engine = FlowEngine([container])
                result = engine.invoke("q")
                query_id = next(iter(result["metadata"]))
                saved = engine.get_result("metadata", query_id)
                performance = saved.snapshots["output"][0].performances[0]
                self.assertIs(performance.did_eval, False)
                self.assertEqual(performance.failure["type"], "ValueError")
                json.dumps(saved.serialize())

    def test_unitless_legacy_metadata_remains_valid(self):
        from ragang.evaluator import attach_evaluator_context
        value = attach_evaluator_context(Performance(score=0, metric="Unitless", unit=""), metric("[]"))
        self.assertTrue(value.did_eval)
        self.assertEqual(value.score, 0)
        self.assertEqual(value.unit, "")

    def test_imported_malformed_metadata_is_not_evaluated_or_averaged(self):
        malformed = [
            {"metric": {}, "unit": {}, "did_eval": True, "score": 1},
            {"metric": "score", "unit": "", "did_eval": True, "score": 1, "failure": {"type": []}},
            {"metric": "score", "unit": "", "did_eval": True, "score": 1, "scope": []},
            {"metric": "score", "unit": "", "did_eval": True, "score": 1, "evaluator": []},
        ]
        payload = {"query": "q", "snapshots": {}, "performances": malformed}
        summary = summarize_run({"q": payload})
        self.assertEqual(summary["evaluator_health"]["evaluated"], 0)
        self.assertEqual(summary["evaluator_health"]["not_evaluated"], 4)
        self.assertEqual(summary["evaluator_health"]["failure_types"], {"invalid_performance_metadata": 4})
        self.assertTrue(all(value["mean"] is None for value in summary["metrics"].values()))
        comparison = compare_runs({"q": payload}, {"q": payload})
        self.assertTrue(all(value["delta"] is None for value in comparison["metrics"]))
        diagnosis = diagnose_state(payload)
        self.assertEqual(diagnosis["evaluator_health"]["evaluated"], 0)
        self.assertTrue(all(item["failure_type"] == "invalid_performance_metadata"
                            for item in diagnosis["observations"]))
        json.dumps(comparison)

    def test_imported_unrepresentable_score_is_not_a_finite_evaluation(self):
        payload = {"query": "q", "snapshots": {}, "performances": [
            {"metric": "Huge", "unit": "", "did_eval": True, "score": 10 ** 1000}]}
        self.assertEqual(summarize_run({"q": payload})["evaluator_health"]["evaluated"], 0)
        self.assertEqual(diagnose_state(payload)["evaluator_health"]["evaluated"], 0)

    def test_cyclic_metadata_is_rejected_before_serialization(self):
        from ragang.evaluator import attach_evaluator_context
        scope = {}
        scope["cycle"] = scope
        with self.assertRaisesRegex(ValueError, "scope"):
            attach_evaluator_context(Performance(score=1, scope=scope), metric("[]"))

    def test_retry_keeps_empty_observation_without_false_final_evidence_inference(self):
        payload = {"query": "q", "gen": "answer", "performances": [],
                   "snapshots": {"ret": [{"data": {"ret_docs": []}}, {"data": {"ret_docs": ["evidence"]}}],
                                 "out": [{"data": {"gen": "answer"}}]},
                   "execution_trace": [
                       {"execution_id": "one", "module_id": "ret", "execution_index": 1, "status": "completed"},
                       {"execution_id": "two", "module_id": "ret", "execution_index": 2, "status": "completed", "parent_execution_ids": ["one"]},
                       {"execution_id": "three", "module_id": "out", "execution_index": 1, "status": "completed", "parent_execution_ids": ["two"], "output_keys": ["gen"]},
                   ]}
        report = diagnose_state(payload)
        self.assertIn("retrieval.empty", {item["code"] for item in report["observations"]})
        self.assertNotIn("answer_without_retrieved_evidence", {item["code"] for item in report["inferences"]})


if __name__ == "__main__":
    unittest.main()
