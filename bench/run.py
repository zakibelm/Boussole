"""Benchmark reproductible des modèles sur les tâches PMO (CLAUDE.md, principe 3).

    uv run python -m bench.run --dry-run                 # modèle factice, gratuit
    uv run python -m bench.run --estimate --models a,b   # coût estimé, aucun appel payant
    uv run python -m bench.run --models a,b              # appels payants, plafonnés

Chaque appel payant passe par le plafond de budget (BOUSSOLE_BUDGET_CAP_CAD) et
est inscrit au registre des coûts. Les résultats sont écrits dans bench/results/.
"""

import argparse
import json
import statistics
import sys
import time
import uuid
from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from decimal import Decimal
from functools import partial
from pathlib import Path

from bench.tasks import SUITES, TASKS, Task
from boussole.agents.catalog import Catalog, load_catalog
from boussole.config import AppConfig, load_config
from boussole.platform.llm_gateway.budget import (
    BudgetedGateway,
    BudgetExceededError,
    InMemoryLedger,
    UsageLedger,
)
from boussole.platform.llm_gateway.fake import FakeGateway
from boussole.platform.llm_gateway.openrouter import OpenRouterGateway
from boussole.platform.llm_gateway.port import (
    GatewayError,
    GenerationRequest,
    GenerationResult,
    LLMGateway,
    Message,
)
from boussole.platform.secrets import OPENROUTER_KEY, KeyringSecretStore

RESULTS = Path(__file__).resolve().parent / "results"
CHARS_PER_TOKEN = 4
EXPECTED_OUTPUT_SHARE = Decimal("0.5")  # part de max_tokens générée, raisonnement compris (prudent)
TIE_MARGIN = 0.05
RETRY_PAUSES_S = (2.0, 6.0)  # deux nouvelles tentatives si OpenRouter est injoignable
MAX_NETWORK_FAILURES = 5


@dataclass(frozen=True)
class Row:
    model: str
    task: str
    item: str
    score: float
    cost_cad: str
    latency_s: float
    answer: str
    error: str | None


def system_prompt(catalog: Catalog, agent_id: str) -> str:
    return f"{catalog.shared_rules.strip()}\n\n{catalog.get(agent_id).skill.strip()}"


class NetworkDownError(RuntimeError):
    """Trop d'échecs réseau d'affilée : on arrête plutôt que d'enchaîner les erreurs."""


def run_model(
    gateway: BudgetedGateway, catalog: Catalog, model: str, suite: str = "base"
) -> list[Row]:
    rows: list[Row] = []
    failures_in_a_row = 0
    for task in TASKS:
        system = system_prompt(catalog, task.agent_id)
        for item in task.items(suite):
            row = _with_retries(partial(_run_item, gateway, task, item, model, system))
            rows.append(row)
            failures_in_a_row = failures_in_a_row + 1 if _network(row) else 0
            if failures_in_a_row >= MAX_NETWORK_FAILURES:
                raise NetworkDownError(f"OpenRouter injoignable ({model}), exécution arrêtée.")
    return rows


def _with_retries(attempt: Callable[[], Row]) -> Row:
    row = attempt()
    for pause in RETRY_PAUSES_S:
        if not _network(row):
            break
        time.sleep(pause)
        row = attempt()
    return row


def _network(row: Row) -> bool:
    return bool(row.error and "injoignable" in row.error)


def _run_item(
    gateway: BudgetedGateway, task: Task, item: dict[str, object], model: str, system: str
) -> Row:
    request = GenerationRequest(
        model=model,
        messages=(Message("system", system), Message("user", task.prompt(item))),
        temperature=0.0,
        max_tokens=task.max_tokens,
    )
    started = time.perf_counter()
    try:
        result = gateway.generate(request, agent=f"bench:{task.name}")
    except GatewayError as exc:
        elapsed = time.perf_counter() - started
        return Row(model, task.name, str(item["id"]), 0.0, "0", round(elapsed, 3), "", str(exc))
    elapsed = time.perf_counter() - started
    error = _answer_problem(result)
    score = 0.0 if error else task.score(item, result.text)
    cost = str(result.usage.cost_cad)
    return Row(
        model, task.name, str(item["id"]), score, cost, round(elapsed, 3), result.text, error
    )


def _answer_problem(result: GenerationResult) -> str | None:
    """Une réponse tronquée ou vide est une erreur signalée, pas un simple zéro."""
    if result.truncated:
        return "réponse tronquée (limite de jetons atteinte, raisonnement compris)"
    if not result.text.strip():
        return f"réponse vide (fin : {result.finish_reason})"
    return None


def summarize(rows: list[Row]) -> dict[str, dict[str, float]]:
    summary: dict[str, dict[str, float]] = {}
    for model in sorted({r.model for r in rows}):
        mine = [r for r in rows if r.model == model]
        latencies = sorted(r.latency_s for r in mine)
        stats = {t.name: statistics.fmean(r.score for r in mine if r.task == t.name) for t in TASKS}
        stats["global"] = statistics.fmean(r.score for r in mine)
        stats["cost_cad"] = float(sum(Decimal(r.cost_cad) for r in mine))
        stats["latency_mean_s"] = statistics.fmean(latencies)
        stats["latency_p95_s"] = latencies[max(0, int(len(latencies) * 0.95) - 1)]
        stats["errors"] = float(sum(r.error is not None for r in mine))
        summary[model] = stats
    return summary


