# Déployer Boussole sur le VPS

Décisions : ADR 0009. Fichiers : `infra/deploy/`. Toutes les commandes en root sur le VPS,
dépôt cloné dans `/opt/boussole/src`.

## Déploiement courant

```bash
sudo /opt/boussole/src/infra/deploy/deploy.sh <étiquette-ou-commit>
```

Sauvegarde, construit `boussole:<commit>`, démarre, attend la sonde de santé. En cas
d'échec, revient tout seul à la version précédente. Version en service :
`cat /srv/boussole/current_tag`.

## Retour arrière

```bash
docker images boussole
sudo /opt/boussole/src/infra/deploy/rollback.sh <commit>
```

Le retour arrière ne touche pas aux données. Restaurer une sauvegarde (base abîmée par une
version) est une **décision humaine** : arrêter l'application, copier
`/var/backups/boussole/<date>/boussole.db` vers `/srv/boussole/data/boussole.db`, relancer,
puis `audit.cli verify --expect` avec la dernière ancre conservée hors du serveur.

## Migration depuis le montage manuel (une seule fois)

Objectif : reprendre **les données et les clés actuelles**, sans perdre le journal signé.
L'ancien montage n'est jamais supprimé par cette procédure : il sert de retour arrière.

### État du serveur avant migration (vérifié le 2026-11-01)

| Élément | Ancien montage | Nouveau montage |
|---|---|---|
| Code | `/opt/boussole/src` (clone git) | idem, sur `phase-0/fondations` |
| Compose | `/opt/boussole/compose.yml`, projet `boussole`, conteneur `boussole` | `infra/deploy/compose.prod.yml`, projet `boussole-prod`, conteneur `boussole-prod-app-1` |
| Port | `127.0.0.1:8770` | `127.0.0.1:8000` |
| Base | volume `boussole_boussole-data` : `/data/boussole.db` | `/srv/boussole/data/boussole.db` |
| Coffre (clé OpenRouter, clé du journal) | volume : `/data/python_keyring/keyring_pass.cfg` | `/srv/boussole/secrets/python_keyring/keyring_pass.cfg` |
| Modèles d'embeddings | volume : `/data/fastembed/` | `/srv/boussole/data/models/` |
| Index RAG et PDF | `/opt/boussole/rag` (`rag_index.jsonl`, `pmbok8.pdf`) | `/srv/boussole/data/` |
| nginx | `/etc/nginx/sites-available/boussole.optigenius.pro`, proxy `127.0.0.1:8770` | même fichier, proxy `127.0.0.1:8000` |
| Comptes | `/etc/nginx/.htpasswd-boussole` : compte `zaki` | même fichier, conservé tel quel; `BOUSSOLE_ROLES=zaki=pmo` |
| Journal de référence | 62 entrées, embranchements documentés [32, 35] | 63 entrées après l'ancre de l'étape 1 |

Sauvegarde déjà faite : `/opt/boussole/backups/` (base et compose du 2026-11-01 20:04).

### Étapes (s'arrêter au premier écart)

1. Ancrer l'ancien journal et **conserver la ligne affichée hors du serveur** :
   ```bash
   docker exec boussole python -m boussole.platform.audit.cli anchor
   ```
2. Mettre le code à jour :
   ```bash
   cd /opt/boussole/src && git fetch && git checkout phase-0/fondations && git pull
   ```
3. Préparer l'hôte et la configuration :
   ```bash
   mkdir -p /srv/boussole/data/models /srv/boussole/secrets/python_keyring /var/log/boussole /var/backups/boussole
   cp /opt/boussole/src/infra/deploy/boussole.env.example /srv/boussole/boussole.env
   chmod 600 /srv/boussole/boussole.env
   ```
   Dans `boussole.env` : `BOUSSOLE_TRUST_PROXY_USER=1`, `BOUSSOLE_ROLES=zaki=pmo`,
   `BOUSSOLE_OPERATOR=zaki`, `BOUSSOLE_ALLOWED_ORIGINS=https://boussole.optigenius.pro`,
   `BOUSSOLE_ANCHOR_URL=<adresse HTTPS de réception des ancres, sans paramètre>` et
   `BOUSSOLE_ANCHOR_TOKEN=<jeton du script de réception>` (voir
   `docs/runbooks/journal-audit.md`). Ne **pas** définir
   `BOUSSOLE_DATABASE_URL` (la base est celle de `/srv/boussole/data`).
