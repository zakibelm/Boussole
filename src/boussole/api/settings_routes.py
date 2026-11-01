"""Page Paramètres : clé OpenRouter, modèle et skill de chaque agent."""

import re
from itertools import groupby
from typing import Annotated, Any

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from boussole.agents.skill_refiner import refine_skill
from boussole.api.services import Services
from boussole.core.enums import Autonomy
from boussole.platform.llm_gateway.budget import BudgetExceededError
from boussole.platform.llm_gateway.port import GatewayError, ModelInfo
from boussole.platform.secrets import OPENROUTER_KEY, mask
from boussole.platform.settings_store.repository import SkillSource

MODEL_ID = re.compile(r"^[\w.-]+/[\w.:-]+$")
AUTONOMY_LABELS = {
    Autonomy.AUTOMATION: "Automatisation",
    Autonomy.ASSISTANCE: "Assistance",
    Autonomy.AUGMENTATION: "Augmentation",
}
KEY_PREFIX = "sk-or-"
FREE_LABEL = "Gratuits (0 $ CA, pour tester les fonctions)"

router = APIRouter(prefix="/settings")


def _services(request: Request) -> Services:
    services: Services = request.app.state.services
    return services


def _render(request: Request, name: str, **context: Any) -> HTMLResponse:
    templates: Jinja2Templates = request.app.state.templates
    context.setdefault("operator", _services(request).operator)
    return templates.TemplateResponse(request, name, context)


def _agent_name(services: Services, agent_id: str) -> str:
    try:
        return services.catalog.get(agent_id).name
    except KeyError:
        raise HTTPException(404, "Agent inconnu") from None


def _models(services: Services) -> tuple[tuple[ModelInfo, ...], str | None]:
    try:
        return services.models(), None
    except GatewayError as exc:
        return (), str(exc)


def _by_provider(models: tuple[ModelInfo, ...]) -> list[tuple[str, list[ModelInfo]]]:
    """Gratuits d'abord (pour tester les fonctions), puis payants par fournisseur.

    La liste arrive triée par identifiant, donc chaque fournisseur reste groupé.
    """
    free = [m for m in models if _is_free(m)]
    paid = [m for m in models if not _is_free(m)]
    groups = [(f"Payants · {name}", list(group)) for name, group in groupby(paid, key=_provider)]
    return ([(FREE_LABEL, free)] if free else []) + groups


def _is_free(model: ModelInfo) -> bool:
    return model.prompt_cad_per_mtok == 0 and model.completion_cad_per_mtok == 0


def _provider(model: ModelInfo) -> str:
    return model.id.split("/", 1)[0]


def _key(request: Request, **extra: Any) -> HTMLResponse:
    masked = mask(_services(request).secrets.get(OPENROUTER_KEY))
    return _render(request, "_key.html", masked_key=masked, **extra)


def _skill(request: Request, agent_id: str, **extra: Any) -> HTMLResponse:
    services = _services(request)
    return _render(
        request,
        "_skill.html",
        agent_id=agent_id,
        agent_name=_agent_name(services, agent_id),
        skill=services.repo.current_skill(agent_id),
        history=services.repo.skill_history(agent_id),
        pmbok_note=services.repo.pmbok_note(agent_id),
        **extra,
    )


@router.get("", response_class=HTMLResponse)
def settings_page(request: Request) -> HTMLResponse:
    services = _services(request)
    models, models_error = _models(services)
    return _render(
        request,
        "settings.html",
        masked_key=mask(services.secrets.get(OPENROUTER_KEY)),
        groups=services.catalog.groups,
        effective=services.repo.effective_model,
        skill_version=lambda agent_id: services.repo.current_skill(agent_id).version,
        models=models,
        model_groups=_by_provider(models),
        models_error=models_error,
        spent=services.ledger.total_spent_cad(),
        cap=services.cap_cad,
        shared_rules=services.catalog.shared_rules,
        autonomy_labels=AUTONOMY_LABELS,
    )


