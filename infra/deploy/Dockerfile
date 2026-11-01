# syntax=docker/dockerfile:1.7
# Image de production de Boussole (ADR 0009). Construite depuis la racine du dépôt :
#   docker build -f infra/deploy/Dockerfile -t boussole:<commit> .
#
# L'application lit config/ et data/local/ par rapport à la racine du dépôt : l'image
# garde cette arborescence sous /app. Données et secrets vivent dans des volumes.

FROM python:3.12-slim-bookworm AS build
COPY --from=ghcr.io/astral-sh/uv:0.11.28 /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never
WORKDIR /app
# Dépendances d'abord (couche réutilisée tant que uv.lock ne change pas)
COPY pyproject.toml uv.lock README.md* ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --extra server --no-install-project
COPY src ./src
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --extra server

FROM python:3.12-slim-bookworm
RUN groupadd --system --gid 10001 boussole \
    && useradd --system --uid 10001 --gid boussole --home-dir /app --no-create-home boussole
WORKDIR /app
COPY --from=build --chown=boussole:boussole /app /app
COPY --chown=boussole:boussole config ./config
COPY --chown=boussole:boussole alembic.ini ./alembic.ini
COPY --chown=boussole:boussole infra/migrations ./infra/migrations

# Volumes : /app/data/local (base SQLite, index RAG, PDF, modèle d'embeddings)
#           /app/secrets    (coffre des clés : OpenRouter et signature du journal)
ENV PATH="/app/.venv/bin:${PATH}" \
    PYTHONUNBUFFERED=1 \
    PYTHON_KEYRING_BACKEND=keyrings.alt.file.PlaintextKeyring \
    XDG_DATA_HOME=/app/secrets \
    FASTEMBED_CACHE_PATH=/app/data/local/models \
    HF_HOME=/app/data/local/models/hf
RUN mkdir -p /app/data/local /app/secrets && chown boussole:boussole /app/data/local /app/secrets
USER boussole

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
    CMD ["python", "-c", "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=4).read() == b'ok' else 1)"]

# Un seul processus : le verrou du journal et les réservations de budget sont
# propres au processus (ADR 0006, ADR 0009). Plusieurs workers les contourneraient.
CMD ["uvicorn", "--factory", "boussole.api.app:app_factory", \
     "--host", "0.0.0.0", "--port", "8000", "--workers", "1", "--no-server-header"]
