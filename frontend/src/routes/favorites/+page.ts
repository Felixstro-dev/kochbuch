import { api } from '#lib/api';
import type { RecipeListResponse } from '#lib/types';

export async function load() {
  try {
    const response = await api.get<RecipeListResponse>('/favorites');
    return { items: response.items, total: response.total };
  } catch {
    return { items: [], total: 0 };
  }
}
