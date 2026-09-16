from dataclasses import replace
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from src.chunker import DocumentChunk
from src.config import Settings
from src.embeddings import Embedder
from src.ingest import ingest
from src.retriever import build_context, retrieve
from src.vector_store import SearchHit, VectorStore
from test_pipeline import write_pdf


class RagTests(unittest.TestCase):
    def test_qdrant_ranking_persistence_rebuild_and_model_guard(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            settings = Settings(qdrant_path=Path(folder) / "db")
            store = VectorStore(settings)
            chunks = [DocumentChunk("a.pdf", 1, 0, "Python"), DocumentChunk("b.pdf", 2, 0, "TypeScript")]
            try:
                store.write_snapshot(chunks, [[1., 0.], [0., 1.]], "model")
                hits = store.search([1., 0.], "model", 1, 0.5)
                self.assertEqual(hits[0].chunk, chunks[0])
                self.assertEqual(len(hits), 1)
                self.assertEqual(store.search([-1., -1.], "model", 4, 0.5), [])
                with self.assertRaisesRegex(ValueError, "mudou"):
                    store.search([1., 0.], "different-model", 1, 0.5)
                with self.assertRaisesRegex(ValueError, "Dimensão"):
                    store.search([1.], "model", 1, 0.5)
                with self.assertRaisesRegex(ValueError, "já existe"):
                    store.write_snapshot(chunks, [[1., 0.], [0., 1.]], "model")
                store.write_snapshot(chunks[1:], [[0., 1.]], "model", rebuild=True)
                self.assertEqual(store.client.count(store.collection).count, 1)
            finally:
                store.close()
            reopened = VectorStore(settings)
            try:
                self.assertEqual(reopened.search([0., 1.], "model", 4, 0.5)[0].chunk, chunks[1])
            finally:
                reopened.close()

    @patch("src.embeddings.post_json")
    def test_embedding_batches_query_and_validation(self, post) -> None:
        embedder = Embedder(Settings(batch_size=1))
        post.return_value = {"data": [{"index": 0, "embedding": [1., 0.]}]}
        self.assertEqual(len(embedder.embed_documents(["a", "b"])), 2)
        self.assertEqual(post.call_count, 2)
        embedder.embed_query("O que é RAG?")
        payload = post.call_args.args[2]
        self.assertIn("Instruct:", payload["input"][0])
        self.assertEqual(payload["encoding_format"], "float")
        self.assertNotIn("truncate", payload)
        self.assertEqual(payload["model"], "qwen/qwen3-embedding-8b")
        self.assertEqual(post.call_args.args[:2], ("https://openrouter.ai/api/v1", "/embeddings"))
        for vectors in ([], [[0., 0.]], [[float("nan")]], [["x"]]):
            post.return_value = {"data": [{"index": i, "embedding": v} for i, v in enumerate(vectors)]}
            with self.assertRaises(RuntimeError):
                embedder.embed_documents(["a"])

    def test_context_budget_and_references(self) -> None:
        hits = [SearchHit(DocumentChunk("a.pdf", 3, 0, "Python é uma linguagem."), 0.9)]
        context = build_context(hits)
        self.assertEqual(build_context(hits, len(context.text)).text, context.text)
        self.assertEqual(build_context(hits, 1).sources, [])
        self.assertEqual(build_context([]).text, "")
        self.assertEqual(context.sources, hits)
        self.assertIn("[1]", context.text)

    @patch("src.embeddings.post_json")
    def test_pipeline_pdf_ingestion_retrieval(self, embed) -> None:
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            docs = root / "documents"
            docs.mkdir()
            write_pdf(docs / "manual.pdf", [None, "Python is a programming language."])
            settings = Settings(documents_dir=docs, qdrant_path=root / "db")
            store = VectorStore(settings)
            embedder = Embedder(settings)
            embed.return_value = {"data": [{"index": 0, "embedding": [1., 0.]}]}
            try:
                self.assertEqual(ingest(settings, embedder, store), 1)
                hits = retrieve("What is Python?", embedder, store)
                context = build_context(hits)
                self.assertEqual(context.sources[0].chunk.page_number, 2)
                self.assertEqual(context.sources[0].chunk.source, "manual.pdf")
                embed.side_effect = RuntimeError("offline")
                with self.assertRaises(RuntimeError):
                    ingest(settings, embedder, store, rebuild=True)
                self.assertEqual(store.client.count(store.collection).count, 1)
                (docs / "manual.pdf").unlink()
                with self.assertRaisesRegex(ValueError, "Nenhum texto"):
                    ingest(settings, embedder, store, rebuild=True)
                self.assertEqual(store.client.count(store.collection).count, 1)
            finally:
                store.close()

    def test_settings_validation(self) -> None:
        for changes in ({"top_k": 0}, {"chunk_overlap": 1000}, {"score_threshold": float("nan")},
                        {"batch_size": 0}, {"timeout": -1}, {"embedding_model": ""}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                replace(Settings(), **changes)


if __name__ == "__main__":
    unittest.main()
