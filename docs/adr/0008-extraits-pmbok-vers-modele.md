# ADR 0008 : extraits du PMBOK envoyés au modèle, sans rétention

- **Statut :** accepté le 2026-11-01 par Zakaria Belmeddah (amende l'ADR 0004, point 1)
- **Date :** 2026-11-01

## Contexte

Le critère de sortie de la phase 0 est une réponse sourcée de bout en bout : un
agent répond en citant le PMBOK. Pour répondre juste, le modèle doit lire les
extraits trouvés, pas seulement leurs numéros de page. L'ADR 0004 interdisait
que le texte du PMBOK quitte le serveur. Trois options ont été pesées : un
modèle local sur le VPS (aucun texte ne sort, mais qualité non mesurée et
lenteur sans GPU), des citations seules (réponses peu fiables) et OpenRouter
avec des fournisseurs sans rétention.

## Décision

1. **Seuls les extraits trouvés partent**, au plus `k` (5 par défaut, environ
   1 500 caractères chacun), pour la question posée. Le livre entier, l'index
   et les embeddings restent sur le serveur (ADR 0004, inchangé sur ces points).
2. **Fournisseurs sans rétention ni entraînement** : toute requête marquée
   `private` envoie `provider: {data_collection: "deny", zdr: true}` à
   OpenRouter. Si aucun fournisseur du modèle choisi ne respecte cette
   politique, l'appel échoue (échec fermé) au lieu de partir ailleurs.
3. **Journal sans texte protégé** : l'entrée de résultat garde les citations,
   les numéros cités, le modèle, les jetons, le coût en $ CA et une empreinte
   SHA-256 de la réponse, jamais l'extrait ni la réponse (ADR 0004, point 6).
4. **Tout passe par le portail d'action** : `search_memory` puis
   `answer_question` (lecture, automatisation, sans effet), avec un même
   identifiant de corrélation, puis l'entrée de résultat.

## Conséquences

- Le modèle par agent doit avoir au moins un fournisseur sans rétention sur
  OpenRouter; sinon la réponse est refusée avec le message du fournisseur.
- Coût mesuré : quelques millièmes de $ CA par réponse avec GPT-5.6 Luna.
- Un modèle local reste possible plus tard, derrière le même port
  `LLMGateway`, si un benchmark montre une qualité suffisante.
