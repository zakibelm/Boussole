# Assistant IA de gestion de projet : structure et architecture

31 oct. 2026 · Zakaria Belmeddah

> Ce document fait foi (voir CLAUDE.md). Les deux schémas de l'original
> (architecture en couches, feuille de route) sont à exporter dans
> `docs/architecture/` : ils ne sont pas encore versionnés.

## Vision et périmètre

L'assistant est un PMO piloté par des agents IA : il aide à choisir la bonne
approche, planifier, suivre et clôturer des projets, sous validation humaine,
avec le PMBOK Guide 8e édition comme référence.

- **Pour qui :** le CEO et le responsable PMO décident; les chefs de projet et
  leurs équipes l'utilisent au quotidien.
- **Ce qu'il fait :** route chaque projet vers une approche prédictive,
  adaptative ou hybride, applique les 6 domaines de performance, produit plans,
  rapports et analyses de risque, puis conserve les leçons apprises.
- **Ce qu'il ne fait pas :** trancher seul les choix stratégiques (portefeuille,
  budget, arbitrages) ni agir sur des données privées sans garde-fous.
- **Principe directeur :** un humain nommé reste responsable de chaque décision
  (PMBOK, annexe X3).

## Architecture en couches

Cinq couches : humains, interface, agents, socle d'intégration IA, sources de
données. Le socle IA exécute les agents; chaque flèche est un échange dans les
deux sens, y compris la validation humaine vers le haut.

## Agents, rôles et niveaux d'autonomie

Chaque agent porte un niveau d'autonomie (annexe X3 du PMBOK) et un point de
validation humaine. Les trois chefs de projet sont les orchestrateurs et chefs
d'équipe : ils portent les compétences de leur méthode et appellent les six
domaines de performance.

| Agent | Rôle | Niveau | Validation humaine |
|---|---|---|---|
| Sélecteur d'approche | Route le projet selon les critères PMBOK 4.3 | Augmentation | CEO ou PMO approuve |
| Chef de projet prédictif | Orchestre planification et contrôle des jalons | Augmentation | L'humain décide |
| Chef de projet adaptatif | Orchestre sprints, backlog et rétrospectives | Augmentation | L'humain décide |
| Chef de projet hybride | Orchestre les méthodes combinées | Augmentation | L'humain décide |
| Planificateur, chemin critique | Équipe prédictive : calendrier et dépendances | Assistance | Révision |
| Jalons | Équipe prédictive : suivi des échéances | Automatisation | Aucune |
| Scrum Master | Équipe adaptative : cérémonies et obstacles | Assistance | Révision |
| Product Owner, architecte | Équipe adaptative : priorités et choix techniques | Augmentation | L'humain décide |
| Coordinateur, conformité | Équipe hybride : liaison et exigences réglementaires | Assistance | Révision |
| Suivi KPI | Équipe hybride : indicateurs | Automatisation | Aucune |
| Portée, échéancier, finance, risque | Domaines PMBOK 8 : plans et analyses | Assistance | Révision |
| Parties prenantes | Domaine PMBOK 8 : analyse de sentiment et communication | Augmentation | L'humain décide |
| Ressources | Domaine PMBOK 8 : suivi des tâches | Automatisation | Aucune |
| Suivi et clôture | Rapports et leçons apprises | Automatisation | Aucune |

## Sélecteur d'approche

Le sélecteur note le projet sur les critères officiels du PMBOK (section 4.3)
puis propose prédictif, adaptatif ou hybride; le CEO ou le PMO valide.

