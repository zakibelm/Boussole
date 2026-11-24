---
name: pmbok-echeancier
description: Domaine de performance Échéancier (PMBOK 8e) : estimation, modèle d'échéancier, baseline, prévisions, flexibilité et suivi. À utiliser pour planifier, estimer des durées, expliquer un retard ou prévoir une date de fin.
---

# Échéancier (domaine de performance)

Source : PMBOK 8e (Guide §2.3), équivalent 6e (domaine Délais, ch. 6) et 7e (domaine Planification). Synthèse reformulée.

## Concepts clés
- **Échéancier du projet** : sortie d'un modèle qui présente activités liées, durées, jalons et ressources.
- **Estimation** : évaluation quantitative d'une valeur probable ; toujours accompagnée de son niveau d'incertitude.
- **Baseline d'échéancier** : version approuvée servant de référence de mesure.
- **Flexibilité** : marge pour absorber changements et risques ; se gère explicitement, pas par gonflement caché.
- **Prévisions** : projections de l'état futur à partir de la performance observée.
- **Durée réelle** : temps calendaire écoulé entre début et fin effectifs d'une activité.
- **Diagramme de réseau** : représentation graphique des dépendances (sert au chemin critique).

## Les 3 processus (8e)
| Processus | Objectif | Équivalents 6e |
|---|---|---|
| Planifier la gestion de l'échéancier | Fixer politiques, méthode, outils, niveau de détail | 6.1 |
| Élaborer l'échéancier | Analyser séquences, durées, ressources, contraintes pour produire le modèle | 6.2 Définir activités, 6.3 Séquencer, 6.4 Estimer durées, 6.5 Élaborer |
| Surveiller et maîtriser l'échéancier | Suivre l'état, gérer les écarts, mettre à jour le modèle | 6.6 Maîtriser |

(La 6e comptait 6 processus séparés ; la 8e en regroupe la mécanique dans « Élaborer ».)

## Méthodes d'estimation (liste de référence)
Jugement d'expert ; par analogie ; paramétrique ; à trois points (optimiste, probable, pessimiste) ; estimation de groupe (Delphi, poker de planification) ; analyse des réserves. En adaptatif : points de complexité relative, vélocité, prévisions par flux.

## Méthodes d'ordonnancement
Chemin critique ; chaîne critique (tampons de ressources) ; nivellement et lissage des ressources ; compression (accélération en ajoutant des ressources, exécution en parallèle) ; ordonnancement par lieu (*location-based*) ; ordonnancement Lean ; planification par vagues ; échéanciers pilotés par itérations et releases.

## Adaptation selon le cycle de vie
- **Prédictif** : échéancier défini en amont, baseline, contrôle des changements.
- **Adaptatif** : horizon court détaillé, long terme en jalons ; prévoir par itérations.
- **Hybride** : combine échéancier de haut niveau et cadences itératives.
Facteurs d'adaptation : criticité/conformité, technologie, taille et dispersion de l'équipe, expérience, culture, confiance des parties prenantes, ampleur et horizon.

## Procédure de réponse à un retard
1. Mesurer l'écart par rapport à la baseline sur le **chemin critique** (pas sur l'ensemble des tâches).
2. Identifier la cause (estimation, dépendance, ressource, portée, risque matérialisé).
3. Options : compresser, paralléliser, réduire la portée, ajouter de la capacité, renégocier la date ; chiffrer l'effet de chaque option sur coût, qualité et risque.
4. Décider via la gouvernance, mettre à jour baseline et prévisions, communiquer.

## Pièges
- Estimer sans plage ni hypothèses.
- Ajouter des personnes à une tâche tardive sans coût d'intégration (effets de coordination).
- Prévoir à partir de la date promise plutôt que du rythme réel.

## Voir aussi
`pmbok-portee`, `pmbok-finance` (valeur acquise), `pmbok-risque-incertitude`, `pmbok-ressources-equipe`.
