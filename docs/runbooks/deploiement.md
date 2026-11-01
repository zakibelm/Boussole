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

1. Repérer les données et le coffre en service :
   ```bash
   docker ps --format "{{.Names}} {{.Image}} {{.Ports}}"
   docker inspect <conteneur-actuel> --format '{{range .Mounts}}{{.Source}} -> {{.Destination}}{{"\n"}}{{end}}'
   docker exec <conteneur-actuel> python -c "import keyring; k = keyring.get_keyring(); print(k, getattr(k, 'file_path', ''))"
   ```
2. Ancrer et vérifier le journal **avant** de toucher à quoi que ce soit, et garder la ligne :
   ```bash
   docker exec <conteneur-actuel> python -m boussole.platform.audit.cli anchor
   ```
   (si la version en service ne connaît pas `anchor`, lancer `verify` et noter le nombre d'entrées)
3. Préparer l'hôte :
   ```bash
   mkdir -p /srv/boussole/data /srv/boussole/secrets/python_keyring /var/log/boussole /var/backups/boussole
   cp /opt/boussole/src/infra/deploy/boussole.env.example /srv/boussole/boussole.env
   chmod 600 /srv/boussole/boussole.env      # puis l'éditer : rôles, opérateur, origine
   ```
4. Arrêter l'ancien conteneur (`docker stop <conteneur-actuel>`, **sans le supprimer**), puis
   copier les données (base, index, PDF) dans `/srv/boussole/data/` et le fichier du coffre
   (`keyring_pass.cfg`) dans `/srv/boussole/secrets/python_keyring/`.
5. Donner les fichiers au compte de l'application et fermer les droits :
   ```bash
   chown -R 10001:10001 /srv/boussole/data /srv/boussole/secrets
   chmod 700 /srv/boussole/secrets /srv/boussole/secrets/python_keyring
   chmod 600 /srv/boussole/secrets/python_keyring/keyring_pass.cfg
   ```
6. Installer nginx et les comptes (un par personne) :
   ```bash
   htpasswd -B -c /etc/nginx/boussole.htpasswd zaki      # sans -c pour les comptes suivants
   cp /opt/boussole/src/infra/deploy/nginx/boussole.conf /etc/nginx/sites-available/boussole.conf
   ln -sf /etc/nginx/sites-available/boussole.conf /etc/nginx/sites-enabled/boussole.conf
   nginx -t && systemctl reload nginx
   ```
   Chaque compte doit figurer dans `BOUSSOLE_ROLES` pour valider ou modifier les paramètres.
7. Déployer : `sudo /opt/boussole/src/infra/deploy/deploy.sh <commit>`. Le script vérifie le
   journal; comparer avec l'ancre de l'étape 2 :
   ```bash
   docker exec boussole-app-1 python -m boussole.platform.audit.cli verify --expect <ancre>
   ```
8. Contrôles de l'audit du 1er novembre (doivent tous réussir) :
   ```bash
   curl -s -o /dev/null -w "%{http_code}\n" https://boussole.optigenius.pro/settings                         # 401
   curl -s -o /dev/null -w "%{http_code}\n" -H "X-Remote-User: zaki" https://boussole.optigenius.pro/settings # 401
   ss -tlnp | grep 8000                                                                                       # 127.0.0.1:8000 seulement
   ```
9. Installer les tâches quotidiennes : `cp /opt/boussole/src/infra/deploy/boussole.cron /etc/cron.d/boussole`.
10. Après une semaine sans incident seulement : supprimer l'ancien conteneur.

## Sauvegardes

`infra/deploy/backup.sh` (avant chaque déploiement et chaque nuit) : base SQLite cohérente,
coffre, index RAG; 14 jours dans `/var/backups/boussole`. Le coffre y est en clair :
copier régulièrement ce dossier **hors du serveur, chiffré**.