| Catégorie | Critère | Penche vers |
|---|---|---|
| Livrables | Exigences connues et stables | Prédictif |
| Livrables | Innovation forte, portée instable | Adaptatif |
| Livrables | Changement difficile ou coûteux | Prédictif |
| Livrables | Exigences de sécurité, forte réglementation | Prédictif |
| Livrables | Rétroaction fréquente utile, risque élevé | Adaptatif |
| Projet | Date de fin fixe | Prédictif |
| Projet | Valeur à livrer tôt, financement incertain | Adaptatif |
| Projet | Parties prenantes très impliquées | Adaptatif |
| Projet | Interdépendances nombreuses | Itératif ou hybride |
| Organisation | Structure fonctionnelle et hiérarchique | Prédictif |
| Organisation | Structure en réseau, équipes autogérées | Adaptatif ou hybride |
| Organisation | Équipe de 3 à 9 personnes | Adaptatif |

Règle de départ : quand les signaux divergent selon les livrables, le
sélecteur propose l'hybride; plusieurs approches peuvent coexister dans un même
projet. Les pondérations se calibrent par test sur des projets passés, pas par
intuition.

## Socle d'intégration IA

Le socle exécute les agents; chaque composant est remplaçable sans toucher aux
agents.

| Composant | Rôle | Conception modulaire | Preuve de qualité |
|---|---|---|---|
| Interface | Chat, tableau de bord, alertes et validations | Une seule API pour tous les canaux | Temps de réponse perçu |
| Passerelle LLM | Point d'entrée unique vers les modèles, routage par tâche | Fournisseurs interchangeables derrière une interface commune | Benchmark réel par tâche avant tout changement |
| Orchestration | Enchaîne les agents et déclenche les workflows | Un agent = un workflow versionné | Taux d'exécution sans erreur |
| Mémoire (RAG) | PMBOK 8, modèles, historique de projets, décisions | Base vectorielle avec droits d'accès par projet | Sources citées et vérifiables |
| Outils et connecteurs | Lecture et écriture dans tâches, agenda, finance, messages | Un connecteur par outil, même contrat d'interface | Actions journalisées et réversibles |
| Garde-fous | Validation humaine, audit, vie privée, limites d'action | Politique d'autonomie appliquée avant chaque action | Aucune action sans trace |
| Mesure | Qualité, coûts, biais | Tableau de bord et tests de régression | Indicateurs de la section Mesure |

## Modèle de données

Un projet relie tout le reste; chaque décision et chaque action d'agent laisse
une trace.

| Entité | Contenu clé | Relations |
|---|---|---|
| Portefeuille | Projets, priorités, ressources disponibles | Contient les projets |
| Projet | Approche choisie, phase, valeur attendue | Appartient à un portefeuille; a des livrables, risques, décisions |
| Livrable et tâche | Échéance, responsable, statut | Appartient à un projet; utilise des ressources |
| Risque | Probabilité, impact, réponse | Lié à un projet et à des tâches |
| Budget | Prévu, réel, écarts | Lié à un projet et à des livrables |
| Partie prenante | Rôle, attentes, historique d'échanges | Liée à des projets |
| Ressource | Compétences, disponibilité | Affectée à des tâches |
| Décision | Options, choix, personne responsable | Liée à un projet; validée par un humain |
| Journal d'agent | Agent, action, sources utilisées, niveau d'autonomie | Lié à une décision ou une tâche |
| Document de connaissance | Extrait, source, version | Alimenté par le PMBOK 8, les modèles et les leçons apprises |

## Cycle de vie de bout en bout

Les cinq axes de focus du PMBOK structurent le parcours; chaque axe a ses
agents et son point de validation.

| Axe de focus | Ce que fait l'assistant | Agents | Validation humaine |
|---|---|---|---|
| Initiation | Qualifie le projet, propose l'approche, esquisse la charte | Sélecteur, parties prenantes | CEO ou PMO approuve l'approche |
| Planification | Construit portée, calendrier, budget, plan de risques | Chef de projet et domaines | Chef de projet valide les plans |
| Exécution | Suit les tâches, coordonne l'équipe, gère les ressources | Équipe dédiée, ressources | Selon le niveau d'autonomie |
| Suivi et maîtrise | Détecte les écarts, alerte, recommande des corrections | Suivi KPI, risque, finance | Responsable valide les corrections |
| Clôture | Rassemble livrables et leçons apprises, mesure les bénéfices | Suivi et clôture | PMO accepte la clôture |

