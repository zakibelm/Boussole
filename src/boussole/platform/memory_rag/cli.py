"""Commande locale : `python -m boussole.platform.memory_rag.cli ingest|search`.

N'affiche jamais le texte du document, sauf `search --show-text`, à l'écran
seulement et pour vérification humaine.
"""

import argparse
import os
import sys
from pathlib import Path

from boussole.agents.pmbok_skills import load_pmbok_skills
from boussole.config import load_config
from boussole.platform.memory_rag.embedders import DEFAULT_LOCAL_MODEL, LocalEmbedder
from boussole.platform.memory_rag.local_store import LocalVectorStore
from boussole.platform.memory_rag.memory import LOCAL_DATA, OutsideLocalDataError, RagMemory

INDEX_PATH = LOCAL_DATA / "rag_index.jsonl"


def memory() -> RagMemory:
    model = os.environ.get("BOUSSOLE_EMBEDDING_MODEL", DEFAULT_LOCAL_MODEL)
    return RagMemory(LocalEmbedder(model), LocalVectorStore(INDEX_PATH))


def _ingest(args: argparse.Namespace) -> int:
    try:
        report = memory().ingest_pdf(Path(args.pdf), args.source)
    except OutsideLocalDataError as exc:
        print(f"Refusé : {exc}", file=sys.stderr)
        return 2
    print(
        f"{report.source} : {report.pages} pages, {report.sections} sections "
        f"(depuis les {report.sections_from}), {report.chunks} extraits indexés."
    )
    return 0


def _search(args: argparse.Namespace) -> int:
    pages = None
    if args.agent:
        pages = load_pmbok_skills(load_config().pmbok_skills_path).pages_for(args.agent)
    hits = memory().search(args.question, k=args.k, pages=pages)
    if not hits:
        print("Aucune source trouvée.")
    for i, hit in enumerate(hits, start=1):
        print(f"[{i}] {hit.score:.3f}  {hit.chunk.citation()}")
        if args.show_text:
            print(f"    {hit.chunk.text[:400]}…\n")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="boussole-rag", description="Mémoire RAG locale")
    commands = parser.add_subparsers(required=True)
    ingest = commands.add_parser("ingest", help="Indexer un PDF situé dans data/local/")
    ingest.add_argument("pdf")
    ingest.add_argument("--source", default="PMBOK 8", help="Nom affiché dans les citations")
    ingest.set_defaults(run=_ingest)
    search = commands.add_parser("search", help="Chercher et afficher les citations")
    search.add_argument("question")
    search.add_argument("-k", type=int, default=5)
    search.add_argument("--show-text", action="store_true")
    search.add_argument("--agent", help="Limiter aux parties du PMBOK de cet agent")
    search.set_defaults(run=_search)
    args = parser.parse_args(argv)
    code: int = args.run(args)
    return code


if __name__ == "__main__":
    sys.exit(main())
