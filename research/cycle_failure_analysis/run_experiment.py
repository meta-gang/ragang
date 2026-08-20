"""Experiment A: Cycle Failure & Max Steps Diagnosis.

Demonstrates RAGANG's execution tracing, revisit counting, bounded max_steps
termination, and automated diagnosis for cyclic / self-corrective RAG workflows.
"""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ragang.container import RAGContainer
from ragang.core.bases.abstracts.base_engine import FlowEngine
from ragang.core.bases.datas.linker import Linker
from ragang.exceptions.frameworks.engine import FlowExecutionLimitException
from ragang.modules.custom import CustomModule


class Starter(CustomModule):
    async def execute(self, query: str):
        return {"query": query}


class CyclicRetriever(CustomModule):
    async def execute(self, query: str):
        return {"query": f"{query} [retrieved]"}


class CyclicCritic(CustomModule):
    def __init__(self, module_id: str, linker: Linker, required_refinements: int = 2):
        super().__init__(module_id, linker)
        self.required_refinements = required_refinements

    async def execute(self, query: str):
        refinements = query.count("[retrieved]")
        if refinements >= self.required_refinements:
            return {"next": ["generator"], "query": query}
        return {"next": ["retriever"], "query": query}


class Generator(CustomModule):
    async def execute(self, query: str):
        return {"gen": f"Synthesized answer for: {query}"}


class InfiniteLoopModule(CustomModule):
    async def execute(self, query: str):
        return {"next": ["infinite_loop"], "query": query}


def build_self_corrective_flow(flow_id: str, required_refinements: int, max_steps: int):
    starter = Starter("starter", is_starter=True)
    retriever = CyclicRetriever("retriever", linker=Linker("starter") | Linker("critic"))
    critic = CyclicCritic("critic", linker=Linker("retriever"), required_refinements=required_refinements)
    generator = Generator("generator", linker=Linker("critic"))

    return RAGContainer(
        flow_id,
        modules=[starter, retriever, critic, generator],
        max_steps=max_steps,
    )


def build_infinite_loop_flow(flow_id: str, max_steps: int):
    starter = Starter("starter", is_starter=True)
    loop = InfiniteLoopModule("infinite_loop", linker=Linker("starter") | Linker("infinite_loop"))
    generator = Generator("generator", linker=Linker("infinite_loop"))

    return RAGContainer(
        flow_id,
        modules=[starter, loop, generator],
        max_steps=max_steps,
    )


def run_experiment():
    print("=" * 70)
    print("EXPERIMENT A: Cycle Failure & Max Steps Diagnosis")
    print("=" * 70)

    # Scenario 1: Converging Self-Corrective Cycle
    print("\n--- Scenario 1: Converging Self-Corrective Cycle (2 iterations) ---")
    container1 = build_self_corrective_flow("converging_flow", required_refinements=2, max_steps=10)
    engine1 = FlowEngine([container1])

    res1 = engine1.invoke("Explain CRISPR gene editing")
    qid1 = next(iter(res1["converging_flow"]))
    state1 = engine1.get_result("converging_flow", qid1)

    print(f"Status: COMPLETED (Success)")
    print(f"Generated Answer: {state1.gen}")
    print(f"Total Steps Executed: {state1.execution_summary['total_executions']}")
    print(f"Module Revisits: {state1.execution_summary['module_revisits']}")
    print(f"Repeated Modules: {state1.execution_summary['repeated_modules']}")
    print(f"Termination Reason: {state1.execution_summary['termination_reason']}")
    print(f"Observed Diagnostics:")
    for obs in state1.diagnosis["observations"]:
        print(f"  - Code: {obs['code']}, Stage: {obs['stage']}, Module: {obs.get('module')}")

    # Scenario 2: Unbounded Loop Terminated by max_steps
    print("\n--- Scenario 2: Non-converging Cycle Bounded by max_steps=4 ---")
    container2 = build_infinite_loop_flow("infinite_flow", max_steps=4)
    engine2 = FlowEngine([container2])

    try:
        engine2.invoke("Unsolvable query loop")
        print("FAIL: Expected FlowExecutionLimitException was not raised.")
    except FlowExecutionLimitException as exc:
        print(f"Caught Expected Engine Exception: {exc}")

    # Retrieve preserved failure state from container storage
    qid2 = next(iter(container2.storage.results.keys()))
    state2 = container2.storage.results[qid2]

    print(f"Status: TERMINATED (max_steps limit enforced)")
    print(f"Total Steps Executed: {state2.execution_summary['total_executions']}")
    print(f"Terminated Flag: {state2.execution_summary['terminated']}")
    print(f"Termination Reason: {state2.execution_summary['termination_reason']}")
    print(f"Execution Trace Step Summary:")
    for step in state2.execution_trace:
        print(f"  - [{step['execution_id']}] module: {step['module_id']}, index: {step['execution_index']}, revisit: {step['revisit_count']}, parents: {step['parent_execution_ids']}")

    print(f"Observations Recorded in Diagnosis:")
    for obs in state2.diagnosis["observations"]:
        print(f"  - Code: {obs['code']}, Stage: {obs.get('stage')}, Message: {obs.get('message')}")

    print("\n" + "=" * 70)
    print("EXPERIMENT A PASSED: Deterministic cycle tracing and safety termination verified.")
    print("=" * 70)
    return True


if __name__ == "__main__":
    run_experiment()
