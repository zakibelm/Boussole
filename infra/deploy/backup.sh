#!/usr/bin/env bash
# Sauvegarde de Boussole : base SQLite (copie cohérente même en service), secrets, index RAG.
#   sudo infra/deploy/backup.sh          (lancé aussi avant chaque déploiement et par cron)
#
# Les secrets sont en clair dans le coffre : les sauvegardes sont lisibles par root seul
# (umask 077). Copier régulièrement le dossier hors du serveur, chiffré.
set -euo pipefail

BOUSSOLE_HOME="${BOUSSOLE_HOME:-/srv/boussole}"
DEST="${BOUSSOLE_BACKUPS:-/var/backups/boussole}"
KEEP_DAYS="${BOUSSOLE_BACKUP_DAYS:-14}"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"

umask 077
mkdir -p "$DEST/$STAMP"

if [ -f "$BOUSSOLE_HOME/data/boussole.db" ]; then
    python3 - "$BOUSSOLE_HOME/data/boussole.db" "$DEST/$STAMP/boussole.db" <<'PY'
import sqlite3
import sys

source = sqlite3.connect(f"file:{sys.argv[1]}?mode=ro", uri=True)
target = sqlite3.connect(sys.argv[2])
source.backup(target)
target.close()
source.close()
PY
fi

tar -C "$BOUSSOLE_HOME" -czf "$DEST/$STAMP/secrets.tgz" secrets
# Index RAG (reconstruire coûte une ingestion complète); ni PDF ni modèle, retéléchargeables
tar -C "$BOUSSOLE_HOME/data" -czf "$DEST/$STAMP/index.tgz" \
    --exclude=./models --exclude='*.pdf' --exclude=./boussole.db .

# Rétention : seuls les dossiers horodatés de ce script sont supprimés
find "$DEST" -mindepth 1 -maxdepth 1 -type d -name '20*Z' -mtime +"$KEEP_DAYS" -exec rm -rf {} +
echo "Sauvegarde : $DEST/$STAMP"
