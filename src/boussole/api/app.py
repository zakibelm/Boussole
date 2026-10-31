"""Application web de Boussole : une seule API pour tous les canaux."""

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from boussole.api import settings_routes
from boussole.api.services import Services, build_services
from boussole.config import load_config

TEMPLATES = Path(__file__).resolve().parents[1] / "ui" / "templates"


def create_app(services: Services) -> FastAPI:
    app = FastAPI(title="Boussole", docs_url=None, redoc_url=None)
    app.state.services = services
    app.state.templates = Jinja2Templates(directory=TEMPLATES)
    app.include_router(settings_routes.router)

    @app.get("/", include_in_schema=False)
    def home() -> RedirectResponse:
        return RedirectResponse("/settings")

    return app


def app_factory() -> FastAPI:
    """Point d'entrée d'uvicorn : `uvicorn --factory boussole.api.app:app_factory`."""
    return create_app(build_services(load_config()))
