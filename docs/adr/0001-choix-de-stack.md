# ADR 0001 : choix du langage et de la base de données

- **Statut :** accepté le 2026-10-31 par Zakaria Belmeddah
- **Date :** 2026-10-31
- **Décideur :** Zakaria Belmeddah

## Contexte

Boussole est un PMO piloté par agents : passerelle LLM multi-fournisseurs,
mémoire RAG avec citations, garde-fous, journal d'audit signé en ajout seul,
benchmarks reproductibles. La phase 0 exige un typage strict, des tests de
contrat par adaptateur, des migrations versionnées et une CI avec scan de
secrets et de dépendances. Aucun code n'est écrit avant la validation de cet ADR.

## Critères (pondération sur 5)

| Critère | Poids | Ce qu'on regarde |
|---|---|---|
| Maintenabilité | 5 | Typage strict vérifiable en CI, lisibilité, outillage de refactorisation |
| Écosystème IA | 5 | SDK des fournisseurs LLM, outils RAG, évaluation, benchmark |
| Sécurité | 4 | Scan des dépendances, maturité, contrôle d'accès en base, audit |
| Coût | 3 | Licences, hébergement, coût d'exploitation, compétences disponibles |

Notes de 1 (faible) à 5 (fort). Score = somme des notes × poids.

## Option langage

| Critère | Python 3.12 (FastAPI, Pydantic, mypy strict) | TypeScript (Node 22, Fastify, Zod) |
|---|---|---|
| Maintenabilité | 4 : mypy strict + Pydantic donnent un typage vérifié; moins rigoureux que TS par nature | 5 : typage natif et strict de bout en bout |
| Écosystème IA | 5 : SDK de référence chez tous les fournisseurs, outils d'éval, d'embedding, de parsing PDF | 4 : SDK disponibles, moins d'outils d'éval et de traitement documentaire |
| Sécurité | 4 : pip-audit, bandit, Safety | 4 : npm audit, Snyk; surface de dépendances plus large |
| Coût | 5 : gratuit, compétences répandues, cohérent avec l'écosystème existant (n8n, Supabase) | 5 : gratuit, compétences répandues |
| **Score** | **4×5 + 5×5 + 4×4 + 5×3 = 76** | **5×5 + 4×5 + 4×4 + 5×3 = 76** |

Égalité au score : on départage sur le critère le plus risqué pour ce
produit, l'écosystème IA (benchmark, ingestion PDF, évaluation de biais).
Python l'emporte. L'interface (src/ui/) pourra être en TypeScript séparément,
via l'API unique.

## Option base de données

| Critère | PostgreSQL 16 + pgvector | SQLite + base vectorielle séparée (Qdrant) |
|---|---|---|
| Maintenabilité | 5 : une seule base pour le relationnel et les vecteurs; migrations Alembic | 3 : deux systèmes à synchroniser et migrer |
| Écosystème IA | 4 : pgvector mature, recherche hybride possible avec le plein texte | 5 : Qdrant plus riche en filtres et en performance vectorielle |
| Sécurité | 5 : rôles, sécurité au niveau des lignes (droits par projet), révocation des UPDATE/DELETE pour l'audit | 2 : pas de rôles dans SQLite; droits par projet à coder dans l'application |
| Coût | 4 : gratuit, hébergeable en local ou managé (dont Supabase, région Canada possible) | 5 : gratuit, très léger |
| **Score** | **5×5 + 4×5 + 5×4 + 4×3 = 77** | **3×5 + 5×5 + 2×4 + 5×3 = 63** |

## Décision proposée

- **Langage :** Python 3.12, gestion par `uv`, `ruff` (lint et format),
  `mypy --strict`, `pytest` + `pytest-cov`, API en FastAPI, schémas Pydantic.
- **Base :** PostgreSQL 16 + pgvector, migrations Alembic, sécurité au niveau
  des lignes pour les droits par projet, table de journal en ajout seul
  (UPDATE/DELETE révoqués, chaînage par empreinte et signature).
- **Base vectorielle derrière un port :** pgvector est le premier adaptateur;
  Qdrant reste remplaçable par configuration (principe 1).
- **Développement local :** PostgreSQL en conteneur (infra/).
- **CI :** GitHub Actions (à confirmer) : ruff, mypy, pytest avec seuil de
  couverture, pip-audit, gitleaks.

## Conséquences

- Positives : un seul moteur de données, droits par projet appliqués en base,
  écosystème IA le plus large pour le benchmark et le RAG.
- Négatives : le typage Python dépend de la discipline mypy en CI; si la
  charge vectorielle dépasse pgvector, il faudra activer l'adaptateur Qdrant.
- Réversibilité : le langage est structurant (coûteux à changer); la base
  vectorielle est réversible grâce au port.

## Validation

1. Python 3.12 + PostgreSQL 16/pgvector : **validé**.
2. Hébergement de la base : **local (conteneur) pour la phase 0** par défaut,
   sans donnée réelle ni secret. Le passage à un hébergement managé est un
   point d'arrêt distinct.
3. CI : **GitHub Actions** par défaut (fichier de workflow dans le dépôt);
   aucun dépôt distant n'est créé sans demande.
4. Fournisseurs LLM réels et budget d'essai : **à fixer** avant le premier
   appel payant (point d'arrêt). D'ici là, seul l'adaptateur factice est
   exécuté.
