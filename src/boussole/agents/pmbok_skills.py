"""Le PMBOK 8 en skills : chaque agent consulte ses parties du livre, les orchestrateurs tout.

Le fichier config/pmbok_skills.yaml ne contient que des repères (pages du PDF
indexé), jamais de texte du livre. Le texte reste dans l'index local (ADR 0004).
"""

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, model_validator

from boussole.agents.catalog import Catalog
from boussole.platform.memory_rag.port import PageRange

WHOLE_BOOK = "all"


class PmbokPart(BaseModel):
    label: str
    pages: tuple[int, int]

    @model_validator(mode="after")
    def _ordered(self) -> "PmbokPart":
        if not 0 < self.pages[0] <= self.pages[1]:
            raise ValueError(f"Pages invalides pour « {self.label} » : {self.pages}")
        return self


class PmbokSkills(BaseModel):
    source: str
    parts: dict[str, PmbokPart]
    agents: dict[str, Literal["all"] | list[str]]

    @model_validator(mode="after")
    def _known_parts(self) -> "PmbokSkills":
        for agent_id, refs in self.agents.items():
            unknown = sorted(set(self._refs(refs)) - self.parts.keys())
            if unknown:
                raise ValueError(f"Parties inconnues pour {agent_id} : {unknown}")
        return self

    def check_agents(self, catalog: Catalog) -> None:
        """Toute affectation vise un agent qui existe vraiment."""
        known = {agent.id for agent in catalog.all_agents()}
        unknown = sorted(self.agents.keys() - known)
        if unknown:
            raise ValueError(f"Agents inconnus dans le PMBOK en skills : {unknown}")

    def pages_for(self, agent_id: str) -> tuple[PageRange, ...] | None:
        """None : tout le livre. Tuple vide : aucune partie (l'agent ne consulte pas le PMBOK)."""
        refs = self.agents.get(agent_id, [])
        if refs == WHOLE_BOOK:
            return None
        return tuple(self.parts[ref].pages for ref in self._refs(refs))

    def pages_of(self, part_ids: tuple[str, ...]) -> tuple[PageRange, ...]:
        """Pages de parties nommées; une partie inconnue fait échouer le chargement."""
        unknown = sorted(set(part_ids) - self.parts.keys())
        if unknown:
            raise ValueError(f"Parties inconnues : {unknown}")
        return tuple(self.parts[p].pages for p in part_ids)

    def note_for(self, agent_id: str) -> str:
        """Paragraphe ajouté au skill : ce que l'agent consulte et comment il cite."""
        refs = self.agents.get(agent_id, [])
        if refs == WHOLE_BOOK:
            scope = f"tout le {self.source}"
        elif refs:
            scope = "; ".join(self._describe(ref) for ref in self._refs(refs))
        else:
            return ""
        return (
            f"Références {self.source} : {scope}.\n"
            "Appuie tes recommandations sur ces parties, cite section et page pour chaque "
            "affirmation normative, et dis-le quand elles ne couvrent pas la question."
        )

    def _describe(self, ref: str) -> str:
        part = self.parts[ref]
        return f"{part.label} (p. {part.pages[0]}-{part.pages[1]})"

    @staticmethod
    def _refs(refs: Literal["all"] | list[str]) -> list[str]:
        return [] if refs == WHOLE_BOOK else list(refs)


def load_pmbok_skills(path: Path) -> PmbokSkills:
    return PmbokSkills.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))
