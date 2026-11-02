# monday.com et Boussole : analyse des écarts (octobre 2026)

Analyse fonctionnelle à partir de sources publiques seulement (site, blogue,
avis). Aucune rétro-ingénierie du service : les conditions d'utilisation de
monday.com l'interdisent, et ce qui compte pour Boussole, ce sont les fonctions
offertes, pas leur implémentation.

## Ce que monday.com offre (2026)

| Domaine | Fonction | Remarque |
|---|---|---|
| Vues | Tableau, Kanban, Gantt, chronologie, calendrier, charge de travail, carte, sur les mêmes données | Gantt avec dépendances, chemin critique et lignes de base |
| Tableaux de bord | Widgets en direct sur plusieurs tableaux | De 1 à 50 tableaux selon le forfait |
| Automatisations | Déclencheur, condition, action, sans code | 250 à 250 000 actions par mois selon le forfait |
| Portefeuille | Vue exécutive, santé et dépendances entre projets | Forfait Enterprise seulement |
| Ressources | Vue de charge par personne et par équipe | Gestion des ressources : Enterprise seulement |
| Demandes | Formulaires d'entrée avec circuit d'approbation | |
| Documents | Documents collaboratifs reliés aux données | |
| Intégrations | Plus de 850 applications, synchronisation bidirectionnelle (Jira, GitHub) | |
| Sidekick | Assistant qui lit tableaux, documents et applications connectées, puis crée et modifie | Limité en messages par jour selon le forfait |
| Agents | Agents personnalisables pour des processus récurrents (triage, notation, alertes de risque) | Permissions, journal des actions et du raisonnement, mode simulation |
| Vibe | Vues, tableaux de bord et mini-applications générés à partir d'une phrase | Facturé en crédits |
| Blocs IA et flux IA | Classer, résumer, extraire, traduire, sentiment, avec étapes d'approbation | Crédits |
| Preneur de notes IA | Transcription, résumé, actions avec responsables | |
| MCP et API | Claude, ChatGPT, Copilot… agissent dans l'espace de travail, OAuth 2.1, mêmes droits que l'utilisateur | Sans frais, limites d'API |
| Centre de coûts IA | Consommation par équipe, plafonds et alertes | 500 crédits gratuits par mois, puis achat |
| Confiance | SOC 1/2/3, ISO 27001, MFA, journal d'audit; pas d'entraînement sur les données des clients | Accès temporaire aux données jusqu'à 60 jours, sauf désactivation sur demande |

Faiblesses relevées dans les avis : lenteurs ponctuelles, application mobile
moins complète, prix élevé pour les petites équipes, plafond atteint par les
organisations qui grandissent, portefeuille et ressources réservés au forfait
le plus cher, IA facturée en crédits.

## Écarts : ce qui manque à Boussole

Les forces déjà retenues dans l'ADR 0003 (création en une conversation, tableau
de bord par projet, configuration sans code, agents créés par le PMO, chat
limité au projet, API et MCP, prix en CAD) ne sont pas répétées ici.

| # | Écart | Pourquoi c'est utile à Boussole | Phase | Garde-fou |
|---|---|---|---|---|
| 1 | **Vues de travail** : tableau et Kanban, puis Gantt avec dépendances, chemin critique et ligne de base | Les agents produisent des plans; sans vue où les manipuler, les équipes gardent leur ancien outil | Kanban et tableau : 1 (adaptatif); Gantt et ligne de base : 2 (prédictif) | Une modification par un agent est une écriture réversible, journalisée |
| 2 | **Formulaire de demande de projet** pour les personnes hors de l'outil, qui alimente le sélecteur | Le portefeuille commence par la demande; c'est l'entrée naturelle du cycle d'initiation | 1 | Le contenu du formulaire est une donnée, jamais une instruction |
| 3 | **Notifications** (courriel, Teams ou Slack) pour les validations en attente et les alertes | Le délai de décision est un indicateur clé du PMO : il dépend des relances | 1 | Aucun envoi sans destinataire prévu par la matrice des responsabilités |
| 4 | **Validation sur mobile** (interface adaptée au téléphone) | Le CEO et le PMO valident souvent hors du bureau; point faible noté chez monday | 1 | Mêmes contrôles d'identité qu'au bureau |
| 5 | **Plafonds de coût IA par projet et par client, avec alertes** | Le plafond global ne suffit pas dès qu'il y a plusieurs clients | Alertes : 1; par client : 3 | Arrêt automatique au plafond |
| 6 | **Mode simulation des agents** : voir ce qu'un agent ferait, sans effet, avant de l'activer | Condition pour laisser le PMO créer des agents en confiance | 2 | Aucune écriture en simulation, même réversible |
| 7 | **Modèles d'agents alignés sur le PMBOK** (point de départ pour le PMO) | Accélère la création d'agents sans partir de zéro | 2 | Un modèle hérite des règles communes et de son plafond d'autonomie |
| 8 | **Comptes rendus de réunion** : décisions, actions, risques extraits vers la file de validation | Gain de temps quotidien très visible pour les chefs de projet | 2 | Assistance : rien n'entre au projet sans révision; la transcription brute n'est pas conservée au-delà du traitement |
| 9 | **Documents de projet générés** (charte, rapport de statut, clôture), exportables en Word et PDF | Livrables attendus par les clients et la direction | 2 | Chiffres tirés des données, sources citées |
| 10 | **Accès invité en lecture** pour le client ou le commanditaire (tableau de bord du projet) | Partage de la valeur sans licence supplémentaire | 3 | Consentement et minimisation (Loi 25), lien révocable |
| 11 | **Synchronisation bidirectionnelle** avec Jira, Azure DevOps, Microsoft Project | Les équipes techniques ne quitteront pas leur outil | 3 | Écriture réversible journalisée; jamais d'action irréversible |
| 12 | **Authentification unique (SSO) et MFA** | Exigence d'achat des moyennes et grandes organisations | 3 | |
| 13 | **Budget de performance** : temps de réponse mesuré et suivi en CI | Les lenteurs sont la plainte récurrente sur monday | 1 | Alerte si le seuil fixé après le pilote est dépassé |

## Ce que Boussole fait déjà mieux, à garder

- Réponses fondées sur le PMBOK, avec sources citées, ou l'aveu qu'il n'y en a pas.
- Un humain nommé pour chaque décision; niveaux d'autonomie par type d'action.
- Portefeuille et ressources dans l'offre de base, pas réservés au forfait le plus cher.
- Coûts en dollars canadiens, plafond visible, jamais de crédits.
- PMBOK indexé en local; conformité à la Loi 25 codée dans le produit.

## Sources

- [Everything monday AI can do (blogue monday.com)](https://monday.com/blog/ai-agents/everything-monday-ai-can-do/)
- [monday.com accueille les agents IA (communiqué, mars 2026)](https://ir.monday.com/news-and-events/news-releases/news-details/2026/monday-com-Welcomes-AI-Agents-to-Its-Platform-Marking-a-Shift-in-How-Work-Gets-Done/)
- [AI 2026 : nouveautés (communauté monday.com)](https://community.monday.com/t/ai-2026-what-s-new-and-what-s-coming/123164)
- [monday.com Features : A Complete Breakdown in 2026 (ZoomInfo)](https://pipeline.zoominfo.com/sales/monday-com-features)
- [Monday.com for Portfolio Management (Acuity PPM)](https://acuityppm.com/monday-com-for-portfolio-management/)
- [Avis monday.com (Capterra)](https://www.capterra.com/p/147657/monday-com/reviews/?page=2)
