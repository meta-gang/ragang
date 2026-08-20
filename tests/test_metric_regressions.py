from __future__ import annotations

import unittest

import numpy as np

from ragang.metrics.builtin.e2e.llm_based import (
    E2EQGenRelevancyMetric,
    E2EScoringRelevancyMetric,
    E2ESYNRelevancyMetric,
)
from ragang.metrics.builtin.e2e.non_llm_based import (
    AnswerQuerySimilarity,
    e2eCosineConsistencyMetric,
)
from ragang.metrics.builtin.generator.llm_based import (
    A2RHallucinationFaithfulnessMetric,
    A2RHybridFaithfulnessMetric,
    A2RSimpleScoringFaithfulnessMetric,
    A2RYNFaithfulnessMetric,
    A2RYNFaithfulnessMetricSingleCall,
)
from ragang.metrics.builtin.generator.non_llm_based import (
    AnswerContextSimilarity,
    MutualInformation_KSG,
    RetrievaltopkMeanAnswerSimilarity,
)
from ragang.metrics.builtin.retriever.llm_based import RandomDocumentInjectionEffect
from ragang.metrics.builtin.retriever.non_llm_based import (
    CosineSimilarityMetric,
    DiversityMetric,
    GeneralizedEmbeddingCoverageError,
    PairwiseCosineSimilarityVariance,
    PrecisionMetric,
)
from tests.fakes import (
    ConstantLLMAdapter,
    EmptyEmbeddingAdapter,
    MappingEmbeddingAdapter,
    SequenceLLMAdapter,
)


