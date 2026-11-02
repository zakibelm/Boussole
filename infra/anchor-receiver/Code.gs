/**
 * Réception des ancres quotidiennes du journal d'audit de Boussole (infra/anchor-cron.sh).
 *
 * Script lié à une feuille Google privée (Extensions > Apps Script), publié en
 * Application Web : exécuter en tant que moi, accès à tout le monde
 * (docs/runbooks/journal-audit.md). Chaque ancre acceptée devient une ligne de la feuille
 * « Ancres » : reçue le, serveur, envoyée le, ancre (NUMÉRO:EMPREINTE).
 *
 * Le jeton est lu dans le CORPS du POST (JSON), jamais dans l'adresse : une adresse se
 * retrouve dans les journaux et l'historique, pas le corps. Aucune fonction GET : une requête GET
 * ne fait rien.
 *
 * JETON : remplacer la valeur ci-dessous dans l'éditeur Apps Script SEULEMENT, par la
 * même valeur que BOUSSOLE_ANCHOR_TOKEN dans /srv/boussole/boussole.env. Ne jamais
 * commiter le vrai jeton. Tant que la valeur vaut '<à définir>', tout est refusé.
 */
const JETON = '<à définir>';
const NON_DEFINI = '<à définir>';
const FEUILLE = 'Ancres';
const ANCRE = /^[0-9]+:[0-9a-f]{64}$/;
const SERVEUR = /^[A-Za-z0-9.-]{1,253}$/;
const DATE_UTC = /^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$/;

function doPost(e) {
  const ancre = lireAncre(e);
  if (!ancre) {
    return texte('refusé');
  }
  const verrou = LockService.getScriptLock();
  verrou.waitLock(10000);
  try {
    feuille().appendRow([new Date(), ancre.host, ancre.at, ancre.anchor]);
  } finally {
    verrou.releaseLock();
  }
  return texte('ok');
}

/** Renvoie l'ancre si le corps est valide et le jeton juste, sinon null. */
function lireAncre(e) {
  if (JETON === NON_DEFINI || !e || !e.postData || !e.postData.contents) {
    return null;
  }
  let corps;
  try {
    corps = JSON.parse(e.postData.contents);
  } catch (erreur) {
    return null;
  }
  if (!corps || !egal(String(corps.token || ''), JETON)) {
    return null;
  }
  // Formats stricts : aucune valeur ne peut être lue comme une formule par la feuille.
  if (!ANCRE.test(corps.anchor) || !SERVEUR.test(corps.host) || !DATE_UTC.test(corps.at)) {
    return null;
  }
  return { anchor: corps.anchor, host: corps.host, at: corps.at };
}

/** Comparaison en temps constant (longueur comprise dans la différence). */
function egal(a, b) {
  let difference = a.length ^ b.length;
  for (let i = 0; i < Math.max(a.length, b.length); i++) {
    difference |= (a.charCodeAt(i) || 0) ^ (b.charCodeAt(i) || 0);
  }
  return difference === 0;
}

function feuille() {
  const classeur = SpreadsheetApp.getActiveSpreadsheet();
  let onglet = classeur.getSheetByName(FEUILLE);
  if (!onglet) {
    onglet = classeur.insertSheet(FEUILLE);
    onglet.appendRow(['Reçue le', 'Serveur', 'Envoyée le (UTC)', 'Ancre']);
    onglet.setFrozenRows(1);
  }
  return onglet;
}

function texte(message) {
  return ContentService.createTextOutput(message).setMimeType(ContentService.MimeType.TEXT);
}
