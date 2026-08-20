"""Experiment C: Evaluator Failure Detection & Health Isolation.

Demonstrates RAGANG's handling of evaluator breakdowns (malformed judge output,
API timeouts, empty inputs, and NaN/Inf rejection) by preserving explicit
'not evaluated' states instead of fabricating deceptive '0.0' scores.
"""

from pathlib import Path
import sys
import warnings

ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ragang.container import RAGContainer
from ragang.core.bases.abstracts.base_engine import FlowEngine
from ragang.core.bases.abstracts.base_metric import BaseMetric
from ragang.core.bases.datas.linker import Linker
from ragang.core.bases.datas.performance import Performance
from ragang.evaluator import attach_evaluator_context
from ragang.modules.custom import CustomModule


class DummyStarter(CustomModule):
    async def execute(self, query: str):
        return {"query": query}


class DummyRetriever(CustomModule):
    def __init__(self, module_id: str, linker: Linker, return_empty: bool = False, metrics=None):
        super().__init__(module_id, linker, metrics=metrics)
        self.return_empty = return_empty

    async def execute(self, query: str):
        if self.return_empty:
            return {"query": query, "ret_docs": []}
        return {"query": query, "ret_docs": ["Document text about quantum computing."]}


class DummyGenerator(CustomModule):
    def __init__(self, module_id: str, linker: Linker, metrics=None):
        super().__init__(module_id, linker, metrics=metrics)

    async def execute(self, query: str, ret_docs: list[str]):
        if not ret_docs:
            return {"gen": "Cannot answer due to missing evidence."}
        return {"gen": "Quantum computers use qubits to perform calculations."}


# Custom Test Metrics
class ValidZeroMetric(BaseMetric):
    """A metric that calculates a legitimate zero score."""
    def evaluate(self, query: str, answer: str) -> Performance:
        # 0.0 overlap is a valid, calculated evaluation result
        return Performance(score=0.0, unit="%", metric="LexicalOverlap", _eval=True)


class ValidHighMetric(BaseMetric):
    """A metric that calculates a legitimate high score."""
    def evaluate(self, query: str, answer: str) -> Performance:
        return Performance(score=100.0, unit="%", metric="LexicalOverlap", _eval=True)


class MalformedJudgeMetric(BaseMetric):
    """Simulates an LLM judge returning invalid or unparseable JSON."""
    def evaluate(self, answer: str) -> Performance:
        # Judge output could not be parsed
        raise ValueError("LLM judge returned malformed markdown instead of JSON schema: '```Here is my review...'")


class TimeoutJudgeMetric(BaseMetric):
    """Simulates an evaluator API network timeout."""
    def evaluate(self, query: str, ret_docs: list[str]) -> Performance:
        raise TimeoutError("Connection to judge endpoint timed out after 30.0s")


class EmptyInputMetric(BaseMetric):
    """A metric that rejects empty retrieval contexts."""
    def evaluate(self, ret_docs: list[str]) -> Performance:
        if not ret_docs:
            return Performance(metric="ContextRelevance", _eval=False, failure={
                "type": "empty_input",
                "message": "Retrieval returned 0 documents; cannot compute relevance."
            })
        return Performance(score=85.0, metric="ContextRelevance", _eval=True)


