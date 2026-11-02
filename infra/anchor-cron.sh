#!/usr/bin/env bash
# Ancre quotidienne du journal d'audit, envoyée HORS du serveur (docs/runbooks/journal-audit.md).
#   infra/anchor-cron.sh              (lancé par /etc/cron.d/boussole)
#
# 1. Crée une ancre signée dans le journal (audit.cli anchor) et affiche sa ligne.
# 2. L'envoie en HTTPS (POST, JSON) vers BOUSSOLE_ANCHOR_URL, avec le jeton
#    BOUSSOLE_ANCHOR_TOKEN DANS LE CORPS (jamais dans l'adresse) : infra/anchor-receiver/.
# L'adresse et le jeton ne sont jamais affichés : ils ne passent ni dans la sortie, ni dans
# les messages d'erreur, ni dans les arguments de curl (corps sur l'entrée standard,
# adresse dans un fichier de configuration temporaire lisible par root seulement).
# Sort en erreur (code ≠ 0) si l'adresse ou le jeton manque, si l'adresse n'est pas en
# HTTPS ou si l'envoi échoue : cron le signale. L'ancre reste créée dans le journal.
set -euo pipefail

CONTAINER="${BOUSSOLE_CONTAINER:-boussole-prod-app-1}"
ENV_FILE="${BOUSSOLE_HOME:-/srv/boussole}/boussole.env"

read_env() {
    if [ -r "$ENV_FILE" ]; then
        sed -n "s/^$1=//p" "$ENV_FILE" | tail -n 1
    fi
}

url="${BOUSSOLE_ANCHOR_URL:-$(read_env BOUSSOLE_ANCHOR_URL)}"
token="${BOUSSOLE_ANCHOR_TOKEN:-$(read_env BOUSSOLE_ANCHOR_TOKEN)}"

output="$(docker exec "$CONTAINER" python -m boussole.platform.audit.cli anchor)"
echo "$output"
line="$(grep -E '^[0-9]+:[0-9a-f]{64}$' <<< "$output" | tail -n 1 || true)"
if [ -z "$line" ]; then
    echo "ERREUR : ancre introuvable dans la sortie de audit.cli anchor." >&2
    exit 2
fi

if [ -z "$url" ]; then
    echo "ERREUR : BOUSSOLE_ANCHOR_URL vide, l'ancre $line n'est pas partie hors du serveur." >&2
    exit 3
fi
if [[ "$url" != https://* || "$url" == *\?* || "$url" == *\"* ]]; then
    echo "ERREUR : BOUSSOLE_ANCHOR_URL doit être en HTTPS et sans paramètre, ancre $line non envoyée." >&2
    exit 3
fi
if [[ ! "$token" =~ ^[A-Za-z0-9_-]{16,}$ ]]; then
    echo "ERREUR : BOUSSOLE_ANCHOR_TOKEN absent ou mal formé (16 caractères A-Z a-z 0-9 _ - au moins), ancre $line non envoyée." >&2
    exit 3
fi

config="$(umask 077 && mktemp)"
trap 'rm -f "$config"' EXIT
printf 'url = "%s"\n' "$url" > "$config"
body="$(printf '{"token":"%s","anchor":"%s","host":"%s","at":"%s"}' \
    "$token" "$line" "$(hostname)" "$(date -u +%Y-%m-%dT%H:%M:%SZ)")"

# Apps Script répond par une redirection vers sa réponse : -L la suit (en GET).
code=0
response="$(curl --fail --silent --location --max-redirs 3 --max-time 30 \
    --config "$config" \
    --header "Content-Type: application/json; charset=utf-8" \
    --data-binary @- <<< "$body" 2> /dev/null)" || code=$?
if [ "$code" -ne 0 ]; then
    echo "ERREUR : envoi de l'ancre $line impossible (curl, code $code)." >&2
    exit 4
fi
if [ "$response" != "ok" ]; then
    echo "ERREUR : ancre $line refusée par le point de réception (jeton ou format)." >&2
    exit 5
fi
echo "Ancre $line envoyée hors du serveur."
