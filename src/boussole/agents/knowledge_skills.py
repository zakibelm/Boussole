"""Connaissances métier : les skills PMBOK combinés et distribués aux bons agents.

config/knowledge/agent_skills.yaml dit quels skills reçoit chaque agent; le texte de
chaque skill vit dans config/knowledge/pmbok-skills/<nom>/SKILL.md, donc dans l'image
Docker. Ce complément oriente le raisonnement : les valeurs normatives précises viennent
de la mémoire RAG et sont citées avec section et page (voir pmbok_skills.py).
"""

import re
from pathlib import Path

import yaml
from pydantic import BaseModel, model_validator

from boussole.agents.catalog import Catalog

MAX_SKILLS_PER_AGENT = 3
_FRONT_MATTER = re.compile(r"\A---\n.*?\n---\n", re.DOTALL)
_HEADER = (
    "Connaissances métier (synthèses du PMBOK, éditions 6, 7 et 8) : elles orientent ton "
    "raisonnement. Nomme l'édition sur laquelle tu t'appuies (la 8e par défaut). Pour une "
    "valeur normative précise, cite la mémoire avec section et page."
)


class KnowledgeSkills(BaseModel):
    texts: dict[str, str]
    agents: dict[str, list[str]]

    @model_validator(mode="after")
    def _consistent(self) -> "KnowledgeSkills":
        for agent_id, names in self.agents.items():
            if len(names) > MAX_SKILLS_PER_AGENT or len(set(names)) != len(names):
                raise ValueError(f"{agent_id} : au plus {MAX_SKILLS_PER_AGENT} skills distincts.")
            unknown = sorted(set(names) - self.texts.keys())
            if unknown:
                raise ValueError(f"Skills inconnus pour {agent_id} : {unknown}")
        return self

    def check_agents(self, catalog: Catalog) -> None:
        """Toute affectation vise un agent qui existe vraiment."""
        known = {agent.id for agent in catalog.all_agents()}
        unknown = sorted(self.agents.keys() - known)
        if unknown:
            raise ValueError(f"Agents inconnus dans les connaissances métier : {unknown}")

    def note_for(self, agent_id: str) -> str:
        """Bloc ajouté au prompt de l'agent; vide s'il ne reçoit aucun skill."""
        names = self.agents.get(agent_id, [])
        if not names:
            return ""
        sections = (f"### {name}\n{self.texts[name]}" for name in names)
        return "\n\n".join([_HEADER, *sections])


def load_knowledge_skills(root: Path) -> KnowledgeSkills:
    """`root` : config/knowledge (agent_skills.yaml et dossier pmbok-skills/)."""
    skills_dir = root / "pmbok-skills"
    texts = {
        folder.name: _FRONT_MATTER.sub(
            "", (folder / "SKILL.md").read_text(encoding="utf-8")
        ).strip()
        for folder in sorted(skills_dir.iterdir())
        if (folder / "SKILL.md").is_file()
    }
    mapping = yaml.safe_load((root / "agent_skills.yaml").read_text(encoding="utf-8"))
    return KnowledgeSkills.model_validate({"texts": texts, **mapping})
