# Feuille de route de Boussole

Une phase ne démarre que lorsque le critère de sortie de la précédente est
démontré et que son rapport (réalisé, tests, benchmark, red team, écarts,
prochaine étape) est validé. Les dates se fixent à la fin de la phase 0.
Les ajouts issus de l'ADR 0003 (marché) sont marqués ★.

## Phase 0 : fondations (en cours)

Critère de sortie : une réponse sourcée et journalisée de bout en bout.

- [x] ADR de stack (0001)
- [x] Modèle de données versionné par migrations
- [x] Passerelle LLM : port commun, adaptateur OpenRouter, adaptateur factice, plafond de budget (ADR 0002)
- [x] ★ Page Paramètres : clé OpenRouter, modèle et skill versionné par agent, plafond de coût IA visible
- [ ] Mémoire RAG : ingestion locale du PMBOK 8, citations
- [ ] Garde-fous : politique d'autonomie (config/autonomy.yaml), journal d'audit signé, séparation lecture et action
- [ ] Benchmark reproductible (3 tâches PMO, au moins 2 modèles via OpenRouter)
- [ ] CI : lint, types, tests, scan des dépendances et des secrets
- [ ] Tests red team 1 à 3
- [ ] Tests d'intégration PostgreSQL exécutés (en attente de Docker)

## Phase 1 : pilote

Critère de sortie : validations humaines mesurées et valeur perçue positive.

- Sélecteur d'approche (critères PMBOK 4.3, niveau augmentation)
- Chef de projet adaptatif et son équipe (Scrum Master, Product Owner et architecte)
- Domaines portée, échéancier et risque (assistance, avec citations)
- Connecteur en lecture seule vers l'outil du pilote
- Interface : chat et file de validations
- ★ Création d'un projet en une conversation
- ★ Tableau de bord par projet
- ★ Chat limité au projet courant
- ★ Configuration sans code : critères et pondérations du sélecteur, niveaux d'autonomie, modèles de projet
- ★ API publique
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

## Phase 3 : échelle

Critère de sortie : indicateurs du PMO en hausse, revue sécurité et juridique faite.

- Connecteurs complets, ★ ouverts aux connecteurs tiers sous le même contrat
- Portefeuille, catalogue de services, maturité
- Tableau de bord du PMO (valeur et fiabilité de l'IA)
- Alerte sur un taux de modification humaine proche de zéro
- Résilience : mode dégradé, sauvegarde et restauration, plafonds par tâche
- Exploitation et dossier de revue
- ★ Grille tarifaire simple en dollars canadiens
