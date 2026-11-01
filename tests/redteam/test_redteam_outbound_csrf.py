"""Red team du 1er novembre 2026, constats 6 et 8.

6. Une action qui sort de Boussole sans destination déclarée échappait à la liste
   blanche : elle est refusée, même validée par un humain.
8. Le filtre CSRF faisait confiance à l'en-tête X-Forwarded-Host envoyé par le client.
"""

import uuid

from fastapi.testclient import TestClient

from boussole.api.app import create_app
from boussole.api.services import Services
from boussole.core.enums import Autonomy
from boussole.platform.guardrails.policy import ActionRequest, Approval, Verdict, decide
from tests.guardrails_support import POLICY
from tests.integration.test_settings_page import services  # noqa: F401  (fixture)

PROJECT = uuid.uuid4()
PMO = Approval("Zakaria", "pmo")


def test_outbound_action_without_destination_is_refused_even_when_approved() -> None:
    request = ActionRequest("send_message", "pm_adaptive", PROJECT, PROJECT)
    decision = decide(POLICY, request, Autonomy.AUGMENTATION, PMO)
    assert decision.verdict is Verdict.DENY
    assert "sans destination" in decision.reason


def test_outbound_action_to_an_allowlisted_destination_still_works() -> None:
    request = ActionRequest(
        "send_message", "pm_adaptive", PROJECT, PROJECT, destination="https://openrouter.ai/x"
    )
    assert decide(POLICY, request, Autonomy.AUGMENTATION, PMO).verdict is Verdict.ALLOW


def test_internal_actions_do_not_need_a_destination() -> None:
    request = ActionRequest("update_task_status", "closing", PROJECT, PROJECT)
    assert decide(POLICY, request, Autonomy.AUTOMATION, None).verdict is Verdict.ALLOW


def test_client_supplied_forwarded_host_is_not_trusted(services: Services) -> None:  # noqa: F811
    client = TestClient(create_app(services))
    response = client.post(
        "/settings/agents/selector/skill",
        data={"text": "Piège"},
        headers={"Origin": "https://pirate.example", "X-Forwarded-Host": "pirate.example"},
    )
    assert response.status_code == 403
    assert services.repo.current_skill("selector").version == 0


def test_configured_public_origin_is_accepted(services: Services) -> None:  # noqa: F811
    app = create_app(services, frozenset({"https://boussole.example"}))
    response = TestClient(app).post(
        "/settings/agents/selector/skill",
        data={"text": "Nouveau skill"},
        headers={"Origin": "https://boussole.example"},
    )
    assert response.status_code == 200
    assert services.repo.current_skill("selector").version == 1
