# ADR 0009 : déploiement versionné sur le VPS

- **Statut :** accepté le 2026-11-01 par Zakaria Belmeddah (« meilleures décisions selon
  les bonnes pratiques »)
- **Date :** 2026-11-01

## Contexte

Boussole tourne sur un VPS (Docker, nginx, HTTPS, mot de passe), mais aucun fichier de
déploiement n'était dans le dépôt : montage manuel, sans retour arrière testé, contraire
à CLAUDE.md (aucune étape manuelle cachée; livraison avec retour arrière). L'audit du
1er novembre n'a pas pu vérifier le point le plus sensible : nginx réécrit-il
`X-Remote-User`, et l'application est-elle joignable sans lui ?

## Décision

1. **Image Docker** (`infra/deploy/Dockerfile`) : Python 3.12, dépendances figées par
   `uv.lock`, compte non root (uid 10001), sonde `/health`, **un seul processus** (le verrou
   du journal et les réservations de budget sont propres au processus).
2. **Compose de production** (`infra/deploy/compose.prod.yml`) : port lié à `127.0.0.1`
   seulement, système de fichiers en lecture seule, aucun privilège, mémoire plafonnée,
   journaux bornés. Données et secrets dans `/srv/boussole/{data,secrets}` sur l'hôte.
3. **Base : SQLite en mode léger**, comme aujourd'hui, pour ne pas toucher au journal signé
   en production. Le passage à PostgreSQL (cible de l'ADR 0001) fera l'objet d'une migration
   distincte, avec vérification du journal avant et après.
4. **Secrets : coffre par fichier** (`keyrings.alt`, déjà utilisé sur le serveur) dans
   `/srv/boussole/secrets`, accessible à l'uid 10001 seul. Ils sont en clair sur le disque :
   la protection repose sur les droits Unix et des sauvegardes lisibles par root seul.
   Un coffre chiffré est un chantier de la phase 3 (rotation des secrets).
5. **nginx sur l'hôte avec certbot** (`infra/deploy/nginx/boussole.conf`) : un compte par
   personne, `X-Remote-User` toujours réécrit, `X-Forwarded-Host` vidé, HSTS, CSP sans CDN,
   limite de débit sur les POST (appels payants et décisions).
6. **Scripts** : `deploy.sh` (sauvegarde, image étiquetée par le commit, sonde de santé,
   retour automatique à la version précédente si elle échoue), `rollback.sh`, `backup.sh`
   (copie cohérente de SQLite en service, rétention 14 jours), cron quotidien de
   sauvegarde et d'ancre du journal.
7. **CI** : l'image est construite à chaque PR, et les scripts sont vérifiés.

## Conséquences

- Un déploiement = une commande et un commit; revenir en arrière = une commande.
- La première bascule depuis le montage manuel est une opération humaine, une seule fois
  (`docs/runbooks/deploiement.md`, section « Migration »).
- L'étiquette de l'image Python n'est pas encore figée par empreinte : à faire après la
  première construction sur le VPS (noter l'empreinte dans le Dockerfile).
