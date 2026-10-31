import { error } from '@sveltejs/kit';
import { api, ApiError } from '#lib/api';
import { peekRecipe, rememberRecipe } from '#lib/prefetch';
import type { RecipeDetail } from '#lib/types';

export async function load({ params }: { params: { key: string } }) {
  const cacheKey = decodeURIComponent(params.key);
  const cached = peekRecipe(cacheKey);
  if (cached) return { cacheKey, recipe: cached };

  try {
    const recipe = await api.get<RecipeDetail>(`/recipes/${encodeURIComponent(cacheKey)}`);
    rememberRecipe(recipe);
    return { cacheKey, recipe };
  } catch (cause) {
    if (cause instanceof ApiError) {
      throw error(cause.status === 404 ? 404 : 502, cause.message);
    }
    throw error(502, 'Das Rezept konnte nicht geladen werden.');
  }
}
