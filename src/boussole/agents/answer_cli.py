"""Poser une question à un agent : réponse sourcée, coût en $ CA, entrées du journal.

python -m boussole.agents.answer_cli "Qu'est-ce qu'un registre des risques ?" --agent domain.risk

Appel payant (plafond du budget d'essai appliqué). Les extraits du PMBOK ne partent
que vers des fournisseurs sans rétention (ADR 0008).
"""

import argparse
import sys

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from boussole.agents.answer import Answerer, AnswerRefusedError, SourcedAnswer
from boussole.agents.catalog import load_catalog
from boussole.agents.pmbok_skills import load_pmbok_skills
from boussole.config import load_config
from boussole.core.models import Base
from boussole.platform.audit.log import AuditLog, MissingSigningKeyError, create_audit_table
from boussole.platform.guardrails.gate import ActionGate
from boussole.platform.guardrails.policy import load_policy
from boussole.platform.llm_gateway.budget import BudgetedGateway, BudgetExceededError
from boussole.platform.llm_gateway.openrouter import OpenRouterGateway
from boussole.platform.llm_gateway.port import GatewayError
from boussole.platform.memory_rag.cli import memory
from boussole.platform.secrets import OPENROUTER_KEY, KeyringSecretStore
from boussole.platform.settings_store.models import SETTINGS_TABLES
from boussole.platform.settings_store.repository import SettingsRepository, SqlUsageLedger


class MissingApiKeyError(RuntimeError):
    """La clé OpenRouter se saisit dans la page Paramètres."""


def build_answerer() -> Answerer:
    config = load_config()
    engine = create_engine(config.database_url)
    if config.is_lightweight:
        Base.metadata.create_all(engine, tables=list(SETTINGS_TABLES))
        create_audit_table(engine)
    sessions = sessionmaker(engine, expire_on_commit=False)
    catalog = load_catalog(config.catalog_path)
    pmbok = load_pmbok_skills(config.pmbok_skills_path)
    secrets = KeyringSecretStore()
    key = secrets.get(OPENROUTER_KEY)
    if not key:
        raise MissingApiKeyError("Clé OpenRouter absente : saisis-la dans la page Paramètres.")
    gateway = BudgetedGateway(
        OpenRouterGateway(key, config.usd_to_cad), SqlUsageLedger(sessions), config.budget_cap_cad
    )
    return Answerer(
        gate=ActionGate(load_policy(config.autonomy_path), catalog, AuditLog(sessions, secrets)),
        memory=memory(),
        gateway=gateway,
        repo=SettingsRepository(sessions, catalog, pmbok),
        pages_for=pmbok.pages_for,
    )


def render(answer: SourcedAnswer) -> str:
    sources = "\n".join(f"  [{i}] {c}" for i, c in enumerate(answer.citations, start=1))
    cited = ", ".join(f"[{n}]" for n in answer.cited) or "aucune"
    return (
        f"{answer.text}\n\nSources fournies :\n{sources or '  aucune'}\n"
        f"Sources citées : {cited}\n"
        f"Modèle : {answer.model} · coût : {answer.cost_cad} $ CA\n"
        f"Journal : entrées {', '.join(map(str, answer.audit_ids))} "
        f"(corrélation {answer.correlation_id})"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="boussole-ask", description="Réponse sourcée")
    parser.add_argument("question")
    parser.add_argument("--agent", default="selector", help="Identifiant de l'agent")
    parser.add_argument("-k", type=int, default=5, help="Nombre d'extraits fournis")
    args = parser.parse_args(argv)
    try:
        answer = build_answerer().answer(args.agent, args.question, k=args.k)
    except MissingSigningKeyError:
        print(
            "Clé de signature du journal absente : un humain la crée avec "
            "`python -m boussole.platform.audit.cli init-key`.",
            file=sys.stderr,
        )
        return 2
    except (MissingApiKeyError, AnswerRefusedError, BudgetExceededError, GatewayError) as exc:
        print(f"Refusé : {exc}", file=sys.stderr)
        return 1
    print(render(answer))
    return 0


if __name__ == "__main__":
    sys.exit(main())
