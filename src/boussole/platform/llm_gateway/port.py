"""Port de la passerelle LLM : le seul contrat que les agents connaissent."""

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Literal, Protocol

Role = Literal["system", "user", "assistant"]


@dataclass(frozen=True)
class Message:
    role: Role
    content: str


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    parameters: dict[str, Any]


@dataclass(frozen=True)
class GenerationRequest:
    model: str
    messages: tuple[Message, ...]
    temperature: float = 0.2
    max_tokens: int = 1024
    response_schema: dict[str, Any] | None = None
    tools: tuple[ToolSpec, ...] = ()


@dataclass(frozen=True)
class ToolCall:
    name: str
    arguments: dict[str, Any]


@dataclass(frozen=True)
class Usage:
    prompt_tokens: int
    completion_tokens: int
    cost_cad: Decimal


@dataclass(frozen=True)
class GenerationResult:
    text: str
    model: str
    usage: Usage
    parsed: dict[str, Any] | None = None
    tool_calls: tuple[ToolCall, ...] = field(default=())


@dataclass(frozen=True)
class EmbeddingResult:
    vectors: tuple[tuple[float, ...], ...]
    model: str
    usage: Usage


@dataclass(frozen=True)
class ModelInfo:
    """Prix en dollars canadiens par million de jetons."""

    id: str
    name: str
    context_length: int
    prompt_cad_per_mtok: Decimal
    completion_cad_per_mtok: Decimal


class LLMGateway(Protocol):
    def generate(self, request: GenerationRequest) -> GenerationResult: ...

    def embed(self, model: str, texts: tuple[str, ...]) -> EmbeddingResult: ...

    def list_models(self) -> tuple[ModelInfo, ...]: ...


class GatewayError(RuntimeError):
    """Erreur du fournisseur, présentée sans fuite de secret."""