Les leçons apprises retournent dans la mémoire (RAG) : les projets suivants
s'en servent dès l'initiation.

## Gouvernance IA et conformité

Les règles ci-dessous s'appliquent à chaque agent avant qu'il agisse.

- **Autonomie :** l'automatisation agit seule sur des tâches à faible risque;
  l'assistance produit un brouillon qu'un humain révise; l'augmentation laisse
  l'humain décider, l'IA conseille.
- **Responsabilité :** chaque décision a un humain nommé; l'IA n'est jamais
  responsable.
- **Audit :** chaque action d'agent est journalisée avec ses sources et son
  niveau d'autonomie.
- **Biais :** tests périodiques sur les recommandations, avec des jeux de
  données variés.
- **Vie privée :** accès par droits, données sensibles protégées, conformité
  aux lois applicables (par exemple la Loi 25 au Québec).
- **Fournisseurs de modèles :** retenir des offres qui n'entraînent pas les
  modèles sur nos données, comme le PMBOK le recommande pour protéger la
  propriété intellectuelle (annexe X3.1.2).

## Mesure et amélioration continue

Deux familles d'indicateurs : la valeur du PMO et la fiabilité de l'IA. Les
cibles se fixent après la phase pilote, pas avant.

| Famille | Indicateur | Source |
|---|---|---|
| Valeur du PMO | Délai entre une demande et une décision | Journal des décisions |
| Valeur du PMO | Écart entre budget prévu et réel | Domaine finance |
| Valeur du PMO | Risques traités avant d'échouer | Domaine risque |
| Valeur du PMO | Bénéfices réalisés contre attendus | Suivi et clôture |
| Valeur perçue | Satisfaction des chefs de projet et de la direction | Sondage trimestriel |
| Fiabilité IA | Part des sorties modifiées ou refusées par un humain | Journal d'agent |
| Fiabilité IA | Justesse des recommandations sur des projets passés | Test de régression |
| Fiabilité IA | Coût par tâche (en dollars canadiens) | Passerelle LLM |
| Fiabilité IA | Biais détectés | Tests périodiques |

## Feuille de route

Voir `docs/feuille-de-route.md`. Le pilote est la phase clé : il prouve la
valeur avant d'élargir le périmètre. Les dates se fixent à la fin de la
phase 0.

## Risques, actions et bénéfices

| Problème | Action | Bénéfice |
|---|---|---|
| Recommandations fausses ou sans source | Réponses fondées sur la mémoire RAG, sources citées, validation selon le niveau | Décisions défendables devant un client |
| Dépendance à un fournisseur de modèles | Passerelle LLM modulaire et benchmark par tâche | Changer de modèle sans réécrire les agents |
| Données privées exposées | Droits d'accès, garde-fous, fournisseurs sans réentraînement | Conformité et confiance |
| Biais dans les recommandations | Tests périodiques et jeux de données variés | Équité mesurable |
| Valeur perçue trop faible auprès des équipes | Catalogue de services centré sur le client, pilote court (PMBOK X2) | Adoption plus rapide |
| Projet trop vaste dès le départ | Feuille de route en phases avec critères de sortie | Valeur dès le pilote |
| Responsabilité floue | Humain nommé par décision et journal d'agent | Traçabilité complète |

## Matrice de couverture

