"""Adoption d'un skill par défaut du catalogue : lancée par un humain seulement.

python -m boussole.platform.settings_store.cli adopt-default selector

Le changement est journalisé AVANT son effet (échec fermé, comme la page Paramètres),
puis versé à l'historique du skill : le retour arrière se fait depuis Paramètres.
"""

import argparse
import sys
import uuid
from typing import Protocol

from boussole.api.services import build_services
from boussole.config import load_config
from boussole.core.enums import ActionClass
from boussole.platform.audit.log import AuditEvent, MissingSigningKeyError
from boussole.platform.settings_store.repository import SettingsRepository


class Journal(Protocol):
    def append(self, event: AuditEvent) -> int: ...


def adopt_default(
    repo: SettingsRepository, audit: Journal | None, agent_id: str, operator: str
) -> int:
    spec = repo.catalog.get(agent_id)
    current = repo.current_skill(agent_id)
    if not repo.default_pending(agent_id):
        print(f"{agent_id} : le skill par défaut v{spec.skill_version} s'applique déjà.")
        return 0
    if audit is None:
        print("Journal d'audit indisponible : aucun changement.", file=sys.stderr)
        return 2
    details: dict[str, object] = {
        "by": operator,
        "agent": agent_id,
        "catalog_version": spec.skill_version,
        "replaces_version": current.version,
    }
    event = AuditEvent(
        uuid.uuid4(),
        f"humain:{operator}",
        "settings.skill.adopt_default",
        ActionClass.REVERSIBLE_WRITE,
        None,
        details,
    )
    try:
        audit.append(event)
    except MissingSigningKeyError as exc:
        print(f"{exc} Aucun changement.", file=sys.stderr)
        return 2
    for view in repo.adopt_default(agent_id, operator):
        print(f"{agent_id} : version {view.version} enregistrée ({view.reason}).")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="boussole-settings")
    commands = parser.add_subparsers(required=True)
    adopt = commands.add_parser(
        "adopt-default", help="Verser le skill par défaut du catalogue à l'historique"
    )
    adopt.add_argument("agent", help="Identifiant de l'agent, par exemple selector")
    args = parser.parse_args(argv)
    config = load_config()
    services = build_services(config)
    try:
        services.catalog.get(args.agent)
    except KeyError:
        print(f"Agent inconnu : {args.agent}", file=sys.stderr)
        return 1
    return adopt_default(services.repo, services.audit, args.agent, config.operator)


if __name__ == "__main__":
    sys.exit(main())
