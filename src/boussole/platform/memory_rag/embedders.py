"""Embedders : local (fastembed, sur le poste) et factice (tests)."""

import hashlib
import math
from typing import Any

DEFAULT_LOCAL_MODEL = "sentence-transformers/paraphrase-multilingual-mpnet-base-v2"


class LocalEmbedder:
    """Calcule les vecteurs sur le poste : le texte ne quitte jamais la machine."""

    def __init__(self, model_name: str = DEFAULT_LOCAL_MODEL, batch_size: int = 32) -> None:
        from fastembed import TextEmbedding  # import différé : chargement du modèle coûteux

        self._model_name = model_name
        self._batch_size = batch_size
        self._model: Any = TextEmbedding(model_name=model_name)

    @property
    def model_name(self) -> str:
        return self._model_name

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        vectors = self._model.embed(texts, batch_size=self._batch_size)
        return [[float(x) for x in v] for v in vectors]

    def embed_query(self, text: str) -> list[float]:
        return self.embed_documents([text])[0]


class FakeEmbedder:
    """Sac de mots haché : déterministe, assez fidèle pour tester la recherche."""

    def __init__(self, dimensions: int = 64) -> None:
        self._dimensions = dimensions

    @property
    def model_name(self) -> str:
        return f"fake/bag-of-words-{self._dimensions}"

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._vector(t) for t in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._vector(text)

    def _vector(self, text: str) -> list[float]:
        vector = [0.0] * self._dimensions
        for word in text.lower().split():
            bucket = int(hashlib.sha256(word.strip(".,;:!?«»()").encode()).hexdigest(), 16)
            vector[bucket % self._dimensions] += 1.0
        norm = math.sqrt(sum(x * x for x in vector)) or 1.0
        return [x / norm for x in vector]
