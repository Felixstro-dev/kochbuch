import { api } from '#lib/api';
import type { Wish } from '#lib/types';

export async function load() {
  try {
    const wishes = await api.get<Wish[]>('/wishes');
    return { wishes, error: null as string | null };
  } catch {
    return { wishes: [] as Wish[], error: 'Die Wünsche konnten nicht geladen werden.' };
  }
}
