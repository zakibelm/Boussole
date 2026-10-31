"""Serveur OpenRouter simulé : aucune requête réseau, aucun coût."""

import json
from typing import Any

import httpx

COST_USD = 0.001


def _chat(payload: dict[str, Any]) -> dict[str, Any]:
    last = payload["messages"][-1]["content"]
    message: dict[str, Any] = {"role": "assistant", "content": f"[{payload['model']}] {last}"}
    if "response_format" in payload:
        message["content"] = json.dumps({"ok": True})
    if payload.get("tools"):
        name = payload["tools"][0]["function"]["name"]
        message["tool_calls"] = [
            {"type": "function", "function": {"name": name, "arguments": "{}"}}
        ]
    usage = {"prompt_tokens": 10, "completion_tokens": 5, "cost": COST_USD}
    choice = {"message": message, "finish_reason": "stop"}
    return {"model": payload["model"], "choices": [choice], "usage": usage}


def _embeddings(payload: dict[str, Any]) -> dict[str, Any]:
    data = [{"embedding": [0.1, 0.2, 0.3]} for _ in payload["input"]]
    return {"data": data, "usage": {"prompt_tokens": 3, "cost": 0}}


_MODELS = {
    "data": [
        {
            "id": "anthropic/claude-sonnet-5.5",
            "name": "Claude Sonnet 5.5",
            "context_length": 200000,
            "pricing": {"prompt": "0.000003", "completion": "0.000015"},
        }
    ]
}


def handler(request: httpx.Request) -> httpx.Response:
    if request.headers.get("Authorization") != "Bearer sk-or-test":
        return httpx.Response(401, json={"error": {"message": "No auth credentials found"}})
    path = request.url.path.removeprefix("/api/v1")
    if path == "/models":
        return httpx.Response(200, json=_MODELS)
    if path == "/key":
        return httpx.Response(200, json={"data": {"label": "test", "limit": None, "usage": 0}})
    payload = json.loads(request.content)
    body = _chat(payload) if path == "/chat/completions" else _embeddings(payload)
    return httpx.Response(200, json=body)


def transport() -> httpx.MockTransport:
    return httpx.MockTransport(handler)
