"""Protection CSRF. Le site est protégé par l'authentification HTTP de nginx, que le
navigateur renvoie d'office : une page tierce pourrait donc soumettre un formulaire
(valider une décision) au nom de l'opérateur. Toute requête qui modifie quelque
chose doit venir de Boussole même.

Les navigateurs envoient toujours `Origin` (et `Sec-Fetch-Site`) sur un POST venu
d'un autre site; une requête sans ces en-têtes ne vient pas d'un navigateur piégé
(ligne de commande, tests) et reste soumise à l'authentification de nginx.
"""

from collections.abc import Awaitable, Callable, MutableMapping
from typing import Any
from urllib.parse import urlsplit

from starlette.responses import PlainTextResponse

Scope = MutableMapping[str, Any]
Receive = Callable[[], Awaitable[MutableMapping[str, Any]]]
Send = Callable[[MutableMapping[str, Any]], Awaitable[None]]
ASGIApp = Callable[[Scope, Receive, Send], Awaitable[None]]

SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})
REFUSAL = "Requête refusée : elle ne vient pas de Boussole (protection CSRF)."


class SameOriginMiddleware:
    def __init__(self, app: ASGIApp, allowed_origins: frozenset[str] = frozenset()) -> None:
        self._app = app
        self._allowed = {_netloc(o) for o in allowed_origins}

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http" and scope["method"] not in SAFE_METHODS:
            headers = {
                k.decode("latin-1").lower(): v.decode("latin-1") for k, v in scope["headers"]
            }
            if not self._same_origin(headers):
                await PlainTextResponse(REFUSAL, status_code=403)(scope, receive, send)
                return
        await self._app(scope, receive, send)

    def _same_origin(self, headers: dict[str, str]) -> bool:
        if headers.get("sec-fetch-site") in ("cross-site", "same-site"):
            return False
        origin = headers.get("origin") or headers.get("referer")
        if origin is None:
            return True
        # X-Forwarded-Host n'est pas pris : il viendrait du client. Derrière nginx,
        # l'origine publique est déclarée dans BOUSSOLE_ALLOWED_ORIGINS.
        hosts = {(headers.get("host") or "").lower()} | self._allowed
        return _netloc(origin) in hosts - {""}


def _netloc(url: str) -> str:
    return urlsplit(url).netloc.lower()
