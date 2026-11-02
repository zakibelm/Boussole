"""Contrat identique pour chaque adaptateur de la passerelle LLM."""

from collections.abc import Callable
from dataclasses import replace
from decimal import Decimal
from typing import Any

import pytest

from boussole.platform.llm_gateway.fake import FakeGateway
from boussole.platform.llm_gateway.openrouter import OpenRouterGateway
from boussole.platform.llm_gateway.port import (
    GenerationRequest,
    LLMGateway,
    Message,
    ToolSpec,
)
from tests.contract import simulated_openrouter

ADAPTERS: dict[str, Callable[[], LLMGateway]] = {
    "fake": FakeGateway,
    "openrouter": lambda: OpenRouterGateway(
        "sk-or-test", Decimal("1.40"), transport=simulated_openrouter.transport()
    ),
}


@pytest.fixture(params=sorted(ADAPTERS))
def gateway(request: pytest.FixtureRequest) -> LLMGateway:
    return ADAPTERS[request.param]()


def _request(**overrides: Any) -> GenerationRequest:
    base = GenerationRequest(model="fake/small", messages=(Message("user", "Bonjour"),))
    return replace(base, **overrides)


def test_generate_returns_text_and_usage(gateway: LLMGateway) -> None:
    result = gateway.generate(_request())
    assert "Bonjour" in result.text
    assert result.usage.cost_cad >= 0
    assert result.usage.prompt_tokens > 0


def test_structured_output_is_parsed(gateway: LLMGateway) -> None:
    schema = {"type": "object", "properties": {"ok": {"type": "boolean"}}}
    result = gateway.generate(_request(response_schema=schema))
    assert isinstance(result.parsed, dict)


def test_tool_call_is_returned(gateway: LLMGateway) -> None:
    tool = ToolSpec("read_status", "Lire le statut", {"type": "object", "properties": {}})
    result = gateway.generate(_request(tools=(tool,)))
    assert [c.name for c in result.tool_calls] == ["read_status"]


def test_embed_returns_one_vector_per_text(gateway: LLMGateway) -> None:
    result = gateway.embed("fake/embed", ("un", "deux"))
    assert len(result.vectors) == 2
    assert all(len(v) > 0 for v in result.vectors)


def test_list_models_reports_prices_in_cad(gateway: LLMGateway) -> None:
    models = gateway.list_models()
    assert models
    assert all(m.prompt_cad_per_mtok >= 0 for m in models)
