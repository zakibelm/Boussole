# ADR 0010 : leader de suivi continu et connaissances métier dans l'image

Statut : proposée (décision du PMO requise, voir « Décisions demandées »).

## Contexte
Boussole conseille bien à la demande, mais personne ne suit le projet entre deux
conversations. Un prototype hors dépôt (SQLite, sans dépendance) a validé le
comportement d'un chef de projet IA qui assure le suivi, avec 5 scénarios de bout en bout
verts. Cet ADR décrit ce qu'il faut reprendre dans l'architecture existante
(ports et adaptateurs, PostgreSQL, `config/autonomy.yaml`). Le prototype n'entre pas dans
le dépôt : il n'a ni les ports, ni le typage strict, ni la base de la stack (ADR 0001).

## Décision proposée
Ajouter un **leader de suivi** : une boucle périodique (`tick`, planifiée par n8n ou cron)
qui lit l'état de chaque projet en cours d'exécution et réagit selon des règles
déterministes. Le modèle ne sert qu'à rédiger.

| Signal | Réaction | Niveau d'autonomie |
|---|---|---|
| Retard, tâche sans mise à jour, tâche sans responsable | Badge au responsable ; alerte à l'admin du projet si retard > 2 j | Automatisation |
| Tâche bloquée, goulot (≥ 2 tâches en dépendent) | Alerte à l'admin avec une piste tirée d'une leçon validée | Automatisation |
| SPI ou CPI < 0,9 | Proposition de replanification | Augmentation |
| Courriel de relance, ticket Jira | Brouillon, validé par un humain avant envoi | Assistance |
| Validation en retard | Rappel, puis escalade admin du projet, puis super admin ; jamais d'approbation automatique | Automatisation |

Règles reprises du prototype :
- Un même signal n'est pas répété avant 3 jours.
- Seuls des membres humains enregistrés valident ; un refus exige une justification, qui
  alimente les leçons apprises (validées par le PMO avant indexation, voir CLAUDE.md).
- Pas de courriel sans consentement du destinataire (CASL).
- Mise à jour d'une tâche réservée à son responsable ou à l'admin du projet.
- Rappel unique d'une leçon d'échec proche d'une décision envisagée ; l'humain décide.

Les actions sont ajoutées à `config/autonomy.yaml` (une ligne par type d'action) ; le
journal d'audit signé existant remplace le journal du prototype.

## Connaissances métier dans l'image
Les 18 skills PMBOK (synthèses reformulées des éditions 6, 7, 8 et de l'Extension
logicielle) sont versionnés dans `config/knowledge/pmbok-skills/`. Le Dockerfile copie
`config/` : ils sont dans chaque image, sans manipulation au déploiement. Ils complètent
la mémoire RAG (texte des livres, dans le volume `data/local/`, jamais dans git) ;
chaque affirmation normative reste citée avec section et page.

## Conséquences
- Réponse à l'écart « personne ne suit » de la phase 1 (chef de projet adaptatif et son
  équipe) et préparation de la phase 2 (suivi et clôture).
- Un port `SkillKnowledge` charge les skills par agent ; l'index `skills-index.json`
  sert d'aiguillage par mots-clés.
- Coût IA : le suivi est déterministe, seule la rédaction consomme (plafond en dollars
  canadiens existant).

## Décisions demandées au PMO
1. Accepter ou refuser cette direction (point d'arrêt : structurant).
2. Si acceptée : première PR de code = port `SkillKnowledge` + lecture des skills par
   agent ; deuxième PR = `tick` en lecture seule sur un projet de test.
3. Indexer les éditions 6, 7 et l'Extension logicielle dans la mémoire RAG du VPS avec la
   commande existante (`ingest`, option `--source`), une seule fois, dans `data/local/`.
