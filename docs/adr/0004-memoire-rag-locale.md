# ADR 0004 : mémoire RAG indexée en local

- **Statut :** accepté le 2026-10-31 par Zakaria Belmeddah
- **Date :** 2026-10-31

## Contexte

La phase 0 demande d'ingérer le PMBOK 8 en local, de le découper par section
avec la section et la page, et de rechercher avec citations. Le PMBOK est
protégé par le droit d'auteur : son texte ne doit apparaître ni dans le dépôt
ni dans les journaux.

## Décision

1. **Embeddings calculés en local** avec `fastembed` (ONNX, sans GPU). Le
   texte du PMBOK ne quitte jamais le poste, et l'indexation ne coûte rien.
   Modèle par défaut : `sentence-transformers/paraphrase-multilingual-mpnet-base-v2`
   (768 dimensions, licence Apache-2.0, français et anglais), modifiable par
   `BOUSSOLE_EMBEDDING_MODEL`. Le choix définitif se fera par un benchmark de
   recherche (principe 3); `intfloat/multilingual-e5-large` est le candidat
   suivant.
2. **Ports et adaptateurs** : `Embedder` (local, factice) et `VectorStore`.
   Premier adaptateur de stockage : un index local dans `data/local/`
   (ignoré par git). L'adaptateur pgvector viendra quand PostgreSQL tournera,
   avec les mêmes tests de contrat.
3. **Ingestion limitée à `data/local/`** : la commande refuse tout fichier
   situé ailleurs, et l'index est écrit au même endroit.
4. **Découpage par section** à partir des signets du PDF (table des matières),
   avec repli sur la détection des titres numérotés; fenêtres d'environ
   1 500 caractères avec recouvrement, chacune portant section, titre et pages.
5. **Droits par projet** : un extrait sans projet (PMBOK, modèles) est visible
   de tous; un extrait de projet n'est visible que de son projet.
6. **Journaux** : seuls des compteurs et des citations (source, section, page)
   sont journalisés, jamais le texte.

## Conséquences

- Premier lancement : téléchargement du modèle (environ 1 Go) depuis
  Hugging Face, mis en cache sur le poste.
- La recherche en Python pur suffit pour quelques milliers d'extraits; au-delà,
  on passera à pgvector avec un index.
