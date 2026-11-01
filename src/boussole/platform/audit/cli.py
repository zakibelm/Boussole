"""Gestion de la clé de signature du journal : lancée par un humain seulement.

python -m boussole.platform.audit.cli init-key
python -m boussole.platform.audit.cli verify
"""

import argparse
import secrets
import sys

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from boussole.config import load_config
from boussole.platform.audit.log import AUDIT_KEY, AuditLog, create_audit_table
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


def _verify(_: argparse.Namespace) -> int:
    config = load_config()
    engine = create_engine(config.database_url)
    if config.is_lightweight:
        create_audit_table(engine)
    report = AuditLog(sessionmaker(engine), KeyringSecretStore()).verify()
    if report.ok:
        print(f"Journal intègre : {report.entries} entrées vérifiées.")
        return 0
    print(f"Journal ALTÉRÉ à l'entrée {report.first_broken_id} : {report.reason}.", file=sys.stderr)
    return 3


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="boussole-audit")
    commands = parser.add_subparsers(required=True)
    commands.add_parser("init-key", help="Créer la clé de signature (une seule fois)").set_defaults(
        run=_init_key
    )
    commands.add_parser("verify", help="Vérifier chaînage et signatures").set_defaults(run=_verify)
    args = parser.parse_args(argv)
    code: int = args.run(args)
    return code


if __name__ == "__main__":
    sys.exit(main())
