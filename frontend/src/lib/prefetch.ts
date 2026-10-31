import { api } from './api';
import type { RecipeDetail } from './types';

interface CacheEntry {
  data: RecipeDetail;
  at: number;
}

const cache = new Map<string, CacheEntry>();
const inFlight = new Map<string, Promise<RecipeDetail | null>>();

export function peekRecipe(cacheKey: string): RecipeDetail | null {
  const entry = cache.get(cacheKey);
  if (!entry) return null;
  if (Date.now() - entry.at > 30_000) {
    cache.delete(cacheKey);
    return null;
  }
  return entry.data;
}

export async function prefetchRecipe(cacheKey: string): Promise<RecipeDetail | null> {
  const cached = peekRecipe(cacheKey);
  if (cached) return cached;
  if (inFlight.has(cacheKey)) return inFlight.get(cacheKey) ?? null;
  const promise = api
    .get<RecipeDetail>(`/recipes/${encodeURIComponent(cacheKey)}`)
    .then((data) => {
      cache.set(cacheKey, { data, at: Date.now() });
      return data;
    })
    .catch(() => null)
    .finally(() => inFlight.delete(cacheKey));
  inFlight.set(cacheKey, promise);
  return promise;
}

export function rememberRecipe(data: RecipeDetail): void {
  cache.set(data.cache_key, { data, at: Date.now() });
}

export function updateCachedRecipe(
  cacheKey: string,
  patch: Partial<Pick<RecipeDetail, 'is_favorite' | 'is_saved'>>
): void {
  const entry = cache.get(cacheKey);
  if (entry) cache.set(cacheKey, { data: { ...entry.data, ...patch }, at: entry.at });
}
