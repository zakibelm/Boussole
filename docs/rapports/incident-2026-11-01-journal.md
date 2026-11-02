# Incident du 1er novembre 2026 : embranchements du journal d'audit

- **Détecté par :** les tests de bout en bout sur boussole.optigenius.pro
  (`audit.cli verify` : « Journal ALTÉRÉ à l'entrée 32 : chaînage rompu »).
- **Gravité :** critique (la preuve d'intégrité ne tenait plus), sans perte de données.

## Cause

Trois questions envoyées en même temps ont écrit dans le journal simultanément. En
mode SQLite, aucune écriture n'était sérialisée : deux transactions ont lu la même
entrée précédente. Les entrées 32 et 35 pointent donc vers une entrée qui existe,
mais qui n'est pas celle juste avant. Aucune entrée n'a été modifiée ni supprimée
(contenu et signatures valides).

## Correction

- Verrou d'écriture dans `AuditLog.append` et transactions SQLite `BEGIN IMMEDIATE`
  (`core/database.py`), qui sérialisent aussi les écritures entre processus.
- Test : 40 écritures simultanées sur 8 fils, chaîne unique.
- Reprise documentée : `audit.cli resume --reason …` ajoute une entrée signée qui
  liste les embranchements. `verify` les accepte seulement s'ils sont listés par une
  reprise signée avec la clé du journal et s'ils pointent vers une entrée existante;
  une suppression reste détectée (tests).

## Résultat

- Entrée de reprise n° 49 (embranchements 32 et 35), signée le 1er novembre 2026.
- `verify` : « Journal intègre : 57 entrées vérifiées (embranchements documentés :
  [32, 35]) », y compris après trois nouvelles questions simultanées.
