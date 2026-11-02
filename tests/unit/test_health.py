"""Sonde de santé du conteneur : répond sans données ni appel externe."""

from fastapi.testclient import TestClient

from boussole.api.app import create_app
from boussole.api.services import Services
from tests.integration.test_settings_page import services  # noqa: F401  (fixture)


def test_health_answers_ok_without_data(services: Services) -> None:  # noqa: F811
    response = TestClient(create_app(services)).get("/health")
    assert (response.status_code, response.text) == (200, "ok")
