from __future__ import annotations

import asyncio
import io
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

import httpx
import requests

from ragang.adapters.embedding_adapter import GeminiEmbeddingAdapter
from ragang.adapters.llm_adapter import GeminiAdapter, OllamaLocalLLMAdapter


class AdapterSafetyTests(unittest.TestCase):
    def test_sync_gemini_failure_does_not_expose_url_query_or_print(self):
        marker = "sensitive" + "-marker"
        adapter = GeminiAdapter("model", marker)
        error = requests.exceptions.ConnectionError(
            f"failed https://example.invalid?key={marker}"
        )
        output = io.StringIO()

        with patch("ragang.adapters.llm_adapter.requests.post", side_effect=error), redirect_stdout(output):
            result = adapter.request("prompt", "query")

        self.assertEqual(result, {"error": "ConnectionError"})
        self.assertNotIn(marker, str(result))
        self.assertEqual(output.getvalue(), "")

    def test_async_http_error_keeps_only_type_and_status(self):
        marker = "sensitive" + "-marker"
        adapter = GeminiAdapter("model", marker)
        request = httpx.Request("POST", f"https://example.invalid?key={marker}")
        response = httpx.Response(401, text=f"body {marker}", request=request)

        class Client:
            async def post(self, *args, **kwargs):
                return response

        result = asyncio.run(adapter.request_async(Client(), "prompt", "query"))

        self.assertEqual(result, {"error": "HTTPStatusError", "status_code": 401})
        self.assertNotIn(marker, str(result))

    def test_embedding_failure_is_silent_and_returns_empty_array(self):
        marker = "sensitive" + "-marker"
        adapter = GeminiEmbeddingAdapter(marker)
        error = requests.exceptions.ConnectionError(
            f"failed https://example.invalid?key={marker}"
        )
        output = io.StringIO()

        with patch("ragang.adapters.embedding_adapter.requests.post", side_effect=error), redirect_stdout(output):
            embeddings = adapter.create_embeddings(["document"])

        self.assertEqual(embeddings.size, 0)
        self.assertEqual(output.getvalue(), "")

    def test_async_batch_rejects_zero_concurrency(self):
        adapter = OllamaLocalLLMAdapter("127.0.0.1:11434", "model")

        with self.assertRaisesRegex(ValueError, "positive integer"):
            asyncio.run(adapter.request_async_batch([], [], max_workers=0))


if __name__ == "__main__":
    unittest.main()
