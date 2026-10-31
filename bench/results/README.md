# Résultats du benchmark

Un fichier par exécution : `<date UTC>-<identifiant>.json` (résumé, recommandation,
réponse brute et note de chaque cas). Les exécutions à blanc ne sont pas versionnées.

| Exécution | Statut | Remarque |
|---|---|---|
| `20261031T210428Z-73e35b` | **Invalide** | Limite de 400 à 900 jetons trop basse : les modèles à raisonnement ont rendu des réponses vides ou tronquées, notées 0 au lieu d'être signalées. Corrigé : limite de 4 000 jetons et réponses tronquées comptées comme erreurs. Coût : 0,28 $ CA. |
