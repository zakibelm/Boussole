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
    operator: str
    catalog_path: Path

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
        operator=os.environ.get("BOUSSOLE_OPERATOR") or getpass.getuser(),
        catalog_path=Path(
            os.environ.get("BOUSSOLE_AGENTS_CONFIG", ROOT / "config" / "agents.yaml")
        ),
    )
