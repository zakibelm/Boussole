# ADR 0007 : le PMBOK 8 en skills, par parties du livre

- **Statut :** accepté le 2026-10-31 par Zakaria Belmeddah
- **Date :** 2026-10-31

## Contexte

Chaque agent doit maîtriser la partie du PMBOK 8 qui le concerne, et les
orchestrateurs tout le livre. Des outils comme book-to-skill
(virgiliojr94/book-to-skill) distillent un livre en skills, mais en faisant lire
le texte entier par un modèle externe, ce que l'ADR 0004 interdit.

## Décision

1. **Le skill reste écrit par l'humain; le livre reste dans l'index local.**
   `config/pmbok_skills.yaml` associe chaque agent à des parties du livre
   (bornes de pages du PDF indexé, sans aucun texte). Orchestrateurs (sélecteur
   et trois chefs de projet) : `all`.
2. **Recherche limitée aux parties de l'agent** : `RagMemory.search(pages=...)`
   ne renvoie que les extraits qui chevauchent ses pages; les extraits de projet
   ne sont pas filtrés (leurs droits sont gérés par projet, ADR 0004).
3. **Note PMBOK ajoutée au prompt système** après le skill : parties consultées
   et obligation de citer section et page. Elle vient de la configuration; un
   skill édité ou raffiné ne peut pas l'effacer. Elle est visible dans la page
   Paramètres.
4. Au démarrage, toute affectation vers un agent ou une partie inconnue fait
   échouer le chargement.

## Conséquences

- Aucun coût, aucun texte du PMBOK hors du serveur, citations vérifiables.
- Les bornes de pages dépendent du PDF indexé : à revalider si le PDF change.
- Un domaine ne voit pas les domaines voisins; la vue transversale passe par
  les orchestrateurs.
