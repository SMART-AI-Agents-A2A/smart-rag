import io
import json
import unittest
from unittest.mock import patch
from urllib.error import HTTPError, URLError

from src.config import Settings
from src.embeddings import Embedder
from src.llm_client import post_json


class OpenRouterTests(unittest.TestCase):
    @patch("src.llm_client.urlopen")
    def test_request_auth_and_response(self, open_url) -> None:
        result = {"data": [{"index": 0, "embedding": [1., 0.]}]}
        open_url.return_value.__enter__.return_value = io.BytesIO(json.dumps(result).encode())
        embedder = Embedder(Settings(openrouter_api_key="test-key"))
        self.assertEqual(embedder.embed_documents(["texto"]), [[1., 0.]])
        request = open_url.call_args.args[0]
        self.assertEqual(request.full_url, "https://openrouter.ai/api/v1/embeddings")
        self.assertEqual(request.get_header("Authorization"), "Bearer test-key")
        self.assertEqual(request.get_method(), "POST")
        self.assertEqual(json.loads(request.data), {
            "model": "qwen/qwen3-embedding-8b", "input": ["texto"], "encoding_format": "float",
        })
        self.assertNotIn("test-key", embedder.signature)
        self.assertNotIn("test-key", repr(embedder.settings))

    @patch("src.llm_client.urlopen")
    def test_missing_key_and_transport_errors(self, open_url) -> None:
        with self.assertRaisesRegex(ValueError, "OPENROUTER_API_KEY"):
            Embedder(Settings()).embed_documents(["texto"])
        open_url.assert_not_called()
        for code in (401, 402, 429, 500):
            open_url.side_effect = HTTPError("https://openrouter.ai", code, "error", {}, None)
            with self.subTest(code=code), self.assertRaisesRegex(RuntimeError, f"HTTP {code}"):
                post_json("https://openrouter.ai/api/v1", "/embeddings", {}, 10, api_key="test-key")
        open_url.side_effect = URLError("offline")
        with self.assertRaisesRegex(RuntimeError, "indisponível"):
            post_json("https://openrouter.ai/api/v1", "/embeddings", {}, 10, api_key="test-key")
        open_url.side_effect = None
        open_url.return_value.__enter__.return_value = io.BytesIO(b"not json")
        with self.assertRaisesRegex(RuntimeError, "JSON inválido"):
            post_json("https://openrouter.ai/api/v1", "/embeddings", {}, 10, api_key="test-key")

    @patch("src.embeddings.post_json")
    def test_response_order_indices_and_dimensions(self, post) -> None:
        embedder = Embedder(Settings())
        post.return_value = {"data": [
            {"index": 1, "embedding": [0., 1.]}, {"index": 0, "embedding": [1., 0.]},
        ]}
        self.assertEqual(embedder.embed_documents(["a", "b"]), [[1., 0.], [0., 1.]])
        for items in (
            [{"index": 0, "embedding": [1.]}, {"index": 0, "embedding": [1.]}],
            [{"index": -1, "embedding": [1.]}, {"index": 1, "embedding": [1.]}],
            [{"index": "0", "embedding": [1.]}, {"index": 1, "embedding": [1.]}],
            [{"index": 0, "embedding": [1.]}, {"index": 1, "embedding": [1., 2.]}],
        ):
            with self.subTest(items=items):
                post.return_value = {"data": items}
                with self.assertRaises(RuntimeError):
                    embedder.embed_documents(["a", "b"])


if __name__ == "__main__":
    unittest.main()
