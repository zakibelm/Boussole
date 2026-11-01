#!/usr/bin/env bash
# Ancre quotidienne du journal d'audit, envoyée HORS du serveur (docs/runbooks/journal-audit.md).
#   infra/anchor-cron.sh              (lancé par /etc/cron.d/boussole)
#
# 1. Crée une ancre signée dans le journal (audit.cli anchor) et affiche sa ligne.
# 2. L'envoie en HTTPS (POST) vers BOUSSOLE_ANCHOR_URL.
# Sort en erreur (code ≠ 0) si l'adresse manque, n'est pas en HTTPS ou si l'envoi échoue :
# cron le signale. L'ancre reste créée dans le journal, et sa ligne dans la sortie.
set -euo pipefail

CONTAINER="${BOUSSOLE_CONTAINER:-boussole-prod-app-1}"
ENV_FILE="${BOUSSOLE_HOME:-/srv/boussole}/boussole.env"

if [ -z "${BOUSSOLE_ANCHOR_URL:-}" ] && [ -r "$ENV_FILE" ]; then
    BOUSSOLE_ANCHOR_URL="$(sed -n 's/^BOUSSOLE_ANCHOR_URL=//p' "$ENV_FILE" | tail -n 1)"
fi

output="$(docker exec "$CONTAINER" python -m boussole.platform.audit.cli anchor)"
echo "$output"
line="$(grep -E '^[0-9]+:[0-9a-f]{64}$' <<< "$output" | tail -n 1 || true)"
if [ -z "$line" ]; then
    echo "ERREUR : ancre introuvable dans la sortie de audit.cli anchor." >&2
    exit 2
fi

url="${BOUSSOLE_ANCHOR_URL:-}"
if [ -z "$url" ]; then
    echo "ERREUR : BOUSSOLE_ANCHOR_URL vide, l'ancre $line n'est pas partie hors du serveur." >&2
    exit 3
fi
if [[ "$url" != https://* ]]; then
    echo "ERREUR : BOUSSOLE_ANCHOR_URL doit être en HTTPS, ancre $line non envoyée." >&2
    exit 3
fi

if ! curl --fail --silent --show-error --max-time 30 \
    --header "Content-Type: text/plain; charset=utf-8" \
    --data-binary "boussole-anchor $(hostname) $(date -u +%Y-%m-%dT%H:%M:%SZ) $line" \
    "$url" > /dev/null; then
    echo "ERREUR : envoi de l'ancre $line vers $url impossible." >&2
    exit 4
fi
echo "Ancre $line envoyée hors du serveur."
