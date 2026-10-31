import { redirect } from '@sveltejs/kit';

// Der Wochenplan ist durch die Wunschliste ersetzt – alte Links
// und Lesezeichen weiterleiten.
export function load() {
  redirect(307, '/wishes');
}
