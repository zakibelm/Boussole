"""Commande de la clé de signature : création unique, vérification du journal."""

import pytest

from boussole.platform.audit import cli
from boussole.platform.audit.log import AUDIT_KEY
from boussole.platform.secrets import InMemorySecretStore


@pytest.fixture
def store(monkeypatch: pytest.MonkeyPatch, tmp_path: object) -> InMemorySecretStore:
    memory = InMemorySecretStore()
    monkeypatch.setattr(cli, "KeyringSecretStore", lambda: memory)
    monkeypatch.setenv("BOUSSOLE_DATABASE_URL", "sqlite://")
    return memory


def test_init_key_creates_a_256_bit_key_once(store: InMemorySecretStore) -> None:
    assert cli.main(["init-key"]) == 0
    key = store.get(AUDIT_KEY)
    assert key is not None and len(bytes.fromhex(key)) == 32
    assert cli.main(["init-key"]) == 1
    assert store.get(AUDIT_KEY) == key


def test_verify_reports_an_intact_empty_log(
    store: InMemorySecretStore, capsys: pytest.CaptureFixture[str]
) -> None:
    cli.main(["init-key"])
    assert cli.main(["verify"]) == 0
    assert "Journal intègre : 0 entrées" in capsys.readouterr().out
