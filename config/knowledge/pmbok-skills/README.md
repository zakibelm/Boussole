# Connaissances métier : 18 skills PMBOK

Synthèses reformulées des éditions 6, 7 et 8 du PMBOK Guide et de l'Extension logicielle
(5e éd.), au format `SKILL.md`. Elles font partie de l'image Docker (le dossier `config/`
est copié dans `/app/config`) : elles restent donc disponibles à chaque déploiement.

- `pmbok-router/` : point d'entrée, règle d'édition (8e par défaut, toujours nommée).
- `skills-index.json` : index lisible par machine (agent par défaut, mots-clés, éditions).
- `AGENTS.md` : répartition proposée des skills entre agents spécialistes.

Ces fichiers sont un complément de contexte. Les valeurs normatives précises (extrants,
tableaux) viennent de la mémoire RAG et sont citées avec section et page (ADR 0004).
Une nouvelle édition = mettre à jour `pmbok-evolution-des-editions`, le skill de domaine
concerné et `skills-index.json`.
