# ADR 0005 : écarts fonctionnels relevés face à monday.com

- **Statut :** proposé le 2026-10-31, en attente de validation par Zakaria Belmeddah
- **Date :** 2026-10-31

## Contexte

Une analyse fonctionnelle de monday.com, faite uniquement à partir de sources
publiques (voir `docs/marche/analyse-monday-2026-10.md`), relève treize
fonctions absentes de Boussole qui aideraient son adoption et sa performance.
La rétro-ingénierie du service a été écartée : les conditions d'utilisation de
monday.com l'interdisent, et seules les fonctions offertes comptent pour nous.

## Décision proposée

Ajouter les treize écarts à la feuille de route (marqués ◆), chacun dans la
phase où il sert le critère de sortie, avec son garde-fou :

- Phase 1 : vues tableau et Kanban, formulaire de demande de projet,
  notifications, validation sur mobile, alertes de coût IA, budget de
  performance.
- Phase 2 : Gantt avec dépendances, chemin critique et ligne de base; mode
  simulation des agents; modèles d'agents; comptes rendus de réunion vers la
  file de validation; documents de projet générés.
- Phase 3 : synchronisation bidirectionnelle (Jira, Azure DevOps, Microsoft
  Project), plafonds de coût par client, accès invité en lecture, SSO et MFA.

## Conséquences

- La phase 1 grossit encore. Si le pilote doit rester court, les candidats au
  report en phase 2 sont, dans l'ordre : validation sur mobile, notifications
  Teams ou Slack (garder le courriel), alertes de coût.
- Aucun écart n'est commencé avant le critère de sortie de la phase 0.
