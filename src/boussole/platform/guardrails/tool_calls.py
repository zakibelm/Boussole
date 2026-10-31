"""Appels d'outil proposés par un modèle : chacun passe par le portail.

Un modèle ne déclenche jamais un effet directement. Si son contexte contenait
un contenu externe, toute action proposée en porte la trace (`external_sources`)
et exige donc une confirmation humaine.
"""

import uuid
from collections.abc import Callable, Mapping
from typing import Any

from boussole.platform.guardrails.gate import ActionGate, GateResult
from boussole.platform.guardrails.policy import ActionRequest
from boussole.platform.llm_gateway.port import ToolCall

Handler = Callable[[dict[str, Any]], object]


def run_tool_calls(
    gate: ActionGate,
    agent_id: str,
    project_id: uuid.UUID | None,
    calls: tuple[ToolCall, ...],
    handlers: Mapping[str, Handler],
    external_sources: tuple[str, ...],
    correlation_id: uuid.UUID,
) -> list[GateResult[object]]:
    results: list[GateResult[object]] = []
    for call in calls:
        handler = handlers.get(call.name)
        request = ActionRequest(
            action=call.name,
            agent_id=agent_id,
            project_id=project_id,
            target_project_id=_target(call.arguments, project_id),
            destination=_str_or_none(call.arguments.get("destination")),
            external_sources=external_sources,
            payload={"arguments": sorted(call.arguments)},
        )
        results.append(gate.act(request, _bind(handler, call.arguments), correlation_id))
    return results


def _bind(handler: Handler | None, arguments: dict[str, Any]) -> Callable[[], object]:
    def run() -> object:
        if handler is None:
            raise LookupError("Aucun gestionnaire pour cette action.")
        return handler(arguments)

    return run


def _target(arguments: dict[str, Any], default: uuid.UUID | None) -> uuid.UUID | None:
    raw = arguments.get("project_id")
    return uuid.UUID(str(raw)) if raw else default


def _str_or_none(value: object) -> str | None:
    return str(value) if value else None
