"""Plafond de budget et comportements propres à OpenRouter."""

from decimal import Decimal

import pytest

from boussole.platform.llm_gateway.budget import (
    BudgetedGateway,
    BudgetExceededError,
    InMemoryLedger,
)
from boussole.platform.llm_gateway.openrouter import OpenRouterGateway
from boussole.platform.llm_gateway.port import GatewayError, GenerationRequest, Message
from tests.contract import simulated_openrouter

REQUEST = GenerationRequest(model="anthropic/claude-sonnet-5.5", messages=(Message("user", "Hi"),))


def _openrouter(key: str = "sk-or-test") -> OpenRouterGateway:
    return OpenRouterGateway(key, Decimal("1.40"), transport=simulated_openrouter.transport())


def test_cost_is_converted_to_cad() -> None:
    assert _openrouter().generate(REQUEST).usage.cost_cad == Decimal("0.001400")


def test_model_prices_are_per_million_tokens_in_cad() -> None:
    model = _openrouter().list_models()[0]
    assert model.prompt_cad_per_mtok == Decimal("4.20")
    assert model.completion_cad_per_mtok == Decimal("21.00")


def test_invalid_key_raises_without_leaking_it() -> None:
    with pytest.raises(GatewayError) as error:
        _openrouter("sk-or-secret-123").check_key()
    assert "401" in str(error.value)
    assert "sk-or-secret-123" not in str(error.value)


def test_check_key_is_free() -> None:
    assert _openrouter().check_key()["label"] == "test"


def test_budget_records_each_call() -> None:
    ledger = InMemoryLedger()
    gateway = BudgetedGateway(_openrouter(), ledger, cap_cad=Decimal("20"))
    gateway.generate(REQUEST, agent="selector")
    assert ledger.entries[0].agent == "selector"
    assert gateway.remaining_cad() == Decimal("20") - Decimal("0.001400")


def test_budget_refuses_a_call_whose_maximal_cost_no_longer_fits() -> None:
    # Estimation d'un appel : environ 0,0215 $ CA (1 024 jetons max au prix de Sonnet);
    # coût réel simulé : 0,0014 $ CA. Avec 0,025 $ CA, trois appels passent, puis le
    # solde (0,0208 $ CA) ne couvre plus l'estimation : refus avant l'envoi.
    ledger = InMemoryLedger()
    gateway = BudgetedGateway(_openrouter(), ledger, cap_cad=Decimal("0.025"))
    for _ in range(3):
        gateway.generate(REQUEST)
    with pytest.raises(BudgetExceededError, match="Budget d'essai atteint"):
        gateway.generate(REQUEST)
    assert len(ledger.entries) == 3
    assert ledger.total_spent_cad() <= Decimal("0.025")


def test_finish_reason_is_reported() -> None:
    result = _openrouter().generate(REQUEST)
    assert result.finish_reason == "stop" and not result.truncated
