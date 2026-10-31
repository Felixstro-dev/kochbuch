export function formatMinutes(value: number | null | undefined): string {
  if (!value || value <= 0) return '–';
  const hours = Math.floor(value / 60);
  const minutes = Math.round(value % 60);
  if (hours && minutes) return `${hours} Std. ${minutes} Min.`;
  if (hours) return `${hours} Std.`;
  return `${minutes} Min.`;
}

export function formatRating(value: number | null | undefined): string {
  if (value === null || value === undefined) return '–';
  return value.toFixed(1).replace('.', ',');
}

export function difficultyLabel(value: number | null | undefined): string {
  if (value === 1) return 'Einfach';
  if (value === 2) return 'Mittel';
  if (value === 3) return 'Anspruchsvoll';
  return '–';
}

const FRACTIONS: Array<[number, string]> = [
  [1 / 8, '⅛'],
  [1 / 4, '¼'],
  [1 / 3, '⅓'],
  [1 / 2, '½'],
  [2 / 3, '⅔'],
  [3 / 4, '¾']
];

export function formatAmount(amount: number | null, factor = 1): string {
  if (amount === null || amount === undefined) return '';
  const scaled = amount * factor;
  if (scaled <= 0) return '';
  const whole = Math.floor(scaled + 1e-9);
  const rest = scaled - whole;
  let fraction = '';
  if (rest > 0.03) {
    const match = FRACTIONS.find(([value]) => Math.abs(rest - value) < 0.04);
    if (match) {
      fraction = match[1];
    } else if (scaled < 10) {
      return scaled.toFixed(1).replace('.', ',');
    } else {
      return String(Math.round(scaled));
    }
  }
  if (whole && fraction) return `${whole} ${fraction}`;
  if (whole) return String(whole);
  return fraction || '0';
}

export function scaledServings(base: number | null, desired: number): number {
  if (!base || base <= 0) return desired;
  return Math.max(1, desired);
}

export function amountFactor(base: number | null, desired: number): number {
  if (!base || base <= 0) return 1;
  return Math.max(0.05, desired / base);
}

export function relativeTime(iso: string | null): string {
  if (!iso) return '';
  const date = new Date(iso.endsWith('Z') ? iso : `${iso}Z`);
  const seconds = Math.max(1, Math.floor((Date.now() - date.getTime()) / 1000));
  if (seconds < 60) return 'gerade eben';
  if (seconds < 3600) return `vor ${Math.floor(seconds / 60)} Min.`;
  if (seconds < 86400) return `vor ${Math.floor(seconds / 3600)} Std.`;
  const days = Math.floor(seconds / 86400);
  if (days < 30) return `vor ${days} ${days === 1 ? 'Tag' : 'Tagen'}`;
  return date.toLocaleDateString('de-DE', { day: '2-digit', month: 'short', year: 'numeric' });
}

export function initials(name: string): string {
  return name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase() ?? '')
    .join('');
}

export function viewTransitionKey(cacheKey: string): string {
  return `recipe-${cacheKey.replace(/[^a-z0-9]/gi, '-')}`;
}

export function timerLabel(seconds: number | null): string {
  if (!seconds) return '';
  if (seconds >= 3600) {
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.round((seconds % 3600) / 60);
    return minutes ? `${hours} Std. ${minutes} Min.` : `${hours} Std.`;
  }
  if (seconds >= 60) return `${Math.round(seconds / 60)} Min.`;
  return `${seconds} Sek.`;
}
