# Carte multi-agents — PMBOK skills

Ce fichier indique comment répartir les 18 skills entre des agents spécialistes. Un agent *orchestrateur* charge `pmbok-router`, classe la demande, puis délègue.

## Agents proposés

| Agent | Mission | Skills chargés |
|---|---|---|
| **Orchestrateur** | Classer la question, choisir l'édition, assembler la réponse | `pmbok-router`, `pmbok-evolution-des-editions` |
| **Stratège valeur** | Cadrer pourquoi, arbitrer selon la valeur, justifier | `pmbok-principes-valeur`, `pmbok-gouvernance`, `pmbok-pmo-et-ia` |
| **Architecte de méthode** | Choisir et adapter l'approche | `pmbok-cycles-de-vie-approches`, `pmbok-adaptation-tailoring`, `pmbok-extension-logicielle` |
| **Analyste portée et qualité** | Exigences, WBS/backlog, critères d'acceptation, qualité | `pmbok-portee`, `pmbok-qualite` |
| **Planificateur délais et coûts** | Estimer, ordonnancer, budgéter, prévoir | `pmbok-echeancier`, `pmbok-finance` |
| **Chargé d'engagement** | Parties prenantes, communication, équipe | `pmbok-parties-prenantes-communications`, `pmbok-ressources-equipe`, `pmbok-7e-domaines-modeles` |
| **Gestionnaire de risques et achats** | Risques, incertitude, sous-traitance, contrats | `pmbok-risque-incertitude`, `pmbok-approvisionnement` |
| **Archiviste de processus** | Questions de processus/ITTO, examen, migration d'édition | `pmbok-6e-processus-49`, `pmbok-evolution-des-editions` |

## Flux type
1. L'orchestrateur lit la demande, détermine le sujet dominant et l'édition (défaut : 8e).
2. Il appelle l'agent principal ; au plus deux agents complémentaires.
3. Chaque agent répond au format **Problème → Action → Bénéfice** et nomme son édition.
4. L'orchestrateur fusionne, résout les contradictions entre éditions et renvoie une recommandation unique.

## Exemples de routage
- « Mon projet logiciel prend du retard et le budget file » → Planificateur délais et coûts (principal), Architecte de méthode, Gestionnaire de risques.
- « Quel contrat choisir pour sous-traiter le développement ? » → Gestionnaire de risques et achats, Planificateur délais et coûts.
- « Quelle est la différence entre un groupe de processus et une zone de focus ? » → Archiviste de processus.
- « Comment encadrer l'usage de l'IA dans mon PMO ? » → Stratège valeur.

## Intégration technique
`skills-index.json` expose, pour chaque skill, son nom, son agent par défaut, ses mots-clés et ses éditions. Une orchestration automatisée peut charger cet index, faire correspondre les mots-clés de la demande, puis charger uniquement les `SKILL.md` retenus.
