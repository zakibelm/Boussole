# ADR 0003 : exigences produit tirées du marché (monday.com)

- **Statut :** accepté le 2026-10-31 par Zakaria Belmeddah
- **Date :** 2026-10-31

## Contexte

La section « Marché » du document d'architecture retient monday.com comme
modèle d'adoption : prise en main rapide, tableaux de bord visuels,
personnalisation sans code, agents créés par l'utilisateur, ouverture par API
et MCP. Elle relève aussi deux faiblesses à éviter : une tarification confuse,
avec l'IA facturée en crédits, et un reporting peu profond.

## Décision

Chaque force devient une exigence de Boussole, placée dans une phase et
soumise aux principes de CLAUDE.md :

| Exigence | Phase | Garde-fou qui s'applique |
|---|---|---|
| Création d'un projet en une conversation : description en une phrase, approche proposée par le sélecteur, modèle de projet prérempli | 1 (pilote) | Le choix d'approche reste en augmentation : le CEO ou le PMO valide |
| Tableau de bord par projet (avancement, budget, risques, validations en attente, coût IA) | 1, avancé depuis la phase 3 | Chiffres calculés depuis les données du projet, jamais générés par un modèle |
| Configuration sans code par le PMO : critères et pondérations du sélecteur, niveaux d'autonomie par type d'action, modèles par type de projet | Amorcée en phase 0 (modèle et skill par agent); critères et autonomie en phase 1; modèles de projet en phase 1 | Chaque changement est versionné, signé par un humain et réversible; un niveau d'autonomie ne s'abaisse pas sans validation du PMO |
| Agents créés par le PMO | 2 | Un agent créé hérite des règles communes, ne peut pas dépasser le niveau de l'action demandée, passe par la politique d'autonomie et le journal d'audit, et n'est actif qu'après validation du PMO |
| Chat limité au projet courant, avec sources | 1 | Droits par projet; sources de la mémoire RAG obligatoires |
| API publique et serveur MCP; connecteurs tiers sous le même contrat | API en phase 1; MCP en phase 2; connecteurs tiers en phase 3 | Le MCP expose les mêmes actions que l'API, avec les mêmes niveaux d'autonomie : rien d'irréversible sans humain nommé |
| Tarification simple en dollars canadiens, plafond de coût IA visible | Plafond visible dès la phase 0 (page Paramètres); grille tarifaire avant la mise en marché | Le plafond coupe les appels payants, il ne les facture pas en crédits |
| Rapports alignés sur les six domaines PMBOK 8, avec valeur et bénéfices | 2 | Sources citées pour tout chiffre |

## Conséquences

- La phase 1 grossit (création en une conversation, tableau de bord, chat,
  configuration du sélecteur et de l'autonomie, API). Son critère de sortie ne
  change pas : validations humaines mesurées et valeur perçue positive.
- La phase 0 reste centrée sur le socle (mémoire RAG, garde-fous, benchmark,
  CI). Aucune de ces exigences n'est commencée avant son critère de sortie.
- La création d'agents par le PMO oblige à passer le catalogue d'agents du
  fichier YAML à la base de données (phase 2), le fichier restant la source
  des agents fournis par défaut.
