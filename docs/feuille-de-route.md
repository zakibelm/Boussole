# Feuille de route de Boussole

Une phase ne démarre que lorsque le critère de sortie de la précédente est
démontré et que son rapport (réalisé, tests, benchmark, red team, écarts,
prochaine étape) est validé. Les dates se fixent à la fin de la phase 0.
Les ajouts issus de l'ADR 0003 (forces de monday.com) sont marqués ★; ceux de
l'ADR 0005 (écarts relevés par l'analyse d'octobre 2026) sont marqués ◆.

## Phase 0 : fondations (terminée, rapport : docs/rapports/phase-0.md)

Critère de sortie : une réponse sourcée et journalisée de bout en bout.

- [x] ADR de stack (0001)
- [x] Modèle de données versionné par migrations
- [x] Passerelle LLM : port commun, adaptateur OpenRouter, adaptateur factice, plafond de budget (ADR 0002)
- [x] ★ Page Paramètres : clé OpenRouter, modèle et skill versionné par agent, plafond de coût IA visible
- [x] Mémoire RAG : découpage par section, embeddings locaux, citations, droits par projet (ADR 0004)
- [x] Indexation du PMBOK 8 (401 pages, 847 extraits, sur le VPS) et PMBOK en skills par agent (ADR 0007)
- [x] Garde-fous : politique d'autonomie (config/autonomy.yaml), journal d'audit signé, séparation lecture et action (ADR 0006)
- [x] Benchmark reproductible (3 tâches PMO, 5 modèles via OpenRouter; jeu de base saturé, jeu difficile le 1er novembre)
- [x] CI : lint, types, tests, couverture, pip-audit, gitleaks, fichiers interdits (GitHub Actions)
- [x] Tests red team 1 à 3
- [x] Tests d'intégration PostgreSQL exécutés (dans la CI, service pgvector)
- [x] Critère de sortie démontré le 1er novembre : réponse sourcée et journalisée de bout en bout, extraits envoyés sans rétention (ADR 0008)
- [x] Modèle par défaut choisi par benchmark : GPT-5.6 Luna pour tous les agents

## Phase 1 : pilote (en cours)

Critère de sortie : validations humaines mesurées et valeur perçue positive.

- [x] Sélecteur d'approche (critères PMBOK 4.3, niveau augmentation) : propose avec citations, l'humain valide, modifie ou refuse (raison obligatoire)
- Chef de projet adaptatif et son équipe (Scrum Master, Product Owner et architecte)
- Domaines portée, échéancier et risque (assistance, avec citations)
- Connecteur en lecture seule vers l'outil du pilote
- Interface : chat et file de validations
- [x] ★ Création d'un projet en une conversation (page Projets)
- [x] ★ Tableau de bord par projet (livrables, tâches, retards, risques critiques, budget; chiffres tirés des données)
- [x] ★ Chat limité au projet courant (fiche du projet transmise comme donnée, réponses citées)
- ★ Configuration sans code : critères et pondérations du sélecteur, niveaux d'autonomie, modèles de projet
- ★ API publique
- ◆ Vues de travail : tableau et Kanban
- ◆ Formulaire de demande de projet, relié au sélecteur
- ◆ Notifications (courriel, Teams ou Slack) pour les validations en attente
- ◆ Validation sur mobile
- ◆ Alertes de coût IA avant le plafond
- ◆ Budget de performance mesuré en CI
- Jeu de référence de 10 projets, mesure du taux de modification et de refus
- Sondage de valeur perçue (5 questions)
- Tests red team 4 à 7

## Phase 2 : trois approches

Critère de sortie : sélecteur calibré par test sur des projets passés.

- Chefs de projet prédictif et hybride avec leurs équipes
- Domaines finance, parties prenantes, ressources
- Principes valeur, qualité, durabilité, éthique comme contrôles
- Suivi et clôture, leçons apprises validées puis indexées
- Calibrage du sélecteur, tests de biais et de régression en CI
- Matrice des responsabilités humaines
- ★ Agents créés par le PMO, sous garde-fous
- ★ Serveur MCP
- ★ Rapports alignés sur les six domaines, valeur et bénéfices
- ◆ Gantt avec dépendances, chemin critique et ligne de base
- ◆ Mode simulation des agents avant activation
- ◆ Modèles d'agents alignés sur le PMBOK
- ◆ Comptes rendus de réunion : décisions, actions, risques vers la file de validation
- ◆ Documents de projet générés (charte, statut, clôture), export Word et PDF

## Phase 3 : échelle

Critère de sortie : indicateurs du PMO en hausse, revue sécurité et juridique faite.

- Connecteurs complets, ★ ouverts aux connecteurs tiers sous le même contrat
- ◆ Synchronisation bidirectionnelle avec Jira, Azure DevOps, Microsoft Project
- Portefeuille, catalogue de services, maturité
- Tableau de bord du PMO (valeur et fiabilité de l'IA)
- Alerte sur un taux de modification humaine proche de zéro
- Résilience : mode dégradé, sauvegarde et restauration, plafonds par tâche
- ◆ Plafonds de coût IA par client
- ◆ Accès invité en lecture pour le client ou le commanditaire
- ◆ Authentification unique (SSO) et MFA
- Exploitation et dossier de revue
- ★ Grille tarifaire simple en dollars canadiens
