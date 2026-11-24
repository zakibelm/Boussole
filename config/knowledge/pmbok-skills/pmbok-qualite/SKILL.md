---
name: pmbok-qualite
description: Gestion de la qualité en projet : principe de qualité intégrée (8e), assurance, contrôle, coût de la qualité, critères d'acceptation, DoD. À utiliser pour définir, mesurer ou améliorer la qualité de livrables et de processus.
---

# Qualité

Source : PMBOK 8e (Standard §3.5, Guide : processus « Gérer l'assurance qualité », qualité dans le domaine Portée), 6e (domaine Qualité, ch. 8), 7e (domaine Livraison : qualité et résultats sous-optimaux), Extension logicielle (§1.9, ch. 8). Synthèse reformulée.

## Idée centrale
La qualité est le degré auquel les caractéristiques inhérentes d'un livrable ou d'un processus permettent d'atteindre ou de dépasser les objectifs visés. En 8e, elle n'est plus un domaine séparé : c'est un **principe** transversal et une **caractéristique de la portée**.

Mesures de la qualité : conformité aux critères d'acceptation, définition de « terminé », adéquation à l'usage, efficacité globale des processus.

## Ce que la 6e détaillait (utile pour l'audit et l'examen)
| Processus | But |
|---|---|
| 8.1 Planifier la gestion de la qualité | Définir normes, critères, façon de démontrer la conformité |
| 8.2 Gérer la qualité (assurance) | Vérifier que les processus sont suivis et efficaces, améliorer |
| 8.3 Maîtriser la qualité (contrôle) | Mesurer les résultats, détecter défauts, valider les corrections |

- **Assurance** : porte sur les *processus* (prévenir). **Contrôle** : porte sur les *résultats* (détecter).
- **Coût de la qualité** : prévention + évaluation (coût de conformité) vs défaillances internes et externes (coût de non-conformité).
- **Outils classiques** : diagrammes de causes et effets, diagramme de Pareto, histogrammes, cartes de contrôle, diagrammes de dispersion, listes de vérification, échantillonnage statistique, audits, inspections.

## Procédure de mise en place
1. Traduire les attentes en **critères mesurables** (acceptation, seuils de performance).
2. Définir la **DoD** au niveau de l'élément livré et au niveau de l'incrément ou de la phase.
3. Choisir où prévenir (revues, standards, automatisation) et où détecter (tests, inspections, audits).
4. Fixer les mesures et leur fréquence ; afficher la tendance, pas seulement le chiffre du jour.
5. Boucler : analyse des causes racines → amélioration du processus → mise à jour des critères.

## Adaptation
- Produits à exigences de sécurité ou très réglementés : plus de documentation et de vérification indépendante.
- Approches itératives : qualité vérifiée à chaque incrément (tests automatisés, revues de démonstration).
- Projets logiciels : attributs de qualité propres (fiabilité, utilisabilité, maintenabilité…) — voir `pmbok-extension-logicielle`.

## Pièges
- Contrôler en fin de chaîne seulement (coût de correction maximal).
- Qualité définie par l'équipe sans validation du client ou de l'utilisateur.
- Confondre « sans défaut » et « adapté à l'usage » : un livrable parfait mais inutile reste un échec de valeur.

## Voir aussi
`pmbok-portee`, `pmbok-gouvernance`, `pmbok-principes-valeur`, `pmbok-extension-logicielle`.
