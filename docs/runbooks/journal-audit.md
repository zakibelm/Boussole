# Journal d'audit : vérifier, ancrer, documenter un incident

Toutes les commandes se lancent dans le conteneur ou le dossier de Boussole.

## Vérifier

```bash
python -m boussole.platform.audit.cli verify --expect NUMÉRO:EMPREINTE
```

Contrôle le chaînage, le contenu, les signatures et chaque ancre. `--expect` compare
avec la dernière ancre conservée hors du serveur (voir ci-dessous) : sans elle, la
suppression de la fin du journal, ancre comprise, ne peut pas être détectée.

## Ancrer (au moins une fois par jour)

```bash
python -m boussole.platform.audit.cli anchor
```

Écrit une entrée signée qui couvre toutes les entrées présentes, puis affiche une ligne
`NUMÉRO:EMPREINTE`. **Conserver cette ligne hors du serveur** (gestionnaire de mots de
passe, courriel à soi-même, dépôt privé) : c'est elle qui rend la suppression de la fin
du journal détectable. Après une ancre, toute suppression antérieure est détectée par
`verify`, même sans `--expect`.

### Ancre quotidienne envoyée hors du serveur

`infra/anchor-cron.sh` crée l'ancre et l'envoie en HTTPS (POST, texte brut) vers
`BOUSSOLE_ANCHOR_URL` (variable de `/srv/boussole/boussole.env`) : un service que le VPS
ne contrôle pas (point de réception d'un outil d'automatisation, webhook vers une boîte
courriel, stockage d'un autre fournisseur). Il est lancé chaque jour par
`/etc/cron.d/boussole` (fichier `infra/deploy/boussole.cron`), avec une copie locale dans
`/var/log/boussole/anchors.log`.

Le script sort en erreur si l'adresse est vide, n'est pas en HTTPS ou si l'envoi
échoue : cron le signale (MAILTO). L'ancre est créée malgré tout et sa ligne figure dans
la copie locale; l'envoyer à la main dès que possible.

Pour vérifier avec l'ancre reçue à l'extérieur :

```bash
docker exec boussole-prod-app-1 python -m boussole.platform.audit.cli verify --expect NUMÉRO:EMPREINTE
```

## Documenter des embranchements

Si `verify` signale « chaînage rompu » sans suppression (écritures simultanées) :

```bash
python -m boussole.platform.audit.cli resume --reason "cause de l'incident"
```

Voir `docs/rapports/incident-2026-11-01-journal.md`.
