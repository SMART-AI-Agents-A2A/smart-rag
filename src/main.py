import argparse
from dataclasses import asdict, replace
import json
from pathlib import Path
import sys

from .chunker import chunk_pages
from .config import load_settings
from .rag import RAG
from .pdf_loader import load_pdf_pages


def main() -> int:
    parser = argparse.ArgumentParser(description="smart_rag: PDF → embeddings → Qdrant → contexto")
    commands = parser.add_subparsers(dest="command", required=True)
    inspect = commands.add_parser("inspect", help="Exibe amostras")
    inspect.add_argument("--pages-only", action="store_true")
    inspect.add_argument("--documents-dir", type=Path)
    inspect.add_argument("--chunk-size", type=int)
    inspect.add_argument("--overlap", type=int)
    ingest_parser = commands.add_parser("ingest", help="Indexa todos os PDFs")
    ingest_parser.add_argument("--rebuild", action="store_true", help="Substitui toda a coleção configurada")
    query = commands.add_parser("retrieve", help="Recupera trechos dos documentos")
    query.add_argument("question")
    query.add_argument("--top-k", type=int)
    query.add_argument("--score-threshold", type=float)
    args = parser.parse_args()
    try:
        settings = load_settings()
        if args.command == "inspect":
            overrides = {name: value for name, value in {
                "documents_dir": args.documents_dir, "chunk_size": args.chunk_size,
                "chunk_overlap": args.overlap,
            }.items() if value is not None}
            settings = replace(settings, **overrides)
            pages = load_pdf_pages(settings.documents_dir)
            print(f"Páginas com texto: {len(pages)}")
            for page in pages:
                print(f"\n[{page.source} | página {page.page_number}]\n{' '.join(page.text.split())[:160]}")
            if not args.pages_only:
                chunks = chunk_pages(pages, settings.chunk_size, settings.chunk_overlap)
                print(f"\nChunks: {len(chunks)}")
                for chunk in chunks:
                    print(f"\n[{chunk.source} | página {chunk.page_number} | chunk {chunk.chunk_index}]")
                    print(" ".join(chunk.text.split())[:160])
            return 0
        with RAG(settings) as rag:
            if args.command == "ingest":
                count = rag.ingest(rebuild=args.rebuild)
                print(f"Ingestão concluída: {count} chunks na coleção {settings.collection}.")
            else:
                result = rag.retrieve(args.question, top_k=args.top_k,
                                      score_threshold=args.score_threshold)
                print(json.dumps(asdict(result), ensure_ascii=False, indent=2))
        return 0
    except Exception as exc:
        print(f"Erro: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
