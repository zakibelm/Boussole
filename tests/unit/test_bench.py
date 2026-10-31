"""Notation du benchmark et exécution à blanc (modèle factice)."""

import json
from decimal import Decimal
from pathlib import Path

import pytest
from bench import run
from bench.tasks import TASKS, extract_json

from boussole.agents.catalog import load_catalog
from boussole.platform.llm_gateway.openrouter import OpenRouterGateway
from tests.contract import simulated_openrouter

TASK = {t.name: t for t in TASKS}


def test_datasets_match_the_phase_0_brief() -> None:
    assert len(TASK["approach"].items()) == 10
    assert {i["expected"] for i in TASK["approach"].items()} == {"predictive", "adaptive", "hybrid"}
    assert all(len(TASK[n].items()) >= 5 for n in ("status", "risks"))


def test_extract_json_tolerates_code_fences() -> None:
    assert extract_json('Voici :\n```json\n{"approche": "hybrid"}\n```') == {"approche": "hybrid"}
    assert extract_json("pas de json") is None


@pytest.mark.parametrize(
    ("answer", "expected"),
    [
        ('{"approche": "Hybride", "justification": "x"}', 1.0),
        ('{"approche": "predictive"}', 0.0),
        ("hybride", 0.0),
    ],
)
def test_approach_scoring(answer: str, expected: float) -> None:
    item = next(i for i in TASK["approach"].items() if i["expected"] == "hybrid")
    assert TASK["approach"].score(item, answer) == expected


def test_risk_scoring_rewards_recall_and_valid_scores() -> None:
    item = TASK["risks"].items()[1]  # pluie, acier, inspecteur
    good = [
        {"titre": "Pluie pendant les fondations", "probabilite": 4, "impact": 3},
        {"titre": "Hausse du prix de l'acier", "probabilite": 5, "impact": 4},
        {"titre": "Visite de l'inspecteur non confirmée", "probabilite": 3, "impact": 4},
    ]
    assert TASK["risks"].score(item, json.dumps(good, ensure_ascii=False)) == 1.0
    bad_scale = [{**good[0], "probabilite": 9}]
    assert TASK["risks"].score(item, json.dumps(bad_scale)) == pytest.approx(1 / 3 * 0.5)
    assert TASK["risks"].score(item, "aucun risque") == 0.0


def test_status_scoring_penalises_long_answers() -> None:
    item = TASK["status"].items()[0]
    short = (
        "Budget : 410 k$ sur 500 k$. Retard de 3 semaines (fournisseur, extraction). "
        "Décision : portée des rapports."
    )
    assert TASK["status"].score(item, short) == 1.0
    assert TASK["status"].score(item, short + " mot" * 200) == 0.5


def test_recommend_prefers_cheaper_model_when_close() -> None:
    summary = {
        "cher": {"global": 0.90, "cost_cad": 0.50},
        "abordable": {"global": 0.87, "cost_cad": 0.05},
        "faible": {"global": 0.60, "cost_cad": 0.01},
    }
    assert run.recommend(summary) == "abordable"


def test_estimate_uses_openrouter_prices_in_cad() -> None:
    gateway = OpenRouterGateway(
        "sk-or-test", Decimal("1.40"), transport=simulated_openrouter.transport()
    )
    catalog = load_catalog(Path(__file__).resolve().parents[2] / "config" / "agents.yaml")
    estimates = run.estimate_cost_cad(gateway, catalog, ["anthropic/claude-sonnet-5.5"])
    assert Decimal("0") < estimates["anthropic/claude-sonnet-5.5"] < Decimal("1")


def test_dry_run_writes_results(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(run, "RESULTS", tmp_path)
    assert run.main(["--dry-run"]) == 0
    (result,) = tmp_path.glob("*-dry-run.json")
    payload = json.loads(result.read_text(encoding="utf-8"))
    assert set(payload["summary"]) == {"fake/small", "fake/large"}
    assert len(payload["rows"]) == 2 * sum(len(t.items()) for t in TASKS)
