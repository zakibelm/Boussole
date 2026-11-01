"""Pages Projets : création en une conversation, décision humaine, tableau de bord, chat."""

import uuid
from datetime import date
from typing import Annotated, Any

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates

from boussole.agents.answer import AnswerRefusedError, MissingApiKeyError
from boussole.api.services import Services
from boussole.core.enums import Approach
from boussole.platform.audit.log import MissingSigningKeyError
from boussole.platform.llm_gateway.budget import BudgetExceededError
from boussole.platform.llm_gateway.port import GatewayError
from boussole.projects.assistant import DecisionRefusedError, ProjectAssistant
from boussole.projects.repository import APPROACH_LABELS

router = APIRouter(prefix="/projects")
_AI_ERRORS = (
    MissingApiKeyError,
    BudgetExceededError,
    GatewayError,
    AnswerRefusedError,
    DecisionRefusedError,
)
CHAT_EXCLUDED = {"skill_refiner"}


def _assistant(request: Request) -> ProjectAssistant:
    services: Services = request.app.state.services
    if services.projects is None:
        raise HTTPException(503, "Projets indisponibles")
    return services.projects


def _render(request: Request, name: str, **context: Any) -> HTMLResponse:
    templates: Jinja2Templates = request.app.state.templates
    services: Services = request.app.state.services
    context.setdefault("operator", services.operator)
    return templates.TemplateResponse(request, name, context)


def _error(exc: Exception) -> str:
    if isinstance(exc, MissingSigningKeyError):
        return "Clé de signature du journal absente : un humain doit la créer (init-key)."
    return str(exc)


@router.get("", response_class=HTMLResponse)
def projects_page(request: Request) -> HTMLResponse:
    return _render(request, "projects.html", projects=_assistant(request).projects.all())


@router.post("")
def create_project(
    request: Request, name: Annotated[str, Form()], description: Annotated[str, Form()] = ""
) -> Response:
    assistant = _assistant(request)
    try:
        project_id = assistant.projects.create(name, description)
    except ValueError as exc:
        return _render(request, "projects.html", projects=assistant.projects.all(), error=str(exc))
    try:
        assistant.propose_approach(project_id)
    except (*_AI_ERRORS, MissingSigningKeyError) as exc:
        return _project(request, project_id, error=f"Proposition impossible : {_error(exc)}")
    return RedirectResponse(f"/projects/{project_id}", status_code=303)


@router.get("/{project_id}", response_class=HTMLResponse)
def project_page(request: Request, project_id: uuid.UUID) -> HTMLResponse:
    return _project(request, project_id)


@router.post("/{project_id}/approach", response_class=HTMLResponse)
def propose(request: Request, project_id: uuid.UUID) -> HTMLResponse:
    try:
        _assistant(request).propose_approach(project_id)
    except KeyError:
        raise HTTPException(404, "Projet inconnu") from None
    except (*_AI_ERRORS, MissingSigningKeyError) as exc:
        return _project(request, project_id, error=f"Proposition impossible : {_error(exc)}")
    return _project(request, project_id, notice="Nouvelle proposition du sélecteur.")


@router.post("/{project_id}/decisions/{decision_id}", response_class=HTMLResponse)
def decide(
    request: Request,
    project_id: uuid.UUID,
    decision_id: uuid.UUID,
    verdict: Annotated[str, Form()],
    approach: Annotated[Approach, Form()] = Approach.UNDECIDED,
    reason: Annotated[str, Form()] = "",
) -> HTMLResponse:
    assistant = _assistant(request)
    try:
        if verdict == "reject":
            assistant.reject(project_id, decision_id, reason)
        else:
            assistant.decide(project_id, decision_id, approach, reason)
    except KeyError:
        raise HTTPException(404, "Décision inconnue") from None
    except (ValueError, DecisionRefusedError, MissingSigningKeyError) as exc:
        return _project(request, project_id, error=_error(exc))
    return _project(request, project_id, notice="Décision enregistrée et journalisée.")


@router.post("/{project_id}/ask", response_class=HTMLResponse)
def ask(
    request: Request,
    project_id: uuid.UUID,
    question: Annotated[str, Form()],
    agent: Annotated[str, Form()] = "selector",
) -> HTMLResponse:
    try:
        answer = _assistant(request).ask(project_id, agent, question)
    except KeyError:
        raise HTTPException(404, "Projet inconnu") from None
    except (ValueError, *_AI_ERRORS, MissingSigningKeyError) as exc:
        return _render(request, "_answer.html", error=_error(exc))
    return _render(request, "_answer.html", answer=answer, question=question)


def _project(request: Request, project_id: uuid.UUID, **extra: Any) -> HTMLResponse:
    assistant = _assistant(request)
    services: Services = request.app.state.services
    try:
        project = assistant.projects.get(project_id)
    except KeyError:
        raise HTTPException(404, "Projet inconnu") from None
    return _render(
        request,
        "project.html",
        project=project,
        pending=assistant.projects.pending_decision(project_id),
        history=assistant.projects.decisions(project_id),
        board=assistant.projects.dashboard(project_id, date.today()),
        approaches=[a for a in Approach if a is not Approach.UNDECIDED],
        labels=APPROACH_LABELS,
        agents=[a for a in services.catalog.all_agents() if a.id not in CHAT_EXCLUDED],
        **extra,
    )
