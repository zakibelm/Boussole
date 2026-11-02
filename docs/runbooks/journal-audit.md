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

`infra/anchor-cron.sh` crée l'ancre et l'envoie en HTTPS (POST, JSON) vers
`BOUSSOLE_ANCHOR_URL`, avec le jeton `BOUSSOLE_ANCHOR_TOKEN` **dans le corps** (les deux
dans `/srv/boussole/boussole.env`, `chmod 600`). Il est lancé chaque jour par
`/etc/cron.d/boussole` (fichier `infra/deploy/boussole.cron`), avec une copie locale dans
`/var/log/boussole/anchors.log`. L'adresse et le jeton n'apparaissent jamais dans la
sortie, les erreurs ni les arguments de `curl`.

Le point de réception est un Apps Script (`infra/anchor-receiver/Code.gs`) lié à une
feuille Google privée, que le VPS ne contrôle pas : chaque ancre acceptée devient une
ligne de l'onglet « Ancres » (reçue le, serveur, envoyée le, ancre).

Le script sort en erreur si l'adresse ou le jeton manque, si l'adresse n'est pas en HTTPS
ou contient un paramètre, si l'envoi échoue (code 4) ou si le point de réception refuse
l'ancre (code 5, jeton ou format) : cron le signale (MAILTO). L'ancre est créée malgré
tout et sa ligne figure dans la copie locale; l'envoyer à la main dès que possible.

#### Publier le point de réception

1. Ouvrir la feuille Google privée qui reçoit les ancres (partagée avec personne),
   puis **Extensions > Apps Script**.
2. Remplacer le contenu de `Code.gs` par `infra/anchor-receiver/Code.gs`, puis, dans
   l'éditeur seulement, remplacer `'<à définir>'` par le jeton. Générer le jeton sur un
   poste de confiance, par exemple `openssl rand -base64 32 | tr '+/' '-_' | tr -d '='`
   (lettres, chiffres, `-` et `_`, 16 caractères au moins). **Ne jamais commiter le vrai
   jeton.**
3. **Déployer > Nouveau déploiement**, type **Application Web** :
   - Exécuter en tant que : **moi**;
   - Qui a accès : **tout le monde** (le jeton, dans le corps du POST, fait la sécurité;
     sans lui, le script répond `refusé` et n'écrit rien).
   Autoriser l'accès à la feuille quand Google le demande.
4. Copier l'adresse de l'Application Web (`https://script.google.com/macros/s/…/exec`),
   **sans paramètre**, dans `BOUSSOLE_ANCHOR_URL`, et le même jeton dans
   `BOUSSOLE_ANCHOR_TOKEN` (`/srv/boussole/boussole.env`).

Le script publié et la variable du VPS se mettent à jour **ensemble** : un nouveau jeton
dans l'un sans l'autre fait refuser l'ancre suivante (code 5). Pour changer le jeton ou le
code : modifier le script, **Déployer > Gérer les déploiements > Modifier > Nouvelle
version** (l'adresse reste la même), puis mettre à jour `boussole.env` dans la foulée.

#### Vérifier le point de réception

1. Lancer l'envoi à la main sur le VPS :
   ```bash
   sudo /opt/boussole/src/infra/anchor-cron.sh
   ```
   La dernière ligne doit être `Ancre NUMÉRO:EMPREINTE envoyée hors du serveur.`, et une
   nouvelle ligne avec la même ancre doit apparaître dans l'onglet « Ancres ».
2. Vérifier qu'un appel sans jeton est refusé et n'écrit rien :
   ```bash
   curl -sL -d '{}' "$(sudo sed -n 's/^BOUSSOLE_ANCHOR_URL=//p' /srv/boussole/boussole.env)"; echo
   ```
   Réponse attendue : `refusé`, aucune ligne ajoutée.
3. Le lendemain, vérifier que l'ancre de 2 h 15 UTC est arrivée et que
   `/var/log/boussole/anchors.log` ne contient pas d'`ERREUR`.

Pour vérifier le journal avec la dernière ancre de la feuille :

```bash
docker exec boussole-prod-app-1 python -m boussole.platform.audit.cli verify --expect NUMÉRO:EMPREINTE
```

## Documenter des embranchements

Si `verify` signale « chaînage rompu » sans suppression (écritures simultanées) :

```bash
python -m boussole.platform.audit.cli resume --reason "cause de l'incident"
```

Voir `docs/rapports/incident-2026-11-01-journal.md`.
