"""Catalogue des agents et sous-agents, lu depuis config/agents.yaml."""

from collections.abc import Iterator
from pathlib import Path

import yaml
from pydantic import BaseModel, Field, model_validator


class AgentSpec(BaseModel):
    id: str = Field(pattern=r"^[a-z_]+(\.[a-z_]+)*$")
    name: str
    default_model: str
    skill: str
    children: list["AgentSpec"] = []


class AgentGroup(BaseModel):
    id: str
    name: str
    agents: list[AgentSpec]


class Catalog(BaseModel):
    shared_rules: str
    groups: list[AgentGroup]

    @model_validator(mode="after")
    def _ids_are_unique(self) -> "Catalog":
        ids = [agent.id for agent in self.all_agents()]
        duplicates = {i for i in ids if ids.count(i) > 1}
        if duplicates:
            raise ValueError(f"Identifiants d'agent en double : {sorted(duplicates)}")
        return self

    def all_agents(self) -> Iterator[AgentSpec]:
        for group in self.groups:
            for agent in group.agents:
                yield agent
                yield from agent.children

    def get(self, agent_id: str) -> AgentSpec:
        for agent in self.all_agents():
            if agent.id == agent_id:
                return agent
        raise KeyError(agent_id)


def load_catalog(path: Path) -> Catalog:
    return Catalog.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))
