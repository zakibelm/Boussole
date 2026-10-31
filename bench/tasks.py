"""Les trois tâches PMO du benchmark : consigne, agent concerné et notation (0 à 1).

Les jeux de données sont synthétiques (aucune donnée de client, aucun texte du
PMBOK). La notation est déterministe : mots-clés attendus et format respecté.
"""

import json
import re
import unicodedata
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

DATASETS = Path(__file__).resolve().parent / "datasets"
MAX_STATUS_WORDS = 150
# Les modèles à raisonnement consomment cette limite avant d'écrire leur réponse.
REASONING_ROOM = 4000

APPROACHES = {
    "predictive": "predictive",
    "predictif": "predictive",
    "predictive approach": "predictive",
    "adaptive": "adaptive",
    "adaptatif": "adaptive",
    "agile": "adaptive",
    "hybrid": "hybrid",
    "hybride": "hybrid",
}


@dataclass(frozen=True)
class Task:
    name: str
    agent_id: str
    prompt: Callable[[dict[str, Any]], str]
    score: Callable[[dict[str, Any], str], float]
    max_tokens: int

    def items(self) -> list[dict[str, Any]]:
        path = DATASETS / f"{self.name}.jsonl"
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def normalize(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text.lower())
    return "".join(c for c in decomposed if not unicodedata.combining(c))


def extract_json(text: str) -> Any:
    """Premier objet ou tableau JSON du texte (blocs ``` tolérés); None sinon."""
    cleaned = re.sub(r"```(?:json)?", "", text)
    pairs = sorted(
        (("{", "}"), ("[", "]")),
        key=lambda pair: cleaned.find(pair[0]) if pair[0] in cleaned else len(cleaned),
    )
    for opener, closer in pairs:
        start, end = cleaned.find(opener), cleaned.rfind(closer)
        if 0 <= start < end:
            try:
                return json.loads(cleaned[start : end + 1])
            except json.JSONDecodeError:
                continue
    return None


def _covered(text: str, groups: list[list[str]]) -> int:
    haystack = normalize(text)
    return sum(any(normalize(k) in haystack for k in group) for group in groups)


# --- Résumer un statut -----------------------------------------------------


def _status_prompt(item: dict[str, Any]) -> str:
    return (
        "Résume ce statut de projet pour la direction, en 5 puces au maximum : avancement, "
        "budget, échéancier, problèmes et décision attendue.\n\n"
        f"<notes>\n{item['notes']}\n</notes>"
    )


def _status_score(item: dict[str, Any], answer: str) -> float:
    facts: list[list[str]] = item["facts"]
    coverage = _covered(answer, facts) / len(facts)
    concise = len(answer.split()) <= MAX_STATUS_WORDS
    return coverage if concise else coverage * 0.5


# --- Extraire les risques --------------------------------------------------


def _risks_prompt(item: dict[str, Any]) -> str:
    return (
        "Extrais les risques de ce texte. Réponds uniquement par un tableau JSON d'objets "
        '{"titre": str, "description": str, "probabilite": 1-5, "impact": 1-5}.\n\n'
        f"<texte>\n{item['text']}\n</texte>"
    )


def _risks_score(item: dict[str, Any], answer: str) -> float:
    risks = extract_json(answer)
    if not isinstance(risks, list) or not risks:
        return 0.0
    gold: list[list[str]] = item["gold"]
    recall = _covered(json.dumps(risks, ensure_ascii=False), gold) / len(gold)
    valid = all(_scored(r) for r in risks)
    concise = len(risks) <= 2 * len(gold)
    return recall * (1.0 if valid else 0.5) * (1.0 if concise else 0.75)


def _scored(risk: Any) -> bool:
    if not isinstance(risk, dict):
        return False
    values = (risk.get("probabilite"), risk.get("impact"))
    return all(isinstance(v, int) and 1 <= v <= 5 for v in values)


# --- Recommander une approche ----------------------------------------------


def _approach_prompt(item: dict[str, Any]) -> str:
    return (
        "Recommande l'approche de ce projet selon les critères du PMBOK (livrables, projet, "
        'organisation). Réponds uniquement en JSON : {"approche": "predictive" | "adaptive" | '
        '"hybrid", "justification": str}.\n\n'
        f"<projet>\n{item['case']}\n</projet>"
    )


def _approach_score(item: dict[str, Any], answer: str) -> float:
    data = extract_json(answer)
    if not isinstance(data, dict):
        return 0.0
    choice = APPROACHES.get(normalize(str(data.get("approche", ""))).strip())
    return 1.0 if choice == item["expected"] else 0.0


TASKS = (
    Task("status", "closing", _status_prompt, _status_score, max_tokens=REASONING_ROOM),
    Task("risks", "domain.risk", _risks_prompt, _risks_score, max_tokens=REASONING_ROOM),
    Task("approach", "selector", _approach_prompt, _approach_score, max_tokens=REASONING_ROOM),
)
