# ADR 0002 : OpenRouter comme passerelle, page Paramètres et skills par agent

- **Statut :** accepté le 2026-10-31 par Zakaria Belmeddah
- **Date :** 2026-10-31

## Contexte

Le décideur veut une passerelle unique vers les modèles, une page où saisir la
clé API, choisir un modèle pour chaque agent et sous-agent, et modifier ou
raffiner le skill (les instructions) de chacun.

## Décision

1. **OpenRouter est le seul fournisseur réel.** Il donne accès à de nombreux
   modèles (Anthropic, OpenAI, Google, Meta, Mistral…) avec une seule API.
   Le port `LLMGateway` est conservé : OpenRouter en est un adaptateur, à côté
   de l'adaptateur factice utilisé par les tests. Changer de fournisseur reste
   une affaire d'adaptateur et de configuration (principe 1).
2. **Choix du modèle par agent.** Les valeurs par défaut sont dans
   `config/agents.yaml`; un choix fait dans la page Paramètres est enregistré
   en base et prévaut sur la valeur par défaut. Aucun identifiant de modèle
   n'est codé en dur dans le code.
3. **Skills versionnés.** Chaque modification d'un skill crée une version
   (auteur, date, motif). Le retour à une version antérieure crée une nouvelle
   version : l'historique n'est jamais réécrit. Le bouton « Raffiner avec
   l'IA » produit une proposition que l'humain accepte ou refuse (niveau
   assistance).
4. **Clé API dans le coffre Windows** (Gestionnaire d'identifiants, via
   `keyring`). Elle n'est ni dans le dépôt, ni dans la base, ni dans les
   journaux, et elle n'est jamais réaffichée : la page montre seulement ses
   quatre derniers caractères.
5. **Interface FastAPI + Jinja + HTMX**, servie par le backend Python : une
   seule stack.
6. **Budget d'essai de la phase 0 : 20 $ CA.** Chaque appel payant est
   enregistré avec son coût; au-delà du plafond, la passerelle refuse l'appel.
   OpenRouter facture en dollars américains : la conversion utilise le taux
   fixé dans `BOUSSOLE_USD_CAD_RATE`.

## Écart assumé

La phase 0 demandait au moins deux adaptateurs réels. Avec un seul
fournisseur, une panne d'OpenRouter coupe tous les modèles. Le mode dégradé de
la phase 3 devra soit ajouter un second adaptateur direct, soit basculer vers
le travail humain. Le benchmark compare quand même au moins deux modèles, via
OpenRouter.

## Conséquences

- Positives : une seule clé, des centaines de modèles comparables par le
  benchmark, un coût suivi par appel.
- Négatives : dépendance à un intermédiaire (disponibilité, confidentialité
  des données envoyées) : à documenter dans le dossier de revue de la phase 3.
