import importlib.util
from pathlib import Path
import unittest
from unittest.mock import MagicMock, patch


class LiveDemoTests(unittest.TestCase):
    def test_collection_setup_retries_until_milvus_is_ready(self):
        project_root = Path(__file__).resolve().parents[1] / "examples" / "live_ollama_milvus"
        spec = importlib.util.spec_from_file_location("ragang_live_demo_retry", project_root / "manager.py")
        module = importlib.util.module_from_spec(spec)
        assert spec.loader is not None

        with patch("ragang.adapters.milvus_adapter.MilvusAdapter") as adapter_class:
            adapter = MagicMock()
            adapter_class.return_value = adapter
            spec.loader.exec_module(module)

        adapter.has_collection.return_value = False
        adapter.create_collection.side_effect = [None, object()]
        adapter.insert.return_value = object()

        module.prepare_collection(timeout_seconds=1, retry_interval_seconds=0)

        self.assertEqual(adapter.create_collection.call_count, 2)
        adapter.insert.assert_called_once()
        adapter.create_index.assert_called_once_with("ragang_live_demo")


if __name__ == "__main__":
    unittest.main()