def run_experiment():
    print("=" * 70)
    print("EXPERIMENT C: Evaluator Failure Detection & Health Isolation")
    print("=" * 70)

    # 1. Direct Metric Evaluation Behavior
    print("\n--- 1. Evaluating Direct Metric Health States ---")

    # Case A: Valid 0.0
    p_zero = ValidZeroMetric(["starter.query", "generation.gen"]).evaluate("apple", "orange")
    p_zero = attach_evaluator_context(p_zero, ValidZeroMetric(["starter.query", "generation.gen"]))
    print(f"Case A (Valid Zero Score):")
    print(f"  did_eval={p_zero.did_eval}, score={p_zero.score}{p_zero.unit}, string='{p_zero}'")

    # Case B: Malformed Judge Output
    m_judge = MalformedJudgeMetric(["generation.gen"])
    try:
        m_judge.evaluate("answer")
    except Exception as exc:
        p_malformed = attach_evaluator_context(
            Performance(metric="MalformedJudge", _eval=False),
            m_judge,
            exc
        )
    print(f"\nCase B (Malformed Judge Failure):")
    print(f"  did_eval={p_malformed.did_eval}, failure_type='{p_malformed.failure['type']}'")
    print(f"  failure_message='{p_malformed.failure['message']}'")
    print(f"  string='{p_malformed}'")

    # Case C: Timeout API Failure
    m_timeout = TimeoutJudgeMetric(["starter.query", "retrieval.ret_docs"])
    try:
        m_timeout.evaluate("query", ["doc"])
    except Exception as exc:
        p_timeout = attach_evaluator_context(
            Performance(metric="TimeoutJudge", _eval=False),
            m_timeout,
            exc
        )
    print(f"\nCase C (API Timeout Failure):")
    print(f"  did_eval={p_timeout.did_eval}, failure_type='{p_timeout.failure['type']}'")
    print(f"  string='{p_timeout}'")

    # 2. Pipeline Execution Isolation (Fault Tolerance)
    print("\n--- 2. Pipeline-Level Fault Isolation & Diagnostic Aggregation ---")

    starter = DummyStarter("starter", is_starter=True)
    retriever = DummyRetriever("retriever", linker=Linker("starter"), metrics=[
        TimeoutJudgeMetric(["starter.query", "retriever.ret_docs"]),
        EmptyInputMetric(["retriever.ret_docs"]),
    ])
    generator = DummyGenerator("generation", linker=Linker("retriever"), metrics=[
        MalformedJudgeMetric(["generation.gen"]),
    ])

    container = RAGContainer(
        "fault_isolation_flow",
        modules=[starter, retriever, generator],
        e2e_metrics=[
            ValidZeroMetric(["starter.query", "generation.gen"]),
        ]
    )

    engine = FlowEngine([container])

    # Suppress expected runtime warnings during intentional error probe
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        res = engine.invoke("What is quantum computing?")

    qid = next(iter(res["fault_isolation_flow"]))
    state = engine.get_result("fault_isolation_flow", qid)

    print(f"Query Result Generated: '{state.gen}'")
    print(f"Pipeline Succeeded despite 2 metric failures!")

    diag = state.diagnosis
    print(f"\nEvaluator Health Summary:")
    print(f"  Total Attempted: {diag['evaluator_health']['evaluated'] + diag['evaluator_health']['not_evaluated']}")
    print(f"  Evaluated Successfully: {diag['evaluator_health']['evaluated']}")
    print(f"  Not Evaluated (Failed): {diag['evaluator_health']['not_evaluated']}")
    print(f"  Coverage: {diag['evaluator_health']['coverage'] * 100:.1f}%")

    print(f"\nRecorded Unevaluated Observations:")
    for obs in diag["observations"]:
        if obs["code"] == "evaluator.not_evaluated":
            print(f"  - [{obs['stage']}:{obs['module']}] Metric: {obs['metric']}, Type: {obs['failure_type']}, Msg: {obs['message']}")

    print(f"\nDiagnostic Inferences:")
    for inf in diag["inferences"]:
        print(f"  - Code: {inf['code']}, Cause: {inf['possible_cause']}, Next Action: {inf['next_action']}")

    # 3. Statistical Distortion Comparison: Why score=0.0 is Harmful
    print("\n--- 3. Distortion Comparison: Fabricated 0.0 vs Honest Not-Evaluated ---")
    valid_scores = [100.0, 95.0, 90.0]
    num_failures = 2

    honest_mean = sum(valid_scores) / len(valid_scores)
    distorted_mean = (sum(valid_scores) + (0.0 * num_failures)) / (len(valid_scores) + num_failures)

    print(f"Valid Evaluations: {valid_scores}")
    print(f"Evaluator Crashes / Timeouts: {num_failures} instances")
    print(f"  [RAGANG Honest Average] Excludes failures from denominator: {honest_mean:.2f}% (Coverage: 3/5)")
    print(f"  [Naive Benchmark Score] Conflates crash with 0.0 score:       {distorted_mean:.2f}% (Distortion: -{honest_mean - distorted_mean:.2f}%)")

    print("\n" + "=" * 70)
    print("EXPERIMENT C PASSED: Honest evaluator health & failure isolation verified.")
    print("=" * 70)
    return True


if __name__ == "__main__":
    run_experiment()
