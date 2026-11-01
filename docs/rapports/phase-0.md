# Rapport de fin de phase 0 : fondations

- **Date :** 2026-11-01
- **Critère de sortie :** une réponse sourcée et journalisée de bout en bout.
- **Statut :** démontré le 2026-11-01 sur boussole.optigenius.pro; à valider par
  Zakaria Belmeddah (la fusion de la PR vaut validation).

## Critère de sortie : démonstration

Commande lancée sur le serveur (`python -m boussole.agents.answer_cli`) :

| | Sélecteur d'approche | Domaine Risque |
|---|---|---|
| Question | Quels critères permettent de choisir entre une approche prédictive, adaptative ou hybride ? | Comment traiter une menace identifiée dans le registre des risques ? |
| Parties du PMBOK consultées | Tout le livre (orchestrateur) | Guide 2.7 Risque, sections 4 et 5, glossaire |
| Sources fournies | 5 extraits, dont 4.2.3 « Hybrid Approaches » p. 88-89 | 5 extraits : 2.7.2 p. 199, 2.7.2.4 p. 202, 2.7.2.1 p. 200, 2.7.4 p. 206, section 4 p. 242-243 |
| Sources citées dans la réponse | 4 sur 5 (détecteur corrigé ensuite, voir écarts) | [1], [2], [3], [5] |
| Modèle | openai/gpt-5.6-luna, fournisseur sans rétention | idem |
| Coût | 0,0023 $ CA | 0,0019 $ CA |
| Journal | entrées 1 à 3, une corrélation | entrées 4 à 6, une corrélation |

`python -m boussole.platform.audit.cli verify` : **journal intègre, 6 entrées
vérifiées** (chaînage, contenu et signature HMAC). Le journal contient les
citations, le modèle, le coût et une empreinte de la réponse, jamais le texte du
PMBOK. Quand une question sort de ses sources, l'agent le dit (« non couverts
par les sources fournies ») au lieu d'inventer.

## Réalisé

- Stack et ADR 0001 à 0008 : FastAPI, SQLAlchemy, PostgreSQL ou SQLite léger,
  passerelle OpenRouter, mémoire RAG locale, garde-fous, PMBOK en skills,
  extraits sans rétention.
- Passerelle LLM : port commun, adaptateurs OpenRouter et factice, plafond de
  20 $ CA, coûts en $ CA.
- Page Paramètres : clé, modèle par agent (menu de 416 modèles OpenRouter,
  gratuits d'abord, recherche), skill versionné et réversible, raffinement par
  l'IA, budget visible.
- Mémoire RAG : PMBOK 8 indexé sur le VPS (401 pages, 847 extraits), citations
  section et page, droits par projet, recherche limitée aux parties de l'agent.
- Garde-fous : politique d'autonomie par type d'action, portail d'action en
  échec fermé, journal d'audit en ajout seul, chaîné et signé.
- Réponse sourcée de bout en bout (critère de sortie), modèle par défaut choisi
  par benchmark : GPT-5.6 Luna pour les 22 agents.
- Déploiement : VPS Hostinger, Docker, nginx avec HTTPS et mot de passe.

## Tests

- 265 tests réussis, 7 sautés (PostgreSQL, exécutés dans la CI avec pgvector).
- ruff, ruff format et mypy strict sans erreur sur 64 fichiers.
- CI GitHub Actions : lint, types, tests, couverture, pip-audit, gitleaks,
  fichiers interdits.
- Nouveaux tests du critère de sortie : réponse citée et journalisée, aucun
  texte protégé au journal, parties du livre propres à l'agent, envoi sans
  rétention, aucune source donc aucun appel, budget épuisé, agent inconnu,
  détection des citations sous toutes leurs formes.

## Benchmark

Détail dans `bench/results/README.md`.

- Jeu de base (20 cas) : saturé, Gemini 3.8 Flash, Mistral Large 4 et
  GPT-5.6 Luna à 1,00.
- Jeu difficile (16 cas) : GPT-5.6 Luna 0,88; Haiku 0,83; Gemini 3.8 Flash
  0,78; Sonnet 0,75; Mistral Large 4 0,72. Luna est aussi le moins cher et le
  plus rapide : modèle par défaut retenu.
- Dépense totale de la phase : environ 1,41 $ CA sur 20 $ CA (benchmark
  1,40 $ CA, démonstration 0,004 $ CA).

## Red team

- Tests 1 à 3 verts (8 tests) : injection dans un document sans effet, aucune
  lecture ni sortie hors du projet et de la liste blanche, action irréversible
  refusée sans humain nommé.
- Ajout de la phase : les extraits sont balisés comme données dans le prompt
  (« jamais des instructions »), et le journal est vérifié sans texte protégé.

## Écarts

| Écart | Action proposée | Bénéfice |
|---|---|---|
| ha01 et ha02 ratés par les 5 modèles : le skill du sélecteur impose l'hybride dès que les signaux divergent | Préciser le skill (le livrable prime sur la préférence de l'équipe) ou étiqueter ces cas « hybride » : décision du PMO | Sélecteur calibré avant la phase 1 |
| La première démonstration affichait « citées : aucune » : le modèle cite au format « [4 — section 4.2.3, p. 88] » | Détecteur élargi et testé sur 4 formats, redéployé | Mesure fiable du taux de citation |
| Journal démarré le 2026-11-01 : la clé de signature n'existait pas avant | Clé créée par Zakaria Belmeddah; toute écriture sans clé est refusée | Aucune entrée non signée |
| Interface limitée à Paramètres; la réponse sourcée passe par la ligne de commande | Chat et file de validations en tête de la phase 1 | Démonstration accessible depuis le site |

## Prochaine étape

Phase 1, en commençant par ce qui rend Boussole utilisable depuis le site : le
chat (création d'un projet en une conversation, réponse sourcée affichée avec
ses citations), puis le tableau de bord par projet et la file de validations.
