/**
 * Zentrale Fehler-Übersetzung für deutsche Benutzeroberfläche.
 * Mappt technische Fehlerarten auf verständliche deutsche Meldungen.
 * Jede Meldung beantwortet drei Fragen:
 *   1. Was ist passiert?
 *   2. Warum (falls bekannt)?
 *   3. Was kann der Nutzer jetzt tun?
 */

/** Netzwerk-/Timeout-Fehler */
export const NETWORK_ERROR = 'Verbindung zum Server getrennt. Bitte prüfen Sie Ihre Internetverbindung und versuchen Sie es erneut.'

/** Server-Fehler (5xx) */
export const SERVER_ERROR = 'Interner Serverfehler. Das Team wurde benachrichtigt. Bitte versuchen Sie es in einigen Minuten erneut.'

/** Authentifizierungs-Fehler */
export const AUTH_ERROR = 'Sie sind nicht angemeldet. Bitte loggen Sie sich erneut ein.'

/** Berechtigungs-Fehler */
export const PERMISSION_ERROR = 'Sie haben für diese Aktion keine Berechtigung.'

/** Validierungs-Fehler */
export const VALIDATION_ERROR = 'Ihre Eingabe ist nicht gültig. Bitte die markierten Felder prüfen.'

/** Leere/Datenbank-Fehler */
export const EMPTY_DATA_ERROR = 'Keine Daten gefunden. Die Seite wurde neu geladen.'

/** Bring-spezifische Fehler */
export const BRING_NETWORK_ERROR = 'Bring-Dienst nicht erreichbar. Funktioniert die App offline oder ist der Dienst vorübergehend unavailable?'
export const BRING_AUTH_ERROR = 'Bring-Zugangsdaten nicht konfiguriert. Bitte Einstellungen prüfen.'
export const BRING_ITEM_ERROR = 'Artikel konnte nicht zur Einkaufsliste hinzugefügt werden. Bitte Feldinhalte prüfen.'

/** Einkaufsliste-Fehler (zentral) */
export const SHOPPING_UNREACHABLE = 'Die Einkaufsliste ist gerade nicht erreichbar. Erneut versuchen?'
export const SHOPPING_EMPTY = 'Keine Zutaten ausgewählt. Bitte mindestens eine Zutat anhaken.'
export const SHOPPING_BAD_DATA = 'Rezept hat keine gültigen Zutaten. Bitte überprüfen Sie das Rezept.'
export const SHOPPING_PARTIAL = 'Einige Zutaten konnten nicht hinzugefügt werden. Nur diese erneut versuchen?'
export const SHOPPING_DUPLICATE = 'Einige Zutaten waren bereits auf der Liste und wurden zusammengeführt.'

/** Globale Fallback-Funktion für unbekannte Fehler */
export function mapError(error: unknown): string {
  if (error instanceof Error) {
    const lower = error.message.toLowerCase()
    if (lower.includes('connection') || lower.includes('network') || lower.includes('timeout'))
      return NETWORK_ERROR
    if (lower.includes('bring'))
      return BRING_NETWORK_ERROR
    if (lower.includes('auth') || lower.includes('anmeldung'))
      return AUTH_ERROR
    if (lower.includes('validation') || lower.includes('falsche eingabe'))
      return VALIDATION_ERROR
    return error.message
  }
  if (typeof error === 'string') {
    const lower = error.toLowerCase()
    if (lower.includes('connection') || lower.includes('network') || lower.includes('timeout'))
      return NETWORK_ERROR
    if (lower.includes('bring'))
      return BRING_NETWORK_ERROR
    if (lower.includes('auth') || lower.includes('anmeldung'))
      return AUTH_ERROR
    if (lower.includes('validation') || lower.includes('falsche eingabe'))
      return VALIDATION_ERROR
    return error.length > 50 ? SERVER_ERROR : error
  }
  return SERVER_ERROR
}

/** Zentrale Fehler-Übersetzung für Einkaufsliste-Aktionen */
export function translateShoppingError(err: unknown): { message: string; retryable: boolean; partial?: string[] } {
  if (err instanceof Error) {
    const m = err.message.toLowerCase();
    if (m.includes('timeout') || m.includes('network') || m.includes('connection') || m.includes('unreachable') || m.includes('offline')) {
      return { message: SHOPPING_UNREACHABLE, retryable: true };
    }
    if (m.includes('empty') || m.includes('none selected')) {
      return { message: SHOPPING_EMPTY, retryable: false };
    }
    if (m.includes('bad data') || m.includes('no ingredients')) {
      return { message: SHOPPING_BAD_DATA, retryable: false };
    }
    if (m.includes('partial') || m.includes('some')) {
      return { message: SHOPPING_PARTIAL, retryable: true, partial: [] };
    }
    if (m.includes('duplicate') || m.includes('already')) {
      return { message: SHOPPING_DUPLICATE, retryable: false };
    }
    // Nur Log, nie ins UI: technische Details für Entwickler.
    console.error('[ShoppingError] Uncaught:', err);
    return { message: SERVER_ERROR, retryable: true };
  }
  if (typeof err === 'string') {
    return translateShoppingError(new Error(err));
  }
  console.error('[ShoppingError] Unknown:', err);
  return { message: SERVER_ERROR, retryable: true };
}
