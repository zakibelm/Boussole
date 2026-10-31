# Résultats du benchmark

Un fichier par exécution : `<date UTC>-<identifiant>.json` (résumé, recommandation,
réponse brute et note de chaque cas). Les exécutions à blanc ne sont pas versionnées.

| Exécution | Statut | Remarque |
|---|---|---|
| `20261031T210428Z-73e35b` | **Invalide** | Limite de 400 à 900 jetons trop basse : les modèles à raisonnement ont rendu des réponses vides ou tronquées, notées 0 au lieu d'être signalées. Corrigé : limite de 4 000 jetons et réponses tronquées comptées comme erreurs. Coût : 0,28 $ CA. |
| `20261031T213807Z-d19834` | **Invalide** | Coupure réseau vers OpenRouter pendant l'exécution (ConnectError) : 86 appels en échec, 14 réponses de Sonnet seulement. Corrigé : 3 tentatives par cas, arrêt après 5 échecs réseau d'affilée. |
| `20261031T231024Z-ef0240` | **Valide, mais saturé** | Aucune erreur. Gemini 3.8 Flash, Mistral Large 4 et GPT-5.6 Luna obtiennent 1,00; Haiku 0,95; Sonnet 0,88. Sonnet et Haiku ne perdent des points que sur la longueur des statuts (plus de 150 mots), alors que la consigne n'annonçait pas cette limite. Le jeu est trop facile pour départager la justesse : la recommandation se fait sur le coût. |

## Lecture de l'exécution valide (31 octobre 2026)

- Recommandation de l'outil : `openai/gpt-5.6-luna`, ex æquo en justesse, le moins cher
  (0,011 $ CA pour 20 cas) et le plus rapide (3,7 s en moyenne).
- Coût total des trois exécutions : 0,92 $ CA sur le budget d'essai de 20 $ CA.
- Avant de changer les modèles par défaut, il faut un jeu plus difficile : cas
  ambigus pour le sélecteur, risques implicites, statuts contradictoires, et une
  consigne qui annonce la limite de mots.
