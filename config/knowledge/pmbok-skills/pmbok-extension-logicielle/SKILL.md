---
name: pmbok-extension-logicielle
description: Extension logicielle du PMBOK (5e éd., PMI/IEEE) : cycles de vie logiciels, exigences, estimation, qualité, changements, risques et communications pour projets logiciels et SI. À utiliser dès qu'un projet produit du logiciel.
---

# Extension logicielle

Source : Software Extension to the PMBOK Guide, Fifth Edition (PMI / IEEE Computer Society), structure alignée sur la 5e édition ; mise en perspective avec les 6e–8e. Synthèse reformulée.

## Principe de l'extension
Elle suit la structure du PMBOK 5e (mêmes chapitres, mêmes processus) et signale pour chaque processus ce qui est inchangé, modifié ou nouveau pour le logiciel. La plupart des outils généraux restent valides ; l'extension ajoute des pratiques propres au logiciel.

## Cycle de vie logiciel
- Six activités de développement servent de repère : **analyser** (exigences), **architecturer**, **concevoir** en détail, **construire**, **intégrer**, **tester/qualifier** (inspirées de la norme ISO/IEC/IEEE 12207).
- **Cycles prédictifs** : phases séquentielles ou chevauchantes avec retour d'information.
- **Cycles adaptatifs** : plusieurs de ces activités à chaque itération ; incréments de logiciel fonctionnel validés régulièrement ; courbe de coût et d'effectif plus plate et plus précoce.
- Les **méthodes agiles** sont des méthodes de développement insérées dans un cycle de vie adaptatif, pas des cycles de vie eux-mêmes.
- Équipes collaboratives : composition, rôles partagés, autogestion.

## Spécificités par domaine (6e/5e)
| Domaine | Apports logiciels |
|---|---|
| **Intégration** | Contrôle des changements incluant l'impact sur produit, utilisateurs, conformité (ex. accessibilité) ; en adaptatif, un changement est un élément du backlog |
| **Portée** | Exigences par cas d'utilisation, récits utilisateurs, prototypes, démonstrations de logiciel fonctionnel ; documentation des exigences selon normes IEEE ; BABOK comme référence d'analyse d'affaires |
| **Délais** | Backlog priorisé comme équivalent du planning par vagues ; estimation par points de fonction, jugement d'expert, analogique, paramétrique, trois points ; ententes de niveau de service (SLA) |
| **Coûts** | Estimation fondée sur la taille fonctionnelle et la productivité observée |
| **Qualité** | Attributs propres : sécurité, fiabilité, utilisabilité, maintenabilité, testabilité, portabilité, interopérabilité… ; coût de la qualité (prévention, évaluation, défauts internes et externes) ; inspections, revues, tests, gestion des défauts |
| **Risques** | Rétrospectives comme source de risques ; risques techniques (intégration, performance), de dépendance (COTS, tiers), de dette technique |
| **Communications / Parties prenantes** | Personas pour comprendre les utilisateurs ; jalons de revue et plans d'itération |
| **Approvisionnements** | Logiciels sur étagère (COTS), sous-traitance de développement, licences |

## Questions types pour un agent
1. **Quel cycle de vie ?** Instabilité des exigences et besoin de retour → adaptatif ; contraintes réglementaires ou sécurité → prédictif ou hybride.
2. **Comment estimer ?** Préférer plusieurs méthodes croisées ; exprimer des plages ; recalibrer avec la vélocité ou les données historiques.
3. **Quand dire « terminé » ?** Définir DoD et critères d'acceptation avant le développement ; tests automatisés dans la DoD.
4. **Comment gérer la dette technique ?** La rendre visible dans le backlog et le risque ; fixer un budget de remboursement.
5. **Comment contrôler les versions ?** Gestion de configuration : identifier, contrôler, tracer, auditer les éléments ; politique de branches et de versions.

## Mise en garde sur l'âge de la source
L'extension date de 2013 : elle ne couvre pas DevOps, livraison continue, infonuagique ni IA générative en détail. Pour ces sujets, combiner avec la 8e (cadence de livraison continue, annexe IA) et les pratiques actuelles.

## Voir aussi
`pmbok-cycles-de-vie-approches`, `pmbok-portee`, `pmbok-qualite`, `pmbok-risque-incertitude`, `pmbok-pmo-et-ia`.
