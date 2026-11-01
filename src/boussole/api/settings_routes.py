"""Page Paramètres : clé OpenRouter, modèle et skill de chaque agent."""

import hashlib
import re
from itertools import groupby
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from boussole.agents.skill_refiner import refine_skill
from boussole.api.services import Services
from boussole.core.enums import Autonomy
from boussole.platform.audit.log import MissingSigningKeyError
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
SETTINGS_WRITERS = frozenset({"pmo"})
# Provenances qu'un formulaire peut déclarer; « default » et « revert » sont posées par le serveur.
FORM_SOURCES = frozenset({SkillSource.MANUAL, SkillSource.AI_REFINED})

router = APIRouter(prefix="/settings")


def _services(request: Request) -> Services:
    services: Services = request.app.state.services
    return services


def _render(request: Request, name: str, **context: Any) -> HTMLResponse:
    templates: Jinja2Templates = request.app.state.templates
    context.setdefault("operator", _services(request).operator_for(request))
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


def _require_pmo(request: Request) -> None:
    """Toute écriture de Paramètres (clé, modèles, skills) est réservée au PMO :
    ces réglages changent ce que font tous les agents et où partent leurs données."""
    if _services(request).role_for(request) not in SETTINGS_WRITERS:
        raise HTTPException(403, "Réservé au PMO : ce compte ne peut pas modifier les paramètres.")


PMO_ONLY = [Depends(_require_pmo)]


def _journal(request: Request, action: str, details: dict[str, object]) -> str | None:
    """Journalise avant l'effet; renvoie un message d'erreur si le journal est indisponible."""
    try:
        _services(request).record_settings_change(request, action, details)
    except MissingSigningKeyError as exc:
        return f"{exc} Aucun changement appliqué."
    return None


def _fingerprint(secret: str) -> str:
    return hashlib.sha256(secret.encode()).hexdigest()[:12]


@router.post("/api-key", response_class=HTMLResponse, dependencies=PMO_ONLY)
def save_key(request: Request, api_key: Annotated[str, Form()]) -> HTMLResponse:
    key = api_key.strip()
    if not key.startswith(KEY_PREFIX):
        return _key(request, error="La clé doit commencer par « sk-or- ».")
    error = _journal(request, "api_key.replace", {"key_fingerprint": _fingerprint(key)})
    if error:
        return _key(request, error=error)
    services = _services(request)
    services.secrets.set(OPENROUTER_KEY, key)
    services.forget_models()
    return _key(request, notice="Clé enregistrée dans le coffre du système.")


@router.post("/api-key/delete", response_class=HTMLResponse, dependencies=PMO_ONLY)
def delete_key(request: Request) -> HTMLResponse:
    error = _journal(request, "api_key.delete", {})
    if error:
        return _key(request, error=error)
    services = _services(request)
    services.secrets.delete(OPENROUTER_KEY)
    services.forget_models()
    return _key(request, notice="Clé supprimée du coffre.")


@router.post("/api-key/test", response_class=HTMLResponse, dependencies=PMO_ONLY)
def test_key(request: Request) -> HTMLResponse:
    gateway = _services(request).gateway()
    if gateway is None:
        return _key(request, error="Aucune clé enregistrée.")
    try:
        return _key(request, key_info=gateway.check_key())
    except GatewayError as exc:
        return _key(request, error=str(exc))


@router.post("/agents/{agent_id}/model", response_class=HTMLResponse, dependencies=PMO_ONLY)
def save_model(request: Request, agent_id: str, model: Annotated[str, Form()]) -> HTMLResponse:
    services = _services(request)
    _agent_name(services, agent_id)
    model = model.strip()
    known = {m.id for m in _models(services)[0]}
    if not MODEL_ID.match(model) or (known and model not in known):
        return _render(request, "_status.html", ok=False, message="Modèle inconnu d'OpenRouter.")
    error = _journal(request, "model.set", {"agent": agent_id, "model": model})
    if error:
        return _render(request, "_status.html", ok=False, message=error)
    services.repo.set_model(agent_id, model, services.operator_for(request))
    return _render(request, "_status.html", ok=True, message="Enregistré")


@router.get("/agents/{agent_id}/skill", response_class=HTMLResponse)
def skill_panel(request: Request, agent_id: str) -> HTMLResponse:
    return _skill(request, agent_id)


@router.post("/agents/{agent_id}/skill", response_class=HTMLResponse, dependencies=PMO_ONLY)
def save_skill(
    request: Request,
    agent_id: str,
    text: Annotated[str, Form()],
    source: Annotated[SkillSource, Form()] = SkillSource.MANUAL,
    reason: Annotated[str, Form()] = "",
) -> HTMLResponse:
    services = _services(request)
    _agent_name(services, agent_id)
    if source not in FORM_SOURCES:
        return _skill(
            request, agent_id, error="Provenance refusée : manuelle ou raffinée par l'IA."
        )
    notice = "Nouvelle version enregistrée."
    if source is SkillSource.AI_REFINED and not services.take_proposal(request, agent_id, text):
        # Seul un texte identique à une proposition générée ici garde « raffinée par l'IA »
        source = SkillSource.MANUAL
        notice = (
            "Nouvelle version enregistrée comme manuelle : le texte diffère de la "
            "proposition de l'IA (ou aucune proposition récente)."
        )
    details: dict[str, object] = {
        "agent": agent_id,
        "source": str(source),
        "text_sha256": hashlib.sha256(text.strip().encode()).hexdigest(),
    }
    error = _journal(request, "skill.save", details)
    if error:
        return _skill(request, agent_id, error=error)
    try:
        services.repo.save_skill(
            agent_id, text, services.operator_for(request), source, reason.strip() or None
        )
    except ValueError as exc:
        return _skill(request, agent_id, error=str(exc))
    return _skill(request, agent_id, notice=notice)


@router.post("/agents/{agent_id}/skill/refine", response_class=HTMLResponse, dependencies=PMO_ONLY)
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
    services.remember_proposal(request, agent_id, proposal)
    return _skill(request, agent_id, draft=text, proposal=proposal, instruction=instruction)


@router.post(
    "/agents/{agent_id}/skill/revert/{version}",
    response_class=HTMLResponse,
    dependencies=PMO_ONLY,
)
def revert(request: Request, agent_id: str, version: int) -> HTMLResponse:
    services = _services(request)
    _agent_name(services, agent_id)
    error = _journal(request, "skill.revert", {"agent": agent_id, "version": version})
    if error:
        return _skill(request, agent_id, error=error)
    try:
        services.repo.revert_skill(agent_id, version, services.operator_for(request))
    except KeyError:
        raise HTTPException(404, "Version inconnue") from None
    return _skill(request, agent_id, notice=f"Version {version} rétablie.")
