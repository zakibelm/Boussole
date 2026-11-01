"""Mémoire RAG : ingestion et recherche avec citations."""

import logging
import re
import uuid
from dataclasses import dataclass
from pathlib import Path

from boussole.platform.memory_rag.chunking import (
    chunk_document,
    heading_sections,
    outline_sections,
    read_pages,
)
from boussole.platform.memory_rag.port import Embedder, Hit, PageRange, VectorStore

log = logging.getLogger(__name__)

LOCAL_DATA = Path(__file__).resolve().parents[4] / "data" / "local"
NO_SOURCE = "Aucune source trouvée dans la mémoire pour cette question."
# Pages liminaires (table des matières, liste des figures, mentions légales, index) :
# elles ressemblent à tout et n'enseignent rien. Constat des tests du 1er novembre.
_FRONT_MATTER = re.compile(
    r"^(table of contents|contents|list of figures.*|notice|index|table des matières)$",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class IngestReport:
    source: str
    pages: int
    sections: int
    chunks: int
    sections_from: str  # « signets » ou « titres »


class OutsideLocalDataError(ValueError):
    """Le document protégé doit rester dans data/local/, ignoré par git."""


class RagMemory:
    def __init__(
        self, embedder: Embedder, store: VectorStore, local_root: Path = LOCAL_DATA
    ) -> None:
        self._embedder = embedder
        self._store = store
        self._local_root = local_root.resolve()

    def ingest_pdf(self, pdf: Path, source: str) -> IngestReport:
        """Réindexe entièrement `source`. Seuls des compteurs sont journalisés."""
        resolved = pdf.resolve()
        if not resolved.is_relative_to(self._local_root):
            raise OutsideLocalDataError(f"Le PDF doit être dans {self._local_root}.")
        pages = read_pages(resolved)
        sections = outline_sections(resolved)
        origin = "signets"
        if not sections:
            sections, origin = heading_sections(pages), "titres"
        chunks = chunk_document(pages, sections, source)
        self._store.remove_source(source)
        vectors = self._embedder.embed_documents([c.text for c in chunks])
        self._store.add(chunks, vectors, self._embedder.model_name)
        report = IngestReport(source, len(pages), len(sections), len(chunks), origin)
        log.info("ingestion %s", report)
        return report

    def search(
        self,
        question: str,
        k: int = 5,
        project_id: uuid.UUID | None = None,
        pages: tuple[PageRange, ...] | None = None,
    ) -> list[Hit]:
        """`pages` : parties du livre propres à l'agent (voir agents/pmbok_skills.py)."""
        vector = self._embedder.embed_query(question)
        found = self._store.search(vector, k * 3, self._embedder.model_name, project_id, pages)
        hits = [h for h in found if not is_front_matter(h.chunk.section_title)][:k]
        log.info("recherche k=%d citations=%s", k, [h.chunk.citation() for h in hits])
        return hits


def is_front_matter(title: str) -> bool:
    return bool(_FRONT_MATTER.match(title.strip()))


def format_sources(hits: list[Hit]) -> str:
    """Bloc de sources numérotées à joindre au contexte d'un agent."""
    if not hits:
        return NO_SOURCE
    return "\n\n".join(
        f"[{i}] {hit.chunk.citation()}\n{hit.chunk.text}" for i, hit in enumerate(hits, start=1)
    )
