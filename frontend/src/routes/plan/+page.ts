import { api } from '#lib/api';
import type { RecipeListResponse, RecipeSummary } from '#lib/types';

export async function load() {
  try {
    const [saved, favorites] = await Promise.all([
      api.get<RecipeListResponse>('/saved'),
      api.get<RecipeListResponse>('/favorites')
    ]);
    const map = new Map<string, RecipeSummary>();
    for (const item of [...saved.items, ...favorites.items]) map.set(item.cache_key, item);
    return { recipes: [...map.values()] };
  } catch {
    return { recipes: [] as RecipeSummary[] };
  }
}
