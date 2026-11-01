#!/usr/bin/env bash
# Retour arrière manuel vers une image déjà construite.
#   sudo infra/deploy/rollback.sh <commit>     (images disponibles : docker images boussole)
#
# Ne touche pas aux données. Si une version a abîmé la base, la restauration d'une
# sauvegarde est une décision humaine distincte (docs/runbooks/deploiement.md).
set -euo pipefail
# shellcheck source=infra/deploy/common.sh
source "$(dirname "$0")/common.sh"

TAG="${1:?Usage : rollback.sh <commit>}"
docker image inspect "boussole:$TAG" > /dev/null
start_tag "$TAG"
echo "$TAG" > "$BOUSSOLE_HOME/current_tag"
echo "Version en service : $TAG"
