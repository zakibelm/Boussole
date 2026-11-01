# Résultats du benchmark

Un fichier par exécution : `<date UTC>-<identifiant>.json` (résumé, recommandation,
réponse brute et note de chaque cas). Les exécutions à blanc ne sont pas versionnées.

| Exécution | Statut | Remarque |
|---|---|---|
| `20261031T210428Z-73e35b` | **Invalide** | Limite de 400 à 900 jetons trop basse : les modèles à raisonnement ont rendu des réponses vides ou tronquées, notées 0 au lieu d'être signalées. Corrigé : limite de 4 000 jetons et réponses tronquées comptées comme erreurs. Coût : 0,28 $ CA. |
| `20261031T213807Z-d19834` | **Invalide** | Coupure réseau vers OpenRouter pendant l'exécution (ConnectError) : 86 appels en échec, 14 réponses de Sonnet seulement. Corrigé : 3 tentatives par cas, arrêt après 5 échecs réseau d'affilée. |
| `20261031T231024Z-ef0240` | **Valide, mais saturé** | Aucune erreur. Gemini 3.8 Flash, Mistral Large 4 et GPT-5.6 Luna obtiennent 1,00; Haiku 0,95; Sonnet 0,88. Sonnet et Haiku ne perdent des points que sur la longueur des statuts (plus de 150 mots), alors que la consigne n'annonçait pas cette limite. Le jeu est trop facile pour départager la justesse : la recommandation se fait sur le coût. |
| `20261101T004257Z-hard-3545e1` | **Valide (jeu difficile)** | Jeu `hard` (16 cas). GPT-5.6 Luna 0,88; Haiku 0,83; Gemini 3.8 Flash 0,78; Sonnet 0,75; Mistral Large 4 0,72 (1 réponse tronquée). Coût : 0,48 $ CA. Fichier conservé sur le VPS (`/opt/boussole/src/bench/results/`). |

## Lecture de l'exécution valide (31 octobre 2026)

- Recommandation de l'outil : `openai/gpt-5.6-luna`, ex æquo en justesse, le moins cher
  (0,011 $ CA pour 20 cas) et le plus rapide (3,7 s en moyenne).
- Coût total des trois exécutions : 0,92 $ CA sur le budget d'essai de 20 $ CA.
- Avant de changer les modèles par défaut, il faut un jeu plus difficile : cas
  ambigus pour le sélecteur, risques implicites, statuts contradictoires, et une
  consigne qui annonce la limite de mots.

## Lecture du jeu difficile (1er novembre 2026)

- Recommandation de l'outil : `openai/gpt-5.6-luna`, meilleur en justesse (0,88), le moins
  cher (0,0095 $ CA pour 16 cas) et le plus rapide (3,7 s en moyenne). Haiku suit (0,83).
- Statuts : la limite de 150 mots est maintenant annoncée. Sonnet la dépasse 4 fois sur 5
  (158 à 176 mots); Luna la respecte toujours et signale chaque incohérence.
- Approche : le piège « sprints » sur un projet figé (ha05) départage Haiku, Sonnet et Luna
  (prédictif, juste) de Gemini et Mistral (hybride).
- **Écart à arbitrer** : ha01 et ha02 sont ratés par les 5 modèles, qui répondent « hybride ».
  Le skill du sélecteur impose « si les signaux divergent, recommande l'hybride » et ces deux
  cas présentent des signaux divergents (équipe agile contre livrable certifié; banque
  hiérarchique contre produit incertain). Il faut soit préciser le skill (le livrable prime
  sur la préférence de l'équipe), soit étiqueter ces cas « hybrid ». Sans ces deux cas, Luna,
  Haiku et Sonnet obtiennent 4 sur 4 en approche.
- Coût cumulé du benchmark : 1,40 $ CA sur le budget d'essai de 20 $ CA.