4. Arrêter l'ancien conteneur **sans le supprimer**, puis copier données et coffre :
   ```bash
   docker stop boussole
   docker run --rm -v boussole_boussole-data:/from:ro -v /srv/boussole:/to alpine sh -c '
     cp -p /from/boussole.db /to/data/ &&
     cp -p /from/python_keyring/keyring_pass.cfg /to/secrets/python_keyring/ &&
     cp -pR /from/fastembed/. /to/data/models/'
   cp -p /opt/boussole/rag/* /srv/boussole/data/
   chown -R 10001:10001 /srv/boussole/data /srv/boussole/secrets
   chmod 700 /srv/boussole/secrets /srv/boussole/secrets/python_keyring
   chmod 600 /srv/boussole/secrets/python_keyring/keyring_pass.cfg
   ```
5. Déployer (la table `llm_reservations` est créée au démarrage sous SQLite) :
   ```bash
   /opt/boussole/src/infra/deploy/deploy.sh <commit de phase-0/fondations>
   docker logs boussole-prod-app-1 2>&1 | tail -20
   ```
6. Vérifier le journal avec l'ancre de l'étape 1 : 63 entrées attendues, aucune erreur.
   ```bash
   docker exec boussole-prod-app-1 python -m boussole.platform.audit.cli verify --expect <ancre>
   ```
7. Basculer nginx sur le nouveau conteneur (un seul fichier pour ce `server_name`) :
   ```bash
   cp /etc/nginx/sites-available/boussole.optigenius.pro /etc/nginx/sites-available/boussole.optigenius.pro.bak
   cp /opt/boussole/src/infra/deploy/nginx/boussole.conf /etc/nginx/sites-available/boussole.optigenius.pro
   nginx -t && systemctl reload nginx
   ```
   Le `.bak` reste dans `sites-available`, jamais dans `sites-enabled`.
   Les comptes restent ceux de `/etc/nginx/.htpasswd-boussole` (fichier existant, ne pas le
   recréer). Ajouter un compte : `htpasswd -B /etc/nginx/.htpasswd-boussole <compte>` (sans
   `-c`, qui écraserait le fichier), puis l'ajouter à `BOUSSOLE_ROLES`.
8. Contrôles (doivent tous réussir) :
   ```bash
   curl -s -o /dev/null -w "%{http_code}
" https://boussole.optigenius.pro/settings                         # 401
   curl -s -o /dev/null -w "%{http_code}
" -H "X-Remote-User: zaki" https://boussole.optigenius.pro/settings # 401
   ss -tlnp | grep 8000                                                                                       # 127.0.0.1 seulement
   curl -s -o /dev/null -w "%{http_code}
" -X POST -H "Origin: https://evil.example" http://127.0.0.1:8000/settings/api-key/test            # 403
   curl -s -o /dev/null -w "%{http_code}
" -X POST -H "Origin: https://boussole.optigenius.pro" http://127.0.0.1:8000/settings/api-key/test # pas 403
   ```
   Puis, avec le compte `zaki` : la page `/projects` s'affiche, et la page Paramètres
   montre la clé OpenRouter comme enregistrée (le coffre a été repris).
9. Installer les tâches quotidiennes : `cp /opt/boussole/src/infra/deploy/boussole.cron /etc/cron.d/boussole`.

### Si une étape échoue après l'étape 4 : retour exact à l'état d'avant

```bash
cd /opt/boussole/src && docker compose -p boussole-prod -f infra/deploy/compose.prod.yml down
cp /etc/nginx/sites-available/boussole.optigenius.pro.bak /etc/nginx/sites-available/boussole.optigenius.pro
nginx -t && systemctl reload nginx
docker start boussole
```

Ne jamais supprimer l'ancien conteneur `boussole` ni le volume `boussole_boussole-data` :
ce sera fait à la main après une semaine sans incident.

## Sauvegardes

`infra/deploy/backup.sh` (avant chaque déploiement et chaque nuit) : base SQLite cohérente,
coffre, index RAG; 14 jours dans `/var/backups/boussole`. Le coffre y est en clair :
copier régulièrement ce dossier **hors du serveur, chiffré**.
