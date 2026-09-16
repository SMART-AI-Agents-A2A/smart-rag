from dataclasses import asdict
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from src.api import create_app
from src.config import Settings
from src.rag import RAG
from test_pipeline import write_pdf


class ApiTests(unittest.TestCase):
    @patch("src.embeddings.post_json")
    def test_ingest_python_and_http_query(self, embed) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            docs = root / "documents"
            docs.mkdir()
            write_pdf(docs / "manual.pdf", [None, "Python is a language."])
            settings = Settings(documents_dir=docs, qdrant_path=root / "db", openrouter_api_key="test-key")
            embed.return_value = {"data": [{"index": 0, "embedding": [1., 0.]}]}
            with RAG(settings) as rag:
                self.assertEqual(rag.ingest(), 1)
                result = asdict(rag.retrieve("What is Python?"))
            app = create_app(settings)
            with TestClient(app) as client:
                response = client.post("/retrieve", json={
                    "question": "What is Python?",
                    "top_k": 1, "score_threshold": 0.5,
                })
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json(), result)
                self.assertEqual(result["chunks"][0]["page_number"], 2)
                self.assertEqual(result["chunks"][0]["text"], "Python is a language.")
                self.assertIn("Python is a language.", result["context"])
                self.assertNotIn("text", result)
                self.assertEqual(app.state.rag.settings.top_k, settings.top_k)
                self.assertTrue(all(call.args[1] == "/embeddings" for call in embed.call_args_list))
                self.assertEqual(client.post("/ask", json={"question": "a"}).status_code, 404)
                schema = client.get("/openapi.json").json()
                self.assertNotIn("/ask", schema["paths"])
                self.assertEqual(client.get("/health").json(), {"status": "ok"})
                self.assertEqual(client.get("/openapi.json").status_code, 200)
                embed.return_value = {"data": [{"index": 0, "embedding": [-1., 0.]}]}
                response = client.post("/retrieve", json={"question": "Unrelated?"})
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json()["chunks"], [])
                self.assertEqual(response.json()["context"], "")
            with RAG(settings) as reopened:
                self.assertTrue(reopened.store.exists())

    def test_request_validation_and_missing_index(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            settings = Settings(qdrant_path=Path(directory) / "db", openrouter_api_key="test-key")
            with TestClient(create_app(settings)) as client:
                for body in ({}, {"question": "   "}, {"question": "a", "top_k": 0},
                             {"question": "a", "top_k": 101}, {"question": "a", "score_threshold": 2},
                             {"question": "a", "model": "provider/model"}, {"question": "a", "unknown": True}):
                    with self.subTest(body=body):
                        self.assertEqual(client.post("/retrieve", json=body).status_code, 422)
                self.assertEqual(client.post("/retrieve", json={"question": "a"}).status_code, 409)

    def test_missing_key(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with TestClient(create_app(Settings(qdrant_path=Path(directory) / "db"))) as client:
                self.assertEqual(client.post("/retrieve", json={"question": "a"}).status_code, 503)

    def test_backend_errors_do_not_expose_upstream_details(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            settings = Settings(qdrant_path=Path(directory) / "db", openrouter_api_key="test-key")
            app = create_app(settings)
            with TestClient(app) as client:
                for error, status in ((RuntimeError("secret upstream"), 502),
                                      (OSError("secret upstream"), 503),
                                      (ValueError("Incompatible index"), 400)):
                    with patch.object(app.state.rag, "retrieve", side_effect=error):
                        response = client.post("/retrieve", json={"question": "a"})
                        self.assertEqual(response.status_code, status)
                        self.assertNotIn("secret upstream", response.text)


if __name__ == "__main__":
    unittest.main()
