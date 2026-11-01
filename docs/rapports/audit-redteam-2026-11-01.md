# Audit et red team du 1er novembre 2026

- **Version auditée :** `phase-0/fondations` au commit `2f868e4` (PR #1 à #6 fusionnées).
- **Périmètre :** code et tests locaux seulement. Le serveur boussole.optigenius.pro
  n'a pas été sondé (vérifications serveur listées à la fin).
- **Méthode :** lecture du code exposé, puis une preuve exécutable par faille
  (7 tests, tous réussis : chaque faille est réelle). Les preuves ne sont pas
  versionnées : elles décrivent comment attaquer.
- **État de départ :** 307 tests verts, lint et types propres.
- **Corrections :** branche `fix/audit-redteam-2026-11-01`, 335 tests verts (28 tests
  red team ajoutés). Statut de chaque constat dans le tableau « Corrections » ci-dessous.

## Constats, du plus grave au moins grave

| # | Gravité | Constat | Preuve | Correction proposée |
|---|---|---|---|---|
| 1 | **Haute** | La page Paramètres ne contrôle aucun rôle. Avec les comptes nginx, un compte sans rôle (« observer ») peut remplacer la clé OpenRouter par la sienne (il reçoit alors tout ce qui part au modèle : extraits du PMBOK, données de projet), la supprimer, changer les modèles et réécrire les skills (injection durable dans les prompts des agents). | Clé remplacée et skill du sélecteur réécrit depuis un compte « stagiaire » | Réserver toute écriture de Paramètres au rôle `pmo` (refus 403 sinon) |
| 2 | **Haute** | Ces modifications de Paramètres n'entrent pas au journal d'audit (seul l'historique des skills garde une trace, modifiable via la base). | Aucune entrée `agent_log` après le remplacement de la clé | Journaliser chaque écriture de Paramètres (qui, quoi, empreinte de la clé, jamais la clé) |
| 3 | Moyenne | Le journal ne détecte pas la suppression de ses dernières entrées, ni celle d'une entrée laissée sur une branche morte par un embranchement documenté (incident du 1er novembre). Il faut un accès en écriture à la base, déclencheurs désactivés. | 2 entrées finales supprimées : « intègre »; entrée de branche morte supprimée : « intègre » | Numéro de séquence continu inclus dans l'empreinte; ancrage signé et périodique de la dernière empreinte hors du serveur |
| 4 | Moyenne | Le plafond de budget est vérifié avant l'appel et compté après : des appels simultanés le dépassent tous ensemble. Pas de plafond par tâche (exigé par CLAUDE.md). | Plafond 1 $ CA, 8 appels simultanés : 8 $ CA dépensés | Réserver le coût maximal de l'appel avant de l'envoyer (sous verrou), puis régulariser; plafond par tâche |
| 5 | Moyenne | HTMX est chargé depuis unpkg sans contrôle d'intégrité, y compris sur la page où l'on saisit la clé API. Un CDN compromis lirait la clé. | Balise `<script>` sans `integrity` | Servir HTMX depuis l'application (fichier versionné) ou ajouter `integrity` et `crossorigin` |
| 6 | Moyenne-faible | Une action sortante sans destination déclarée (`send_message`) échappe à la liste blanche. Atténué : elle exige toujours un humain nommé. | `send_message` sans destination, validé : autorisé | Exiger une destination pour toute action qui sort de Boussole |
| 7 | Faible | La provenance d'une version de skill vient du formulaire : on peut enregistrer une modification manuelle comme « default » ou « ai_refined ». | Skill réécrit, provenance « default » | Accepter seulement « manual » et « ai_refined » (après une proposition), fixer « revert » côté serveur |
| 8 | Faible | Le filtre CSRF fait confiance à l'en-tête `X-Forwarded-Host` reçu et laisse passer une requête sans `Origin` ni `Referer`. Non exploitable depuis un navigateur piégé (en-tête impossible à poser sans CORS), choix documenté. | — | Faire poser `X-Forwarded-Host` par nginx et ignorer celui du client |

## Corrections

| # | Statut | Correction | Tests |
|---|---|---|---|
| 1 | Corrigé | Toute écriture de Paramètres exige le rôle `pmo` (refus 403) | `tests/redteam/test_redteam_settings.py` |
| 2 | Corrigé | Chaque écriture de Paramètres est journalisée avant son effet (auteur, rôle, cible, empreinte de la clé); sans journal, aucun changement | idem |
| 3 | Corrigé, sous condition | Ancres signées (`audit.cli anchor`) et ancre externe (`verify --expect`). **La protection n'existe qu'à partir d'une ancre** : ancrer chaque jour et garder la ligne hors du serveur (`docs/runbooks/journal-audit.md`) | `tests/redteam/test_redteam_audit_anchor.py` |
| 4 | Corrigé | Réservation du plafond par tâche avant chaque appel (`BOUSSOLE_TASK_CAP_CAD`, 0,50 $ CA); plafond 1 $ CA et 8 appels simultanés : au plus 1 $ CA | `tests/redteam/test_redteam_budget.py` |
| 5 | Corrigé | HTMX 2.0.3 servi par Boussole (archive npm vérifiée), contrôle d'intégrité SHA-384 | `tests/redteam/test_redteam_scripts.py` |
| 6 | Corrigé | `outbound: true` : action sortante refusée sans destination déclarée | `tests/redteam/test_redteam_outbound_csrf.py` |
| 7 | Corrigé | Provenance limitée à « manuelle » ou « raffinée par l'IA » depuis le formulaire | `tests/redteam/test_redteam_settings.py` |
| 8 | Corrigé | `X-Forwarded-Host` du client ignoré; l'origine publique vient de `BOUSSOLE_ALLOWED_ORIGINS` | `tests/redteam/test_redteam_outbound_csrf.py` |

Contre-vérification : les 7 preuves de concept d'origine relancées après correction.
5 échouent (faille fermée); les 2 du journal réussissent encore, car elles visent un
journal jamais ancré, ce qui est la limite assumée du constat 3.

**À faire au déploiement :** `BOUSSOLE_ALLOWED_ORIGINS` doit contenir l'origine publique
(`https://boussole.optigenius.pro`), sinon les formulaires seront refusés derrière nginx;
lancer une première ancre et la conserver hors du serveur.

## Ce qui tient

- Liste blanche réseau : le contournement « pirate.com#.openrouter.ai » est fermé (PR #1).
- Red team 1 à 3 : injection sans effet, aucune sortie de projet, irréversible refusé sans humain nommé.
- Journal : modification de contenu, signature invalide et suppression au milieu détectées; écritures sérialisées depuis l'incident.
- Protection CSRF présente sur toutes les requêtes qui modifient quelque chose.

## Vérifications serveur à faire (non couvertes)

Le risque principal côté serveur : avec `BOUSSOLE_TRUST_PROXY_USER=1`, l'identité vient
de l'en-tête `X-Remote-User`. Si nginx ne le réécrit pas, ou si le port de l'application
est joignable sans nginx, n'importe qui choisit son identité et son rôle.

1. nginx réécrit l'en-tête : `proxy_set_header X-Remote-User $remote_user;`
2. Le conteneur de l'application n'écoute que sur `127.0.0.1` (`docker ps`).
3. Sans mot de passe, `curl -H "X-Remote-User: zaki" https://boussole.optigenius.pro/settings` répond 401.
