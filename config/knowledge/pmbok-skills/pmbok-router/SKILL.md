---
name: pmbok-router
description: Point d'entrée de la base de connaissances PMBOK (6e, 7e, 8e + extension logicielle 5e). À utiliser en premier pour toute question de gestion de projet afin de choisir le bon skill et la bonne édition.
---

# Routeur PMBOK

Ce skill ne contient pas de contenu de fond : il aiguille vers le bon skill, puis vers la bonne édition.

## Règle d'édition par défaut

| Situation | Édition de référence |
|---|---|
| Question générale ou moderne (valeur, domaines, adaptation, IA) | **8e** (2025) |
| Vocabulaire « processus / ITTO / groupes de processus / 10 domaines de connaissance » | **6e** (2017) |
| Principes, modèles, méthodes, artefacts, mesure, incertitude | **7e** (2021) |
| Projet logiciel / SI / IA | **8e + Extension logicielle (5e éd., IEEE)** |
| Préparation d'examen ou audit qui cite une édition | l'édition citée, sans la mélanger |

Toujours annoncer dans la réponse sur quelle édition elle s'appuie. Ne jamais fondre deux éditions sans signaler la différence (voir `pmbok-evolution-des-editions`).

## Table d'aiguillage

| Si la question porte sur… | Skill principal | Skills complémentaires |
|---|---|---|
| Pourquoi un projet existe, valeur, principes, état d'esprit | `pmbok-principes-valeur` | `pmbok-gouvernance` |
| Prédictif / agile / hybride, phases, cadence de livraison, zones de focus | `pmbok-cycles-de-vie-approches` | `pmbok-adaptation-tailoring` |
| Comment adapter la méthode au contexte | `pmbok-adaptation-tailoring` | `pmbok-cycles-de-vie-approches` |
| Charte, plan intégré, changements, clôture, connaissances | `pmbok-gouvernance` | `pmbok-6e-processus-49` |
| Exigences, périmètre, WBS, backlog, validation | `pmbok-portee` | `pmbok-qualite` |
| Planning, durées, chemin critique, prévisions | `pmbok-echeancier` | `pmbok-risque-incertitude` |
| Coûts, budget, réserves, valeur acquise | `pmbok-finance` | `pmbok-echeancier` |
| Parties prenantes, communication, engagement | `pmbok-parties-prenantes-communications` | `pmbok-ressources-equipe` |
| Équipe, leadership, ressources physiques | `pmbok-ressources-equipe` | `pmbok-parties-prenantes-communications` |
| Risques, menaces/opportunités, ambiguïté, résilience | `pmbok-risque-incertitude` | `pmbok-gouvernance` |
| Qualité, définition de « terminé », assurance/contrôle | `pmbok-qualite` | `pmbok-portee` |
| Achats, sous-traitance, contrats, choix fournisseur | `pmbok-approvisionnement` | `pmbok-finance`, `pmbok-risque-incertitude` |
| Les 49 processus / groupes de processus / ITTO | `pmbok-6e-processus-49` | domaine correspondant |
| Modèles (Tuckman, ADKAR…), méthodes, artefacts, métriques | `pmbok-7e-domaines-modeles` | `pmbok-ressources-equipe` |
| Ce qui a changé d'une édition à l'autre, équivalences de termes | `pmbok-evolution-des-editions` | — |
| Logiciel, SI, cycle de développement, défauts, versions | `pmbok-extension-logicielle` | `pmbok-qualite`, `pmbok-portee` |
| PMO, maturité, intelligence artificielle en gestion de projet | `pmbok-pmo-et-ia` | `pmbok-gouvernance` |

## Procédure d'aiguillage (pour un agent orchestrateur)

1. Identifier le **sujet dominant** et l'**édition implicite** (indices : « processus », « principe », « domaine », « sprint »).
2. Charger le skill principal ; ajouter au plus **2 skills complémentaires**.
3. Si la question traverse plusieurs domaines (ex. « retard + dépassement de budget + insatisfaction client »), charger `pmbok-gouvernance` en plus : c'est le domaine qui arbitre les compromis entre les autres.
4. Répondre au format : **Problème → Action → Bénéfice**, en nommant l'édition utilisée.
5. En cas de doute entre 6e et 8e, proposer la correspondance via `pmbok-evolution-des-editions` plutôt que de choisir silencieusement.

## Vocabulaire qui change selon l'édition (aide-mémoire)

- Groupes de processus (6e) → **zones de focus** (8e) : mêmes cinq noms, mais ce ne sont plus des catégories de processus formels.
- Domaines de connaissance (6e, 10) → **domaines de performance** (8e, 7).
- 8 domaines de performance (7e) → 7 domaines (8e) différents ; ne pas les confondre.
- 12 principes (7e) → 6 principes (8e).
