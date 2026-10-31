"""Coffre de secrets : la clé API reste hors du dépôt, de la base et des journaux."""

from typing import Protocol

import keyring
import keyring.errors

SERVICE = "boussole"
OPENROUTER_KEY = "openrouter_api_key"


class SecretStore(Protocol):
    def get(self, name: str) -> str | None: ...

    def set(self, name: str, value: str) -> None: ...

    def delete(self, name: str) -> None: ...


class KeyringSecretStore:
    """Gestionnaire d'identifiants de Windows (ou trousseau du système)."""

    def get(self, name: str) -> str | None:
        return keyring.get_password(SERVICE, name)

    def set(self, name: str, value: str) -> None:
        keyring.set_password(SERVICE, name, value)

    def delete(self, name: str) -> None:
        try:
            keyring.delete_password(SERVICE, name)
        except keyring.errors.PasswordDeleteError:
            return


class InMemorySecretStore:
    def __init__(self) -> None:
        self._values: dict[str, str] = {}

    def get(self, name: str) -> str | None:
        return self._values.get(name)

    def set(self, name: str, value: str) -> None:
        self._values[name] = value

    def delete(self, name: str) -> None:
        self._values.pop(name, None)


def mask(secret: str | None) -> str | None:
    """Ne montre que les quatre derniers caractères."""
    if not secret:
        return None
    return f"••••{secret[-4:]}"
