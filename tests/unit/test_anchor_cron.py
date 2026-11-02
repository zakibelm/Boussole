"""infra/anchor-cron.sh : l'ancre part hors du serveur, sinon cron est prévenu (revue 3).

Le jeton voyage dans le corps du POST, jamais dans l'adresse; ni l'adresse ni le jeton
n'apparaissent dans la sortie ou les erreurs. `docker` et `curl` sont remplacés par des
doubles; aucun réseau, aucun conteneur.
"""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "infra" / "anchor-cron.sh"
ANCHOR = "63:" + "ab" * 32
URL = "https://script.example/macros/s/secret-deploiement/exec"
TOKEN = "jeton_" + "x" * 24  # valeur de test, faible entropie (gitleaks)

pytestmark = pytest.mark.skipif(
    sys.platform == "win32", reason="script bash, testé sous Linux (CI)"
)

FAKE_CURL = """#!/bin/sh
printf "%s\\n" "$@" > "{d}/curl_args"
while [ $# -gt 0 ]; do
    if [ "$1" = "--config" ]; then cp "$2" "{d}/curl_config"; fi
    shift
done
cat > "{d}/curl_body"
printf "%s" "{response}"
exit {code}
"""


def _run(
    tmp_path: Path,
    url: str | None = URL,
    token: str | None = TOKEN,
    curl_code: int = 0,
    response: str = "ok",
    env_file: str | None = None,
) -> subprocess.CompletedProcess[str]:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(exist_ok=True)
    (bin_dir / "docker").write_text(
        "#!/bin/sh\n"
        "echo 'Ancre signée (entrée 63). À conserver HORS du serveur :'\n"
        f"echo '{ANCHOR}'\n"
    )
    (bin_dir / "curl").write_text(FAKE_CURL.format(d=tmp_path, response=response, code=curl_code))
    for tool in ("docker", "curl"):
        (bin_dir / tool).chmod(0o755)
    home = tmp_path / "home"
    home.mkdir(exist_ok=True)
    if env_file is not None:
        (home / "boussole.env").write_text(env_file)
    tmp_dir = tmp_path / "tmpdir"
    tmp_dir.mkdir(exist_ok=True)
    env = {
        "PATH": f"{bin_dir}:{os.environ['PATH']}",
        "BOUSSOLE_HOME": str(home),
        "TMPDIR": str(tmp_dir),
    }
    if url is not None:
        env["BOUSSOLE_ANCHOR_URL"] = url
    if token is not None:
        env["BOUSSOLE_ANCHOR_TOKEN"] = token
    bash = shutil.which("bash") or "/bin/bash"
    return subprocess.run(  # noqa: S603
        [bash, str(SCRIPT)], env=env, capture_output=True, text=True, check=False
    )


def _assert_nothing_leaks(result: subprocess.CompletedProcess[str]) -> None:
    for secret in (URL, TOKEN, "secret-deploiement"):
        assert secret not in result.stdout and secret not in result.stderr


def test_anchor_and_token_are_posted_in_the_body(tmp_path: Path) -> None:
    result = _run(tmp_path)
    assert result.returncode == 0, result.stderr
    body = json.loads((tmp_path / "curl_body").read_text())
    assert body["token"] == TOKEN and body["anchor"] == ANCHOR
    assert URL in (tmp_path / "curl_config").read_text()
    _assert_nothing_leaks(result)


def test_token_and_url_never_appear_in_curl_arguments(tmp_path: Path) -> None:
    _run(tmp_path)
    args = (tmp_path / "curl_args").read_text()
    assert TOKEN not in args and URL not in args


def test_values_are_read_from_boussole_env(tmp_path: Path) -> None:
    env_file = f"BOUSSOLE_ANCHOR_URL={URL}\nBOUSSOLE_ANCHOR_TOKEN={TOKEN}\n"
    result = _run(tmp_path, url=None, token=None, env_file=env_file)
    assert result.returncode == 0, result.stderr
    assert json.loads((tmp_path / "curl_body").read_text())["token"] == TOKEN


@pytest.mark.parametrize("url", [None, "", "http://ancres.example", f"{URL}?token={TOKEN}"])
def test_missing_insecure_or_parameterised_url_fails(tmp_path: Path, url: str | None) -> None:
    result = _run(tmp_path, url=url)
    assert result.returncode == 3
    assert ANCHOR in result.stdout  # l'ancre est créée et visible malgré tout
    assert not (tmp_path / "curl_args").exists()
    _assert_nothing_leaks(result)


@pytest.mark.parametrize("token", [None, "", "court", 'avec"guillemet-0123456789'])
def test_missing_or_malformed_token_fails(tmp_path: Path, token: str | None) -> None:
    result = _run(tmp_path, token=token)
    assert result.returncode == 3
    assert not (tmp_path / "curl_args").exists()
    _assert_nothing_leaks(result)


def test_failed_post_fails_without_leaking(tmp_path: Path) -> None:
    result = _run(tmp_path, curl_code=22)
    assert result.returncode == 4
    assert "impossible" in result.stderr
    _assert_nothing_leaks(result)


def test_refused_by_receiver_fails(tmp_path: Path) -> None:
    result = _run(tmp_path, response="refusé")
    assert result.returncode == 5
    _assert_nothing_leaks(result)


def test_temporary_config_is_removed(tmp_path: Path) -> None:
    result = _run(tmp_path)
    assert result.returncode == 0, result.stderr
    assert list((tmp_path / "tmpdir").iterdir()) == []
