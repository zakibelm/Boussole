"""Gestion de la clé de signature du journal : lancée par un humain seulement.

python -m boussole.platform.audit.cli init-key
python -m boussole.platform.audit.cli verify
python -m boussole.platform.audit.cli resume --reason "…"
"""

import argparse
import secrets
import sys
import uuid

from sqlalchemy.orm import sessionmaker

from boussole.config import load_config
from boussole.core.database import make_engine
from boussole.core.enums import ActionClass
from boussole.platform.audit.log import (
    AUDIT_KEY,
    RESUME_ACTION,
    AuditEvent,
    AuditLog,
    create_audit_table,
)
from boussole.platform.secrets import KeyringSecretStore


def _init_key(_: argparse.Namespace) -> int:
    store = KeyringSecretStore()
    if store.get(AUDIT_KEY):
        print(
            "Une clé existe déjà : la remplacer rendrait le journal invérifiable.", file=sys.stderr
        )
        return 1
    store.set(AUDIT_KEY, secrets.token_hex(32))
    print("Clé de signature créée dans le trousseau du système (boussole), jamais affichée.")
    return 0


def _audit() -> AuditLog:
    config = load_config()
    engine = make_engine(config.database_url)
    if config.is_lightweight:
        create_audit_table(engine)
    return AuditLog(sessionmaker(engine), KeyringSecretStore())


def _verify(_: argparse.Namespace) -> int:
    report = _audit().verify()
    if report.ok:
        forks = report.documented_forks
        note = f" (embranchements documentés : {list(forks)})" if forks else ""
        print(f"Journal intègre : {report.entries} entrées vérifiées{note}.")
        return 0
    print(f"Journal ALTÉRÉ à l'entrée {report.first_broken_id} : {report.reason}.", file=sys.stderr)
    return 3


def _resume(args: argparse.Namespace) -> int:
    """Documente, par une entrée signée, des embranchements dus à des écritures
    simultanées. Ne modifie ni ne supprime aucune entrée."""
    audit = _audit()
    forks = audit.forks()
    if not forks:
        print("Aucun embranchement à documenter.")
        return 0
    operator = load_config().operator
    event = AuditEvent(
        uuid.uuid4(),
        f"humain:{operator}",
        RESUME_ACTION,
        ActionClass.READ,
        None,
        {"forks": forks, "reason": args.reason, "by": operator},
    )
    entry = audit.append(event)
    print(f"Reprise signée (entrée {entry}) pour les embranchements {forks}.")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="boussole-audit")
    commands = parser.add_subparsers(required=True)
    commands.add_parser("init-key", help="Créer la clé de signature (une seule fois)").set_defaults(
        run=_init_key
    )
    commands.add_parser("verify", help="Vérifier chaînage et signatures").set_defaults(run=_verify)
    resume = commands.add_parser("resume", help="Documenter des embranchements (humain)")
    resume.add_argument("--reason", required=True, help="Cause de l'incident")
    resume.set_defaults(run=_resume)
    args = parser.parse_args(argv)
    code: int = args.run(args)
    return code


if __name__ == "__main__":
    sys.exit(main())
