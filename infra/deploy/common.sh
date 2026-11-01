#!/usr/bin/env bash
# Fonctions partagées par deploy.sh et rollback.sh.

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
export BOUSSOLE_HOME="${BOUSSOLE_HOME:-/srv/boussole}"
CONTAINER="boussole-app-1"

compose() {
    docker compose -f "$ROOT/infra/deploy/compose.prod.yml" -p boussole "$@"
}

# Démarre l'image boussole:<étiquette> et attend que la sonde de santé réponde.
start_tag() {
    local tag="$1"
    BOUSSOLE_IMAGE_TAG="$tag" compose up -d --remove-orphans
    wait_healthy
}

wait_healthy() {
    local status=""
    for _ in $(seq 1 30); do
        status="$(docker inspect --format '{{.State.Health.Status}}' "$CONTAINER" 2>/dev/null || true)"
        if [ "$status" = "healthy" ]; then
            return 0
        fi
        sleep 3
    done
    echo "Sonde de santé : ${status:-aucune réponse} après 90 s" >&2
    return 1
}
