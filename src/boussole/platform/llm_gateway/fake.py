"""Adaptateur factice, déterministe et gratuit, pour les tests."""

import hashlib
from decimal import Decimal
from typing import Any

from boussole.platform.llm_gateway.port import (
    EmbeddingResult,
    GenerationRequest,
    GenerationResult,
    ModelInfo,
    ToolCall,
    Usage,
)

_FREE = Decimal("0")
_DIMENSIONS = 8


def _tokens(text: str) -> int:
    return max(1, len(text.split()))


def _vector(text: str) -> tuple[float, ...]:
    digest = hashlib.sha256(text.encode()).digest()
    return tuple(byte / 255 for byte in digest[:_DIMENSIONS])


class FakeGateway:
    def __init__(self, models: tuple[str, ...] = ("fake/small", "fake/large")) -> None:
        self._models = models

    def generate(self, request: GenerationRequest) -> GenerationResult:
        prompt = " ".join(m.content for m in request.messages)
        text = f"[{request.model}] {request.messages[-1].content}"
        tool_calls = (ToolCall(request.tools[0].name, {}),) if request.tools else ()
        parsed: dict[str, Any] | None = {} if request.response_schema is not None else None
        usage = Usage(_tokens(prompt), _tokens(text), _FREE)
        return GenerationResult(text, request.model, usage, parsed, tool_calls)

    def embed(self, model: str, texts: tuple[str, ...]) -> EmbeddingResult:
        usage = Usage(sum(_tokens(t) for t in texts), 0, _FREE)
        return EmbeddingResult(tuple(_vector(t) for t in texts), model, usage)

    def list_models(self) -> tuple[ModelInfo, ...]:
        return tuple(ModelInfo(m, m, 8192, _FREE, _FREE) for m in self._models)
