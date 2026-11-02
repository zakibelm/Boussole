#!/usr/bin/env bash
# Échoue si le dépôt suit un fichier interdit : PDF (PMBOK protégé), données
# locales, fichiers d'environnement réels, bases de données ou index RAG.
set -euo pipefail

forbidden=$(
  git ls-files \
    | grep -Ei '\.pdf$|^data/|(^|/)\.env(\..+)?$|\.db$|\.sqlite3?$|rag_index' \
    | grep -v '\.env\.example$' \
    || true
)

if [ -n "$forbidden" ]; then
  echo "Fichiers interdits suivis par git :"
  echo "$forbidden"
  exit 1
fi
echo "Aucun fichier interdit suivi."
