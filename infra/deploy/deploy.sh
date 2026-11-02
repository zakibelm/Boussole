#!/usr/bin/env bash
# Déploie une étiquette ou un commit sur le VPS (ADR 0009, docs/runbooks/deploiement.md).
#   sudo infra/deploy/deploy.sh <étiquette|commit>
#
# 1. sauvegarde (base, secrets, index)   2. image boussole:<commit>
# 3. démarrage et sonde de santé          4. échec : retour automatique à la version précédente
set -euo pipefail
# shellcheck source=infra/deploy/common.sh
source "$(dirname "$0")/common.sh"

REF="${1:?Usage : deploy.sh <étiquette|commit>}"
cd "$ROOT"
git fetch --tags origin
git checkout --detach "$REF"
TAG="$(git rev-parse --short=12 HEAD)"
PREVIOUS="$(cat "$BOUSSOLE_HOME/current_tag" 2>/dev/null || true)"
echo "Déploiement de $TAG (en service : ${PREVIOUS:-aucune version})"

"$ROOT/infra/deploy/backup.sh"
docker build -f infra/deploy/Dockerfile -t "boussole:$TAG" .

if start_tag "$TAG"; then
    echo "$TAG" > "$BOUSSOLE_HOME/current_tag"
    if ! docker exec "$CONTAINER" python -m boussole.platform.audit.cli verify; then
        echo "ATTENTION : le journal d'audit ne se vérifie pas (voir docs/runbooks/journal-audit.md)" >&2
    fi
    echo "Déployé : $TAG"
    exit 0
fi

echo "Échec du démarrage de $TAG." >&2
if [ -n "$PREVIOUS" ]; then
    echo "Retour automatique à $PREVIOUS (les données n'ont pas été modifiées par l'échec)." >&2
    start_tag "$PREVIOUS"
fi
exit 1
