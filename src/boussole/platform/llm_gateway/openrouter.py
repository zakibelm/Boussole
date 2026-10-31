"""Adaptateur OpenRouter (API compatible OpenAI). Coûts convertis en CAD."""

import json
from decimal import Decimal
from typing import Any

import httpx

from boussole.platform.llm_gateway.port import (
    EmbeddingResult,
    GatewayError,
    GenerationRequest,
    GenerationResult,
    ModelInfo,
    ToolCall,
    Usage,
)

BASE_URL = "https://openrouter.ai/api/v1"
_MILLION = Decimal(1_000_000)


class OpenRouterGateway:
    def __init__(
        self,
        api_key: str,
        usd_to_cad: Decimal,
        transport: httpx.BaseTransport | None = None,
        timeout_s: float = 60.0,
    ) -> None:
        self._rate = usd_to_cad
        self._client = httpx.Client(
            base_url=BASE_URL,
            headers={"Authorization": f"Bearer {api_key}", "X-Title": "Boussole"},
            transport=transport,
            timeout=timeout_s,
        )

    def generate(self, request: GenerationRequest) -> GenerationResult:
        body = self._post("/chat/completions", _chat_body(request))
        message = body["choices"][0]["message"]
        text = message.get("content") or ""
        parsed = json.loads(text) if request.response_schema is not None and text else None
        calls = tuple(_tool_call(c) for c in message.get("tool_calls") or ())
        return GenerationResult(
            text, body.get("model", request.model), self._usage(body), parsed, calls
        )

    def embed(self, model: str, texts: tuple[str, ...]) -> EmbeddingResult:
        body = self._post("/embeddings", {"model": model, "input": list(texts)})
        vectors = tuple(tuple(item["embedding"]) for item in body["data"])
        return EmbeddingResult(vectors, model, self._usage(body))

    def list_models(self) -> tuple[ModelInfo, ...]:
        body = self._get("/models")
        return tuple(self._model_info(m) for m in body["data"])

    def check_key(self) -> dict[str, Any]:
        """Vérifie la clé sans appel payant (GET /key)."""
        data: dict[str, Any] = self._get("/key")["data"]
        return data

    def _usage(self, body: dict[str, Any]) -> Usage:
        usage = body.get("usage") or {}
        cost_usd = Decimal(str(usage.get("cost", 0)))
        return Usage(
            int(usage.get("prompt_tokens", 0)),
            int(usage.get("completion_tokens", 0)),
            (cost_usd * self._rate).quantize(Decimal("0.000001")),
        )

    def _model_info(self, raw: dict[str, Any]) -> ModelInfo:
        pricing = raw.get("pricing") or {}
        return ModelInfo(
            id=raw["id"],
            name=raw.get("name", raw["id"]),
            context_length=int(raw.get("context_length") or 0),
            prompt_cad_per_mtok=self._per_mtok(pricing.get("prompt")),
            completion_cad_per_mtok=self._per_mtok(pricing.get("completion")),
        )

    def _per_mtok(self, usd_per_token: str | None) -> Decimal:
        price = Decimal(usd_per_token or "0") * _MILLION * self._rate
        return price.quantize(Decimal("0.01"))

    def _get(self, path: str) -> dict[str, Any]:
        return _checked(self._safe(lambda: self._client.get(path)))

    def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        return _checked(self._safe(lambda: self._client.post(path, json=payload)))

    @staticmethod
    def _safe(call: Any) -> httpx.Response:
        try:
            response: httpx.Response = call()
        except httpx.HTTPError as exc:
            raise GatewayError(f"OpenRouter injoignable : {type(exc).__name__}") from None
        return response


def _checked(response: httpx.Response) -> dict[str, Any]:
    if response.status_code >= 400:
        raise GatewayError(
            f"OpenRouter a répondu {response.status_code} : {_error_message(response)}"
        )
    body: dict[str, Any] = response.json()
    return body


def _error_message(response: httpx.Response) -> str:
    try:
        return str(response.json()["error"]["message"])[:200]
    except (ValueError, KeyError, TypeError):
        return "erreur inconnue"


def _chat_body(request: GenerationRequest) -> dict[str, Any]:
    body: dict[str, Any] = {
        "model": request.model,
        "messages": [{"role": m.role, "content": m.content} for m in request.messages],
        "temperature": request.temperature,
        "max_tokens": request.max_tokens,
        "usage": {"include": True},
    }
    if request.response_schema is not None:
        body["response_format"] = {
            "type": "json_schema",
            "json_schema": {"name": "result", "strict": True, "schema": request.response_schema},
        }
    if request.tools:
        body["tools"] = [
            {
                "type": "function",
                "function": {
                    "name": t.name,
                    "description": t.description,
                    "parameters": t.parameters,
                },
            }
            for t in request.tools
        ]
    return body


def _tool_call(raw: dict[str, Any]) -> ToolCall:
    function = raw["function"]
    arguments = json.loads(function.get("arguments") or "{}")
    return ToolCall(function["name"], arguments)
