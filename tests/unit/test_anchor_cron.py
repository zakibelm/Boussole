"""infra/anchor-cron.sh : l'ancre part hors du serveur, sinon cron est prévenu (revue 3).

`docker` et `curl` sont remplacés par des doubles; aucun réseau, aucun conteneur.
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "infra" / "anchor-cron.sh"
ANCHOR = "63:" + "ab" * 32

pytestmark = pytest.mark.skipif(
    sys.platform == "win32", reason="script bash, testé sous Linux (CI)"
)


def _run(tmp_path: Path, url: str | None, curl_code: int = 0) -> subprocess.CompletedProcess[str]:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(exist_ok=True)
    (bin_dir / "docker").write_text(
        "#!/bin/sh\n"
        "echo 'Ancre signée (entrée 63). À conserver HORS du serveur :'\n"
        f"echo '{ANCHOR}'\n"
    )
    (bin_dir / "curl").write_text(
        f'#!/bin/sh\nprintf "%s\\n" "$@" > "{tmp_path}/curl_args"\nexit {curl_code}\n'
    )
    for tool in ("docker", "curl"):
        (bin_dir / tool).chmod(0o755)
    env = {
        "PATH": f"{bin_dir}:{os.environ['PATH']}",
        "BOUSSOLE_HOME": str(tmp_path / "absent"),
    }
    if url is not None:
        env["BOUSSOLE_ANCHOR_URL"] = url
    bash = shutil.which("bash") or "/bin/bash"
    return subprocess.run(  # noqa: S603
        [bash, str(SCRIPT)], env=env, capture_output=True, text=True, check=False
    )


def test_anchor_is_posted_over_https(tmp_path: Path) -> None:
    result = _run(tmp_path, "https://ancres.example/boussole")
    assert result.returncode == 0, result.stderr
    args = (tmp_path / "curl_args").read_text()
    assert "https://ancres.example/boussole" in args and ANCHOR in args


@pytest.mark.parametrize("url", [None, "", "http://ancres.example"])
def test_missing_or_insecure_url_fails_so_cron_warns(tmp_path: Path, url: str | None) -> None:
    result = _run(tmp_path, url)
    assert result.returncode != 0
    assert ANCHOR in result.stdout  # l'ancre est créée et visible malgré tout


def test_failed_post_fails_so_cron_warns(tmp_path: Path) -> None:
    result = _run(tmp_path, "https://ancres.example/boussole", curl_code=22)
    assert result.returncode == 4
    assert "impossible" in result.stderr
