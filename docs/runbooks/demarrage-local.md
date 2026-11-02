# Démarrer Boussole en local

## Prérequis

- Python 3.12 et [uv](https://docs.astral.sh/uv/)
- Docker Desktop (pour PostgreSQL; facultatif pour la page Paramètres)

## Installation

```bash
uv sync
```

## Lancer l'application

```bash
uv run uvicorn --factory boussole.api.app:app_factory --host 127.0.0.1 --port 8765
```

Puis ouvrir http://127.0.0.1:8765/settings.

Sans `BOUSSOLE_DATABASE_URL`, Boussole démarre en **mode local léger** : une
base SQLite dans `data/local/` (ignoré par git), limitée aux paramètres
d'agents. Pour le reste du produit, utiliser PostgreSQL :

```bash
docker compose -f infra/docker-compose.yml -p boussole up -d --wait
uv run alembic upgrade head
```

## Clé OpenRouter

Saisie dans la page Paramètres, elle est rangée dans le Gestionnaire
d'identifiants Windows (service « boussole »). « Tester la connexion » est
gratuit. Seul « Raffiner avec l'IA » fait un appel payant, compté dans le
budget d'essai (`BOUSSOLE_BUDGET_CAP_CAD`).

## Vérifications

```bash
uv run ruff check . && uv run mypy && uv run pytest --cov
```
