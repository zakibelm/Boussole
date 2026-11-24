---
name: pmbok-finance
description: Domaine de performance Finance (PMBOK 8e) : définition de la valeur, financement, estimation des coûts, budget, réserves, baseline de coûts, suivi et valeur acquise. À utiliser pour budgéter, expliquer un écart de coût ou prévoir le coût final.
---

# Finance (domaine de performance)

Source : PMBOK 8e (Guide §2.4), équivalent 6e (domaine Coûts, ch. 7) ; la 7e traitait ces sujets dans Planification et Mesure. Synthèse reformulée.

## Concepts clés
- **Définition de la valeur** : chaque organisation la définit à sa façon (tangible ou non) ; elle guide les arbitrages de coût.
- **Maximisation de la valeur** : le domaine ne vise pas seulement à réduire le coût, mais à optimiser le rapport valeur/investissement.
- **Financement** : sources et calendrier des fonds ; le rythme de financement conditionne l'approche.
- **Contraintes financières** : le budget en est la principale.
- **Budget du projet** : se construit à partir des actifs organisationnels, des estimations et des réserves.
- **Baseline de coûts** : version approuvée du budget étalée dans le temps.
- **Réserves** : provisions pour risques identifiés (réserve pour imprévus) et pour inconnus (réserve de gestion) ; chacune a un propriétaire et des règles d'utilisation.
- **Gestion et mesure des coûts** : le coût vient surtout des ressources ; les parties prenantes le mesurent différemment (comptable, trésorerie, valeur du cycle de vie).

## Les 4 processus (8e)
| Processus | Objectif | Équivalent 6e |
|---|---|---|
| Planifier la gestion financière | Définir comment revenus et coûts seront estimés, budgétés, suivis | 7.1 |
| Estimer les coûts | Approximer le coût des ressources requises | 7.2 |
| Élaborer le budget | Agréger les estimations en baseline | 7.3 Déterminer le budget |
| Surveiller et maîtriser les finances | Suivre l'état financier, gérer les écarts | 7.4 Maîtriser les coûts |

## Valeur acquise (EVM) — formules de référence
- **PV** valeur planifiée ; **EV** valeur acquise ; **AC** coût réel ; **BAC** budget à l'achèvement.
- **CV = EV − AC** (écart de coût) ; **SV = EV − PV** (écart de délai).
- **CPI = EV / AC** ; **SPI = EV / PV** (> 1 favorable).
- **EAC** (estimation à l'achèvement) : BAC / CPI si l'écart persiste ; AC + (BAC − EV) si l'écart est ponctuel ; AC + nouvelle estimation du reste si le plan est caduc.
- **ETC = EAC − AC** ; **VAC = BAC − EAC** ; **TCPI** = (BAC − EV) / (BAC − AC).
Toujours exprimer les montants en dollars canadiens (CAD) lorsque le contexte est québécois.

## Adaptation
- Industries réglementées : contrôles financiers plus formels.
- Approches itératives : budget par incréments ; décisions de financement à chaque cycle.
- **Stratégie d'approvisionnement** : décision faire/acheter liée aux coûts (voir `pmbok-approvisionnement`).
- Disponibilité des ressources, définition de la valeur propre à chaque organisation.
- Petit projet : flexibilité limitée → prudence budgétaire ; secteur public : exigences accrues de responsabilité fiscale.

## Procédure d'élaboration d'un budget
1. Partir de la structure de portée et des durées ; estimer par composante (analogie, paramétrique, ascendante).
2. Ajouter les réserves selon les risques identifiés ; documenter leurs règles.
3. Étaler dans le temps pour obtenir la baseline ; vérifier la cohérence avec le financement.
4. Approuver via la gouvernance, puis suivre EV/AC/PV à intervalle fixe.

## Pièges
- Confondre budget (autorisé) et estimation (prévue).
- Réserves de gestion consommées comme budget normal.
- Ignorer les coûts du cycle de vie (exploitation, maintenance) dans la décision de valeur.

## Voir aussi
`pmbok-echeancier`, `pmbok-risque-incertitude` (réserves), `pmbok-approvisionnement`, `pmbok-gouvernance`.
