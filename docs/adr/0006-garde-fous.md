# ADR 0006 : garde-fous, portail d'action et journal signé

- **Statut :** accepté le 2026-10-31 par Zakaria Belmeddah (tâche 5 de la phase 0)
- **Date :** 2026-10-31

## Décision

1. **Un seul chemin vers l'effet : le portail d'action** (`ActionGate`). Les
   agents et les modèles proposent; le portail décide, journalise, puis exécute.
   `read` n'accepte que des lectures; toute écriture passe par `act`.
2. **Niveau effectif = le plus restrictif** entre le niveau de l'action
   (`config/autonomy.yaml`) et le plafond de l'agent (`config/agents.yaml`).
   Le plafond borne les **effets**, pas la lecture : un agent en augmentation
   (sélecteur, Product Owner) doit pouvoir lire son projet pour conseiller.
   Le plafond vient toujours du catalogue, jamais de la requête de l'agent.
3. **Règles non configurables :** action inconnue refusée; action irréversible
   validée seulement par un humain nommé ayant un rôle autorisé; action inspirée
   par un contenu externe ramenée au moins en assistance; hors du projet de
   l'agent ou hors liste blanche réseau, refus même avec validation.
4. **Journal d'audit** : chaque entrée est chaînée à la précédente (SHA-256)
   et signée (HMAC-SHA256). La base refuse UPDATE, DELETE et TRUNCATE. La
   vérification nomme la première entrée altérée et la nature de l'altération.
5. **Échec fermé** : la décision est journalisée avant l'effet; sans journal
   (clé absente, base indisponible), rien n'est exécuté.
6. **Clé de signature** : créée par un humain (`audit.cli init-key`), rangée
   dans le Gestionnaire d'identifiants Windows, jamais remplacée sans décision
   explicite, car une nouvelle clé rend l'ancien journal invérifiable.

## Conséquences

- Les tests red team 1 à 3 sont automatisés (`tests/redteam/`).
- La rotation de la clé (phase 3) devra signer un point de passage de
  l'ancienne clé vers la nouvelle.
- La file de validation (phase 1) consommera les décisions `needs_human`.
