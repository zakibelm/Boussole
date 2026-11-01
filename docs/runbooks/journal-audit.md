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

Planification suggérée sur le VPS (cron, chaque jour à 2 h), avec envoi de la ligne
vers un endroit extérieur :

```bash
0 2 * * * docker exec boussole python -m boussole.platform.audit.cli anchor
```

## Documenter des embranchements

Si `verify` signale « chaînage rompu » sans suppression (écritures simultanées) :

```bash
python -m boussole.platform.audit.cli resume --reason "cause de l'incident"
```

Voir `docs/rapports/incident-2026-11-01-journal.md`.
