"""Ports de la mémoire RAG : extraits, embeddings, stockage vectoriel."""

import uuid
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class Chunk:
    """Extrait indexé. `project_id` absent = connaissance commune (PMBOK, modèles)."""

    id: str
    source: str
    section: str
    section_title: str
    page_start: int
    page_end: int
    text: str
    project_id: uuid.UUID | None = None

    def citation(self) -> str:
        """Référence affichable et journalisable : jamais le texte."""
        pages = (
            f"p. {self.page_start}"
            if self.page_start == self.page_end
            else f"p. {self.page_start}-{self.page_end}"
        )
        title = f" « {self.section_title} »" if self.section_title else ""
        return f"{self.source}, section {self.section}{title}, {pages}"


@dataclass(frozen=True)
class Hit:
    chunk: Chunk
    score: float


class Embedder(Protocol):
    @property
    def model_name(self) -> str: ...

    def embed_documents(self, texts: list[str]) -> list[list[float]]: ...

    def embed_query(self, text: str) -> list[float]: ...


class VectorStore(Protocol):
    def add(self, chunks: list[Chunk], vectors: list[list[float]], model: str) -> None: ...

    def remove_source(self, source: str) -> int: ...

    def search(
        self, vector: list[float], k: int, model: str, project_id: uuid.UUID | None
    ) -> list[Hit]: ...

    def count(self) -> int: ...
