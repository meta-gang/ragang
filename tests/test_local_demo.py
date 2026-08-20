from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import unittest
from unittest.mock import patch

from ragang.core.bases.abstracts.base_engine import FlowEngine


class LocalDemoTests(unittest.TestCase):
    def test_network_free_demo_executes_real_documents_and_metrics(self):
        project_root = Path(__file__).resolve().parents[1] / "examples" / "local_demo"
        spec = importlib.util.spec_from_file_location("ragang_local_demo_manager", project_root / "manager.py")
        module = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(module)

        with patch.dict(os.environ, {
            "RAGANG_DEMO_MODE": "focused",
            "RAGANG_DEMO_INCLUDE_NOT_EVALUATED": "0",
        }):
            engine = FlowEngine(module.containers())
        result = engine.invoke("What does RAGANG evaluate without a traditional gold dataset?")
        query_id = next(iter(result["local_demo"]))
        state = engine.get_result("local_demo", query_id)

        self.assertIn("RAGANG", state.gen)
        self.assertEqual(state.diagnosis["evaluator_health"]["evaluated"], 3)
        self.assertEqual(state.diagnosis["evaluator_health"]["not_evaluated"], 0)
        self.assertEqual(
            state.run_metadata["configuration"]["modules"][1]["settings"]["mode"],
            "focused",
        )
        metadata_text = json.dumps(state.run_metadata)
        self.assertNotIn("fermentation", metadata_text.lower())
        self.assertNotIn(str(project_root), metadata_text)

    def test_acceptance_probe_records_not_evaluated_without_changing_valid_scores(self):
        project_root = Path(__file__).resolve().parents[1] / "examples" / "local_demo"
        spec = importlib.util.spec_from_file_location("ragang_local_demo_probe", project_root / "manager.py")
        module = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(module)

        with patch.dict(os.environ, {
            "RAGANG_DEMO_MODE": "noisy",
            "RAGANG_DEMO_INCLUDE_NOT_EVALUATED": "1",
        }):
            engine = FlowEngine(module.containers())
        result = engine.invoke("What does RAGANG evaluate without a traditional gold dataset?")
        query_id = next(iter(result["local_demo"]))
        state = engine.get_result("local_demo", query_id)
        generation_performances = state.snapshots["generation"][0].performances
        probe = next(item for item in generation_performances if item.metric == "Unavailable evaluator probe")

        self.assertFalse(probe.did_eval)
        self.assertEqual(probe.failure["type"], "not_evaluated")
        self.assertEqual(state.diagnosis["evaluator_health"]["evaluated"], 3)
        self.assertEqual(state.diagnosis["evaluator_health"]["not_evaluated"], 1)


if __name__ == "__main__":
    unittest.main()
