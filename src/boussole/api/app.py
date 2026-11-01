"""Application web de Boussole : une seule API pour tous les canaux."""

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.exceptions import HTTPException

from boussole.api import project_routes, settings_routes
from boussole.api.csrf import SameOriginMiddleware
from boussole.api.services import Services, build_services
from boussole.config import load_config
from boussole.ui import markdown

TEMPLATES = Path(__file__).resolve().parents[1] / "ui" / "templates"
# Scripts servis par Boussole même : aucun CDN tiers sur les pages (clé API comprise).
STATIC = Path(__file__).resolve().parents[1] / "ui" / "static"


def create_app(services: Services, allowed_origins: frozenset[str] = frozenset()) -> FastAPI:
    app = FastAPI(title="Boussole", docs_url=None, redoc_url=None)
    app.add_middleware(SameOriginMiddleware, allowed_origins=allowed_origins)
    app.state.services = services
    app.state.templates = Jinja2Templates(directory=TEMPLATES)
    app.state.templates.env.filters["md"] = markdown.render
    app.mount("/static", StaticFiles(directory=STATIC), name="static")
    app.include_router(settings_routes.router)
    app.include_router(project_routes.router)

    @app.get("/", include_in_schema=False)
    def home() -> RedirectResponse:
        return RedirectResponse("/projects")

    @app.exception_handler(HTTPException)
    async def http_error(request: Request, exc: HTTPException) -> HTMLResponse:
        return _error_page(request, exc.status_code, str(exc.detail))

    @app.exception_handler(RequestValidationError)
    async def invalid_request(request: Request, _: RequestValidationError) -> HTMLResponse:
        return _error_page(
            request, 422, "Requête invalide : un champ manque ou n'a pas le bon format."
        )

    return app


def _error_page(request: Request, status: int, message: str) -> HTMLResponse:
    titles = {404: "Introuvable", 403: "Refusé", 422: "Requête invalide"}
    templates: Jinja2Templates = request.app.state.templates
    services: Services = request.app.state.services
    context = {
        "status": status,
        "title": titles.get(status, "Erreur"),
        "message": message,
        "operator": services.operator_for(request),
    }
    return templates.TemplateResponse(request, "error.html", context, status_code=status)


def app_factory() -> FastAPI:
    """Point d'entrée d'uvicorn : `uvicorn --factory boussole.api.app:app_factory`."""
    config = load_config()
    return create_app(build_services(config), config.allowed_origins)
