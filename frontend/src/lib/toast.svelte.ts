import { writable } from 'svelte/store';

export type ToastKind = 'success' | 'error' | 'info';

export interface Toast {
  id: number;
  message: string;
  kind: ToastKind;
}

let counter = 0;
export const toasts = writable<Toast[]>([]);

export function showToast(message: string, kind: ToastKind = 'info', duration = 3500) {
  const id = ++counter;
  toasts.update((list) => [...list, { id, message, kind }]);
  if (duration > 0) {
    setTimeout(() => {
      toasts.update((list) => list.filter((t) => t.id !== id));
    }, duration);
  }
  // Persistent: duration <= 0 -> bleibt bis Klick auf X (ToastContainer hat schon Button)
  return id;
}

export function dismissToast(id: number) {
  toasts.update((list) => list.filter((t) => t.id !== id));
}