def recommend(summary: dict[str, dict[str, float]]) -> str:
    """Meilleure justesse globale; à moins de 0,05 du meilleur, le moins cher l'emporte."""
    best = max(s["global"] for s in summary.values())
    close = [m for m, s in summary.items() if best - s["global"] <= TIE_MARGIN]
    return min(close, key=lambda m: (summary[m]["cost_cad"], -summary[m]["global"]))


def estimate_cost_cad(
    gateway: LLMGateway, catalog: Catalog, models: list[str], suite: str = "base"
) -> dict[str, Decimal]:
    prices = {m.id: m for m in gateway.list_models()}
    estimates: dict[str, Decimal] = {}
    for model in models:
        info = prices.get(model)
        if info is None:
            raise SystemExit(f"Modèle inconnu d'OpenRouter : {model}")
        total = Decimal(0)
        for task in TASKS:
            system = system_prompt(catalog, task.agent_id)
            for item in task.items(suite):
                prompt_tokens = Decimal(len(system) + len(task.prompt(item))) / CHARS_PER_TOKEN
                output_tokens = task.max_tokens * EXPECTED_OUTPUT_SHARE
                total += (
                    prompt_tokens * info.prompt_cad_per_mtok
                    + output_tokens * info.completion_cad_per_mtok
                ) / Decimal(1_000_000)
        estimates[model] = total.quantize(Decimal("0.0001"))
    return estimates


def write_results(
    rows: list[Row], summary: dict[str, dict[str, float]], label: str, suite: str = "base"
) -> Path:
    RESULTS.mkdir(exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    path = RESULTS / f"{stamp}-{label}.json"
    payload = {
        "run_at": stamp,
        "label": label,
        "suite": suite,
        "tasks": {t.name: {"agent": t.agent_id, "items": len(t.items(suite))} for t in TASKS},
        "summary": summary,
        "recommended_default": recommend(summary),
        "rows": [asdict(r) for r in rows],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def render_table(summary: dict[str, dict[str, float]]) -> str:
    header = (
        "| Modèle | Statut | Risques | Approche | Global | Coût ($ CA) "
        "| Latence moy. (s) | p95 (s) | Erreurs |"
    )
    lines = [header, "|" + "---|" * 9]
    for model, s in sorted(summary.items(), key=lambda kv: -kv[1]["global"]):
        lines.append(
            f"| {model} | {s['status']:.2f} | {s['risks']:.2f} | {s['approach']:.2f} | "
            f"{s['global']:.2f} | {s['cost_cad']:.4f} | {s['latency_mean_s']:.2f} | "
            f"{s['latency_p95_s']:.2f} | {int(s['errors'])} |"
        )
    return "\n".join(lines)


def _real_gateway(config: AppConfig) -> OpenRouterGateway:
    key = KeyringSecretStore().get(OPENROUTER_KEY)
    if not key:
        raise SystemExit("Aucune clé OpenRouter : enregistre-la dans la page Paramètres.")
    return OpenRouterGateway(key, config.usd_to_cad)


def _ledger(config: AppConfig) -> UsageLedger:
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from boussole.core.models import Base
    from boussole.platform.settings_store.models import SETTINGS_TABLES
    from boussole.platform.settings_store.repository import SqlUsageLedger

    engine = create_engine(config.database_url)
    if config.is_lightweight:
        Base.metadata.create_all(engine, tables=list(SETTINGS_TABLES))
    return SqlUsageLedger(sessionmaker(engine))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="bench", description="Benchmark PMO de Boussole")
    parser.add_argument(
        "--models", default="", help="Identifiants OpenRouter séparés par des virgules"
    )
    parser.add_argument("--dry-run", action="store_true", help="Modèle factice, aucun appel payant")
    parser.add_argument("--estimate", action="store_true", help="Coût estimé seulement")
    parser.add_argument("--suite", choices=SUITES, default="base", help="Jeu de cas")
    args = parser.parse_args(argv)
    config = load_config()
    catalog = load_catalog(config.catalog_path)

    if args.dry_run:
        models = ["fake/small", "fake/large"]
        gateway = BudgetedGateway(FakeGateway(tuple(models)), InMemoryLedger(), Decimal("1"))
        label = "dry-run"
    else:
        models = [m.strip() for m in args.models.split(",") if m.strip()]
        if len(models) < 2:
            raise SystemExit("Indique au moins deux modèles avec --models.")
        real = _real_gateway(config)
        if args.estimate:
            for model, cost in estimate_cost_cad(real, catalog, models, args.suite).items():
                print(f"{model} : environ {cost} $ CA")
            return 0
        gateway = BudgetedGateway(real, _ledger(config), config.budget_cap_cad)
        label = f"{args.suite}-{uuid.uuid4().hex[:6]}"

    rows: list[Row] = []
    try:
        for model in models:
            rows.extend(run_model(gateway, catalog, model, args.suite))
    except (BudgetExceededError, NetworkDownError) as exc:
        print(f"Arrêt : {exc}", file=sys.stderr)
    if not rows:
        return 1
    summary = summarize(rows)
    path = write_results(rows, summary, label, args.suite)
    print(render_table(summary))
    print(f"\nModèle par défaut recommandé : {recommend(summary)}")
    print(f"Résultats : {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
