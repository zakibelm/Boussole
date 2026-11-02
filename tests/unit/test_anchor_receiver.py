"""infra/anchor-receiver/Code.gs : jeton lu dans le corps du POST, jamais versionné.

Les contrôles statiques tournent partout; le comportement est vérifié avec Node (présent
sur les exécuteurs de la CI), en remplaçant les services Google par des doubles.
"""

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

CODE = Path(__file__).resolve().parents[2] / "infra" / "anchor-receiver" / "Code.gs"
ANCHOR = "63:" + "ab" * 32
TOKEN = "jeton_" + "x" * 24  # valeur de test, faible entropie (gitleaks)

HARNESS = """
const rows = [];
const sheet = { appendRow: (r) => rows.push(r), setFrozenRows: () => {} };
globalThis.SpreadsheetApp = { getActiveSpreadsheet: () => ({
  getSheetByName: () => sheet, insertSheet: () => sheet }) };
globalThis.LockService = { getScriptLock: () => ({ waitLock: () => {}, releaseLock: () => {} }) };
globalThis.ContentService = { MimeType: { TEXT: 'text' },
  createTextOutput: (m) => ({ setMimeType: () => m }) };
%(code)s
const cases = %(cases)s;
const out = cases.map((c) => doPost(c === null ? undefined : { postData: { contents: c } }));
console.log(JSON.stringify({ out, rows: rows.length }));
"""


def _source(token: str | None = None) -> str:
    code = CODE.read_text(encoding="utf-8")
    if token is not None:
        code = code.replace("const JETON = '<à définir>';", f"const JETON = '{token}';", 1)
    return code


def _body(**changes: str) -> str:
    body = {"token": TOKEN, "anchor": ANCHOR, "host": "srv1", "at": "2026-11-02T02:15:00Z"}
    body.update(changes)
    return json.dumps(body)


def _post(code: str, cases: list[str | None]) -> dict[str, object]:
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node absent : comportement vérifié dans la CI")
    script = HARNESS % {"code": code, "cases": json.dumps(cases)}
    result = subprocess.run(  # noqa: S603
        [node, "-e", script], capture_output=True, text=True, check=True
    )
    return json.loads(result.stdout)  # type: ignore[no-any-return]


def test_versioned_script_holds_only_the_placeholder() -> None:
    code = _source()
    assert re.findall(r"const JETON = '([^']*)';", code) == ["<à définir>"]


def test_token_is_never_read_from_the_url() -> None:
    code = _source()
    assert "doGet" not in code and "e.parameter" not in code
    assert "e.postData.contents" in code


def test_valid_anchor_is_written() -> None:
    assert _post(_source(TOKEN), [_body()]) == {"out": ["ok"], "rows": 1}


def test_placeholder_token_refuses_everything() -> None:
    body = _body(token="<à définir>")  # noqa: S106 (valeur de remplacement)
    assert _post(_source(), [body]) == {"out": ["refusé"], "rows": 0}


@pytest.mark.parametrize(
    "body",
    [
        None,
        "pas du json",
        _body(token="mauvais_" + "y" * 20),
        _body(anchor="63:=HYPERLINK(1)"),
        _body(host="=IMPORTXML(1)"),
        _body(at="hier"),
    ],
)
def test_invalid_posts_are_refused(body: str | None) -> None:
    assert _post(_source(TOKEN), [body]) == {"out": ["refusé"], "rows": 0}
