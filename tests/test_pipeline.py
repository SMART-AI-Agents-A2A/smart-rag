from pathlib import Path
import tempfile
import unittest

from pypdf import PdfWriter
from pypdf.generic import DictionaryObject, NameObject, DecodedStreamObject

from src.chunker import chunk_pages
from src.pdf_loader import DocumentPage, load_pdf_pages


def write_pdf(path: Path, texts: list[str | None]) -> None:
    writer = PdfWriter()
    font = DictionaryObject({
        NameObject("/Type"): NameObject("/Font"),
        NameObject("/Subtype"): NameObject("/Type1"),
        NameObject("/BaseFont"): NameObject("/Helvetica"),
    })
    for text in texts:
        page = writer.add_blank_page(width=600, height=800)
        if text is not None:
            page[NameObject("/Resources")] = DictionaryObject({
                NameObject("/Font"): DictionaryObject({NameObject("/F1"): font})
            })
            stream = DecodedStreamObject()
            escaped = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
            stream.set_data(f"BT /F1 12 Tf 50 750 Td ({escaped}) Tj ET".encode("ascii"))
            page[NameObject("/Contents")] = stream
    writer.write(path)


class PipelineTests(unittest.TestCase):
    def test_pdf_to_pages_to_chunks(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            write_pdf(root / "b.pdf", ["Second document"])
            write_pdf(root / "a.pdf", ["abcdefghij", None, "klmnopqrst", "   "])
            (root / "ignored.txt").write_text("ignore")
            pages = load_pdf_pages(root)
            self.assertEqual(
                [(p.source, p.page_number, p.text) for p in pages],
                [("a.pdf", 1, "abcdefghij"), ("a.pdf", 3, "klmnopqrst"),
                 ("b.pdf", 1, "Second document")],
            )
            chunks = chunk_pages(pages, chunk_size=6, overlap=2)
            self.assertEqual(
                [(c.source, c.page_number, c.chunk_index, c.text) for c in chunks[:4]],
                [("a.pdf", 1, 0, "abcdef"), ("a.pdf", 1, 1, "efghij"),
                 ("a.pdf", 3, 0, "klmnop"), ("a.pdf", 3, 1, "opqrst")],
            )

    def test_chunk_boundaries(self) -> None:
        for text, size, overlap, expected in [
            ("abc", 6, 2, ["abc"]),
            ("abcdef", 6, 2, ["abcdef"]),
            ("abcdefg", 6, 2, ["abcdef", "efg"]),
            ("abcdefg", 3, 0, ["abc", "def", "g"]),
            ("abcd", 3, 2, ["abc", "bcd"]),
            ("A😀BC", 3, 1, ["A😀B", "BC"]),
            ("   ", 3, 0, []),
            ("", 3, 0, []),
        ]:
            with self.subTest(text=text, size=size, overlap=overlap):
                chunks = chunk_pages([DocumentPage("a.pdf", 1, text)], size, overlap)
                self.assertEqual([c.text for c in chunks], expected)
        self.assertEqual(chunk_pages([]), [])

    def test_invalid_configuration(self) -> None:
        for size, overlap in [(0, 0), (-1, 0), (5, -1), (5, 5), (5, 6),
                              (True, 0), (5, 1.5)]:
            with self.subTest(size=size, overlap=overlap):
                with self.assertRaises(ValueError):
                    chunk_pages([], size, overlap)

    def test_missing_empty_and_corrupt(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            self.assertEqual(load_pdf_pages(root), [])
            with self.assertRaises(NotADirectoryError):
                load_pdf_pages(root / "missing")
            (root / "broken.pdf").write_bytes(b"%PDF-1.7\ninvalid\n%%EOF")
            with self.assertRaisesRegex(RuntimeError, "broken.pdf"):
                load_pdf_pages(root)


if __name__ == "__main__":
    unittest.main()
