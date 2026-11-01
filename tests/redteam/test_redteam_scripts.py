"""Red team du 1er novembre 2026, constat 5 : aucun script tiers sur les pages."""

import base64
import hashlib
import re
from pathlib import Path

from fastapi.testclient import TestClient

from boussole.api.app import STATIC, TEMPLATES, create_app
from boussole.api.services import Services
from tests.integration.test_settings_page import services  # noqa: F401  (fixture)

SCRIPT_SRC = re.compile(r'<script[^>]*\bsrc="([^"]+)"[^>]*>', re.S)


def test_templates_load_no_external_script() -> None:
    for template in Path(TEMPLATES).glob("*.html"):
        for src in SCRIPT_SRC.findall(template.read_text(encoding="utf-8")):
            assert src.startswith("/static/"), f"{template.name} charge {src}"


def test_local_htmx_matches_its_integrity(services: Services) -> None:  # noqa: F811
    base = (Path(TEMPLATES) / "base.html").read_text(encoding="utf-8")
    integrity = re.search(r'integrity="sha384-([^"]+)"', base)
    assert integrity is not None
    body = TestClient(create_app(services)).get("/static/htmx-2.0.3.min.js").content
    assert body == (Path(STATIC) / "htmx-2.0.3.min.js").read_bytes()
    assert base64.b64encode(hashlib.sha384(body).digest()).decode() == integrity.group(1)
