"""Raffinement d'un skill par l'IA : produit une proposition, jamais un effet."""

from boussole.platform.llm_gateway.budget import BudgetedGateway
from boussole.platform.llm_gateway.port import GenerationRequest, Message
from boussole.platform.settings_store.repository import SettingsRepository

REFINER_ID = "skill_refiner"


def refine_skill(
    repo: SettingsRepository,
    gateway: BudgetedGateway,
    agent_id: str,
    draft: str,
    instruction: str,
    agent_name: str,
) -> str:
    """Le skill et la consigne sont des données à améliorer, pas des ordres à exécuter."""
    content = (
        f"Agent : {agent_name} ({agent_id})\n\n"
        f"<skill_actuel>\n{draft.strip()}\n</skill_actuel>\n\n"
        f"<consigne_utilisateur>\n{instruction.strip() or 'Aucune'}\n</consigne_utilisateur>"
    )
    request = GenerationRequest(
        model=repo.effective_model(REFINER_ID),
        messages=(
            Message("system", repo.system_prompt(REFINER_ID)),
            Message("user", content),
        ),
        temperature=0.3,
        max_tokens=1500,
    )
    return gateway.generate(request, agent=REFINER_ID).text.strip()