class MetricRegressionTests(unittest.TestCase):
    def test_metric_constructors_preserve_parameter_sources(self):
        precision = PrecisionMetric(["ret.docs", "gold.docs"])
        injection = RandomDocumentInjectionEffect(
            ["starter.query", "ret.docs", "gold.docs"],
            precision,
            llm_adapter=object(),
        )
        hybrid = A2RHybridFaithfulnessMetric(
            ["ret.docs", "output.gen"],
            llm_adapter=object(),
            embedding_adapter=object(),
        )

        self.assertEqual(precision.param_refs, ["ret.docs", "gold.docs"])
        self.assertEqual(len(injection.param_refs), 3)
        self.assertEqual(len(hybrid.param_refs), 2)

    def test_embedding_api_failures_are_not_evaluated(self):
        embedding = EmptyEmbeddingAdapter()
        results = [
            CosineSimilarityMetric(
                ["starter.query", "ret.docs"], embedding_adapter=embedding
            ).evaluate("query", ["doc"]),
            AnswerContextSimilarity(
                ["ret.docs", "output.gen"], embedding_adapter=embedding
            ).evaluate(["doc"], "answer"),
            AnswerQuerySimilarity(
                ["starter.query", "output.gen"], embedding_adapter=embedding
            ).evaluate("query", "answer"),
        ]
        self.assertTrue(all(not result.did_eval for result in results))

    def test_single_sample_metrics_are_not_evaluated(self):
        embedding = MappingEmbeddingAdapter()
        results = [
            RetrievaltopkMeanAnswerSimilarity(
                ["ret.docs", "output.gen", "starter.query"],
                embedding_adapter=embedding,
            ).evaluate(["doc-1"], "answer", "query"),
            PairwiseCosineSimilarityVariance(
                ["starter.query", "ret.docs"], embedding_adapter=embedding
            ).evaluate("query", ["doc-1"]),
            DiversityMetric(
                ["starter.query", "ret.docs"], embedding_adapter=embedding
            ).evaluate("query", ["doc-1"]),
            e2eCosineConsistencyMetric(
                ["starter.query", "output.gen"], embedding_adapter=embedding
            ).evaluate("query", "answer"),
        ]
        self.assertTrue(all(not result.did_eval for result in results))

    def test_empty_gece_is_not_evaluated_instead_of_infinite(self):
        result = GeneralizedEmbeddingCoverageError(
            ["starter.query", "ret.docs"], embedding_adapter=MappingEmbeddingAdapter()
        ).evaluate("query", [])
        self.assertFalse(result.did_eval)

    def test_precision_without_reference_documents_is_not_evaluated(self):
        result = PrecisionMetric(["ret.docs", "gold.docs"]).evaluate(["doc"], [])
        self.assertFalse(result.did_eval)

    def test_numbered_claim_parser_uses_only_the_final_verdict(self):
        metric = A2RYNFaithfulnessMetric(
            ["ret.docs", "output.gen"],
            llm_adapter=SequenceLLMAdapter(
                [
                    {"text": "1. claim"},
                    {"text": "Groundedness: Grounded\nGroundedness: Not Grounded"},
                ]
            ),
        )
        result = metric.evaluate(["doc"], "answer")
        self.assertTrue(result.did_eval)
        self.assertEqual(result.score, 0)

    def test_numbered_claim_parser_rejects_malformed_claims(self):
        metric = A2RYNFaithfulnessMetric(
            ["ret.docs", "output.gen"],
            llm_adapter=ConstantLLMAdapter({"text": "no numbered claims"}),
        )
        self.assertFalse(metric.evaluate(["doc"], "answer").did_eval)

    def test_all_llm_judge_parse_failures_are_not_evaluated(self):
        malformed = ConstantLLMAdapter({"text": "malformed"})
        empty_embedding = EmptyEmbeddingAdapter()
        results = [
            E2ESYNRelevancyMetric(
                ["starter.query", "output.gen"], llm_adapter=malformed
            ).evaluate("query", "answer"),
            E2EScoringRelevancyMetric(
                ["starter.query", "output.gen"], llm_adapter=malformed
            ).evaluate("query", "answer"),
            E2EQGenRelevancyMetric(
                ["starter.query", "output.gen"],
                llm_adapter=ConstantLLMAdapter({"error": "down"}),
                embedding_adapter=empty_embedding,
            ).evaluate("query", "answer"),
            A2RSimpleScoringFaithfulnessMetric(
                ["ret.docs", "output.gen"], llm_adapter=malformed
            ).evaluate(["doc"], "answer"),
            A2RHallucinationFaithfulnessMetric(
                ["starter.query", "ret.docs", "output.gen"], llm_adapter=malformed
            ).evaluate("query", ["doc"], "answer"),
            A2RYNFaithfulnessMetricSingleCall(
                ["ret.docs", "output.gen"], llm_adapter=malformed
            ).evaluate(["doc"], "answer"),
            A2RHybridFaithfulnessMetric(
                ["ret.docs", "output.gen"], llm_adapter=malformed
            ).evaluate(["doc"], "answer"),
        ]
        self.assertTrue(all(not result.did_eval for result in results))

    def test_random_document_injection_does_not_fabricate_on_llm_failure(self):
        precision = PrecisionMetric(["ret.docs", "gold.docs"])
        metric = RandomDocumentInjectionEffect(
            ["starter.query", "ret.docs", "gold.docs"],
            precision,
            llm_adapter=ConstantLLMAdapter({"error": "down"}),
        )
        self.assertFalse(metric.evaluate("query", ["answer"], ["answer"]).did_eval)

    def test_mutual_information_is_finite_and_rejects_one_chunk(self):
        metric = MutualInformation_KSG(
            ["ret.docs", "output.gen", "starter.query"],
            embedding_adapter=MappingEmbeddingAdapter(),
            k=2,
        )
        evaluated = metric.evaluate(["doc-1", "doc-2", "doc-3"], "answer", "query")
        insufficient = metric.evaluate(["doc-1"], "answer", "query")
        self.assertTrue(evaluated.did_eval)
        self.assertTrue(np.isfinite(evaluated.score))
        self.assertGreaterEqual(evaluated.score, 0)
        self.assertFalse(insufficient.did_eval)


if __name__ == "__main__":
    unittest.main()