@router.post("/api-key", response_class=HTMLResponse)
def save_key(request: Request, api_key: Annotated[str, Form()]) -> HTMLResponse:
    key = api_key.strip()
    if not key.startswith(KEY_PREFIX):
        return _key(request, error="La clé doit commencer par « sk-or- ».")
    services = _services(request)
    services.secrets.set(OPENROUTER_KEY, key)
    services.forget_models()
    return _key(request, notice="Clé enregistrée dans le coffre du système.")


@router.post("/api-key/delete", response_class=HTMLResponse)
def delete_key(request: Request) -> HTMLResponse:
    services = _services(request)
    services.secrets.delete(OPENROUTER_KEY)
    services.forget_models()
    return _key(request, notice="Clé supprimée du coffre.")


@router.post("/api-key/test", response_class=HTMLResponse)
def test_key(request: Request) -> HTMLResponse:
    gateway = _services(request).gateway()
    if gateway is None:
        return _key(request, error="Aucune clé enregistrée.")
    try:
        return _key(request, key_info=gateway.check_key())
    except GatewayError as exc:
        return _key(request, error=str(exc))


@router.post("/agents/{agent_id}/model", response_class=HTMLResponse)
def save_model(request: Request, agent_id: str, model: Annotated[str, Form()]) -> HTMLResponse:
    services = _services(request)
    _agent_name(services, agent_id)
    model = model.strip()
    known = {m.id for m in _models(services)[0]}
    if not MODEL_ID.match(model) or (known and model not in known):
        return _render(request, "_status.html", ok=False, message="Modèle inconnu d'OpenRouter.")
    services.repo.set_model(agent_id, model, services.operator)
    return _render(request, "_status.html", ok=True, message="Enregistré")


@router.get("/agents/{agent_id}/skill", response_class=HTMLResponse)
def skill_panel(request: Request, agent_id: str) -> HTMLResponse:
    return _skill(request, agent_id)


@router.post("/agents/{agent_id}/skill", response_class=HTMLResponse)
def save_skill(
    request: Request,
    agent_id: str,
    text: Annotated[str, Form()],
    source: Annotated[SkillSource, Form()] = SkillSource.MANUAL,
    reason: Annotated[str, Form()] = "",
) -> HTMLResponse:
    services = _services(request)
    _agent_name(services, agent_id)
    try:
        services.repo.save_skill(agent_id, text, services.operator, source, reason.strip() or None)
    except ValueError as exc:
        return _skill(request, agent_id, error=str(exc))
    return _skill(request, agent_id, notice="Nouvelle version enregistrée.")


@router.post("/agents/{agent_id}/skill/refine", response_class=HTMLResponse)
def refine(
    request: Request,
    agent_id: str,
    text: Annotated[str, Form()],
    instruction: Annotated[str, Form()] = "",
) -> HTMLResponse:
    services = _services(request)
    name = _agent_name(services, agent_id)
    gateway = services.budgeted_gateway()
    if gateway is None:
        return _skill(request, agent_id, error="Enregistre d'abord la clé OpenRouter.")
    try:
        proposal = refine_skill(services.repo, gateway, agent_id, text, instruction, name)
    except (GatewayError, BudgetExceededError) as exc:
        return _skill(request, agent_id, error=str(exc))
    return _skill(request, agent_id, draft=text, proposal=proposal, instruction=instruction)


@router.post("/agents/{agent_id}/skill/revert/{version}", response_class=HTMLResponse)
def revert(request: Request, agent_id: str, version: int) -> HTMLResponse:
    services = _services(request)
    _agent_name(services, agent_id)
    try:
        services.repo.revert_skill(agent_id, version, services.operator)
    except KeyError:
        raise HTTPException(404, "Version inconnue") from None
    return _skill(request, agent_id, notice=f"Version {version} rétablie.")
