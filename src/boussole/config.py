"""Configuration lue dans les variables d'environnement (voir .env.example)."""

import getpass
import os
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class AppConfig:
    database_url: str
    usd_to_cad: Decimal
    budget_cap_cad: Decimal
    task_cap_cad: Decimal
    operator: str
    operator_role: str
    catalog_path: Path
    pmbok_skills_path: Path
    autonomy_path: Path
    min_relevance: float
    allowed_origins: frozenset[str]
    trust_proxy_user: bool
    roles: tuple[tuple[str, str], ...]

    @property
    def is_lightweight(self) -> bool:
        """SQLite : mode local léger, limité aux paramètres d'agents."""
        return self.database_url.startswith("sqlite")


def load_config() -> AppConfig:
    default_db = f"sqlite:///{(ROOT / 'data' / 'local' / 'boussole.db').as_posix()}"
    return AppConfig(
        database_url=os.environ.get("BOUSSOLE_DATABASE_URL", default_db),
        usd_to_cad=Decimal(os.environ.get("BOUSSOLE_USD_CAD_RATE", "1.40")),
        budget_cap_cad=Decimal(os.environ.get("BOUSSOLE_BUDGET_CAP_CAD", "20")),
        task_cap_cad=Decimal(os.environ.get("BOUSSOLE_TASK_CAP_CAD", "0.50")),
        operator=os.environ.get("BOUSSOLE_OPERATOR") or getpass.getuser(),
        operator_role=os.environ.get("BOUSSOLE_OPERATOR_ROLE", "pmo"),
        catalog_path=Path(
            os.environ.get("BOUSSOLE_AGENTS_CONFIG", ROOT / "config" / "agents.yaml")
        ),
        pmbok_skills_path=Path(
            os.environ.get("BOUSSOLE_PMBOK_SKILLS", ROOT / "config" / "pmbok_skills.yaml")
        ),
        autonomy_path=Path(
            os.environ.get("BOUSSOLE_AUTONOMY_CONFIG", ROOT / "config" / "autonomy.yaml")
        ),
        min_relevance=float(os.environ.get("BOUSSOLE_MIN_RELEVANCE", "0.32")),
        allowed_origins=frozenset(
            o.strip()
            for o in os.environ.get("BOUSSOLE_ALLOWED_ORIGINS", "").split(",")
            if o.strip()
        ),
        trust_proxy_user=os.environ.get("BOUSSOLE_TRUST_PROXY_USER", "") == "1",
        roles=_roles(os.environ.get("BOUSSOLE_ROLES", "")),
    )


def _roles(raw: str) -> tuple[tuple[str, str], ...]:
    """« zaki=pmo,marie=project_manager » : rôle de chaque compte nginx."""
    pairs = (item.split("=", 1) for item in raw.split(",") if "=" in item)
    return tuple((user.strip(), role.strip()) for user, role in pairs)