| Élément de l'architecture | Composant de la solution | Section |
|---|---|---|
| Gouvernance PMO et CEO | Validation humaine, décisions | Agents; Gouvernance IA |
| Contexte, portfolio et ressources | Entités Portefeuille, Ressource, Partie prenante | Modèle de données |
| Sélecteur d'approche | Agent sélecteur et critères PMBOK 4.3 | Sélecteur d'approche |
| Chefs de projet waterfall, agile, hybride | Trois orchestrateurs et équipes dédiées | Agents |
| Six domaines de performance | Agents de domaine appelés par les chefs de projet | Agents |
| Principes : valeur, qualité, durabilité, éthique | Contrôles appliqués à chaque domaine | Gouvernance IA |
| Suivi, clôture, leçons apprises | Agent de suivi, retour dans la mémoire | Cycle de vie |
| Niveaux d'autonomie | Automatisation, assistance, augmentation | Agents; Gouvernance IA |
| Intégration IA | Passerelle LLM, orchestration, RAG, outils, garde-fous, mesure | Socle d'intégration IA |
| Sources de données | Connecteurs vers projets, finance, documents, messages | Socle d'intégration IA |
| Maturité et catalogue de services du PMO | Services adaptés au client, pilote puis échelle | Feuille de route; Risques |
| Marché : forces à importer | Création en une conversation, tableau de bord par projet, configuration sans code, agents créés par le PMO, API et MCP, prix simples en CAD | Marché; ADR 0003 |

## Marché : comparatif et forces à importer

Au 31 octobre 2026, monday.com combine le plus d'avis et la meilleure note
parmi les plateformes généralistes : ses forces servent de modèle d'adoption
pour Boussole, ses faiblesses de point de différenciation. Les notes évaluent
les plateformes dans leur ensemble, pas leurs agents IA, qui ont encore peu
d'avis isolés.

| Outil | Note | Avis |
|---|---|---|
| monday.com | 4,7 sur G2; 4,6 sur Capterra | environ 15 000 (G2) |
| Asana | 4,5 sur Capterra | environ 13 600 |
| ClickUp | 4,6 sur Capterra | environ 4 600 |
| Smartsheet | 4,5 sur Capterra | environ 3 500 |
| Microsoft Planner | 4,3 sur Capterra | environ 290 |
| Planview Portfolios | 8,5 sur 10 sur TrustRadius; 3,8 sur G2 | 177 (TrustRadius), environ 85 (G2) |

### Forces de monday.com à importer

| Force observée | Ce qu'on importe dans Boussole | Bénéfice |
|---|---|---|
| Facilité d'utilisation notée 4,5 et prise en main rapide | Création d'un projet en une conversation : l'utilisateur décrit son projet, le sélecteur propose l'approche, un modèle se remplit | Adoption rapide, premier résultat en quelques minutes |
| Tableaux de bord visuels et partageables | Un tableau de bord par projet dès la phase 1, pas seulement en phase 3 | Valeur visible dès le pilote |
| Flux de travail très personnalisables, sans code | Modèles par type de projet et configuration modifiable par le PMO (critères du sélecteur, niveaux d'autonomie) dans une interface | Le PMO adapte l'outil sans développeur |
| Agents et automatisations créables par l'utilisateur | Création d'agents et de règles par le PMO, toujours soumis aux garde-fous et aux niveaux d'autonomie | Flexibilité sans perdre le contrôle |
| Assistant ancré dans le contexte du projet | Chat limité au projet courant, avec sources citées de la mémoire RAG | Réponses pertinentes et vérifiables |
| Ouverture : API, marketplace, MCP, agents tiers | Exposer Boussole par API et MCP, et accepter des connecteurs tiers sous le même contrat | Intégration dans les outils déjà utilisés par les clients |

### Faiblesses à éviter

| Problème | Action | Bénéfice |
|---|---|---|
| Structure de prix perçue comme élevée et confuse, IA facturée en crédits | Grille tarifaire simple, en dollars canadiens, avec plafond de coût IA visible | Confiance des PME, achat plus rapide |
| Profondeur de reporting jugée limitée par certains utilisateurs | Rapports alignés sur les six domaines PMBOK 8, avec suivi de la valeur et des bénéfices réalisés | Argument de différenciation face aux outils généralistes |

Sources : Capterra, avis monday.com, G2, comparatif monday.com, Planner,
TrustRadius, Planview, comparatif avec ClickUp. Notes relevées en octobre 2026.
