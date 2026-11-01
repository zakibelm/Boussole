"""Index vectoriel local (fichier JSONL dans data/local/, ignoré par git)."""

import json
import math
import uuid
from dataclasses import asdict
from pathlib import Path

from boussole.platform.memory_rag.port import Chunk, Hit, PageRange


class LocalVectorStore:
    """Recherche par similarité cosinus en Python : suffisant pour quelques milliers d'extraits."""

    def __init__(self, path: Path | None = None) -> None:
        self._path = path
        self._rows: list[tuple[Chunk, list[float], str]] = []
        if path and path.exists():
            self._load(path)

    def add(self, chunks: list[Chunk], vectors: list[list[float]], model: str) -> None:
        if len(chunks) != len(vectors):
            raise ValueError("Autant de vecteurs que d'extraits sont attendus.")
        known = {chunk.id for chunk, _, _ in self._rows}
        self._rows.extend(
            (c, _normalized(v), model)
            for c, v in zip(chunks, vectors, strict=True)
            if c.id not in known
        )
        self._save()

    def remove_source(self, source: str) -> int:
        before = len(self._rows)
        self._rows = [row for row in self._rows if row[0].source != source]
        self._save()
        return before - len(self._rows)

    def search(
        self,
        vector: list[float],
        k: int,
        model: str,
        project_id: uuid.UUID | None,
        pages: tuple[PageRange, ...] | None = None,
    ) -> list[Hit]:
        query = _normalized(vector)
        hits = [
            Hit(chunk, _dot(query, v))
            for chunk, v, row_model in self._rows
            if row_model == model
            and chunk.project_id in (None, project_id)
            and _within(chunk, pages)
        ]
        return sorted(hits, key=lambda h: h.score, reverse=True)[:k]

    def count(self) -> int:
        return len(self._rows)

    def _save(self) -> None:
        if self._path is None:
            return
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with self._path.open("w", encoding="utf-8") as handle:
            for chunk, vector, model in self._rows:
                row = {**asdict(chunk), "project_id": _str(chunk.project_id)}
                handle.write(json.dumps({"chunk": row, "vector": vector, "model": model}) + "\n")

    def _load(self, path: Path) -> None:
        with path.open(encoding="utf-8") as handle:
            for line in handle:
                row = json.loads(line)
                data = row["chunk"]
                project = data.pop("project_id")
                chunk = Chunk(**data, project_id=uuid.UUID(project) if project else None)
                self._rows.append((chunk, row["vector"], row["model"]))


def _within(chunk: Chunk, pages: tuple[PageRange, ...] | None) -> bool:
    """Un extrait de projet n'a pas de pages du livre : le filtre ne vise que les sources."""
    if pages is None or chunk.project_id is not None:
        return True
    return any(chunk.page_start <= end and chunk.page_end >= start for start, end in pages)


def _normalized(vector: list[float]) -> list[float]:
    norm = math.sqrt(sum(x * x for x in vector)) or 1.0
    return [x / norm for x in vector]


def _dot(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b, strict=True))


def _str(value: uuid.UUID | None) -> str | None:
    return str(value) if value else None
