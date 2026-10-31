export interface User {
  id: string;
  username: string;
  display_name: string;
  role: 'admin' | 'member' | string;
  is_active: boolean;
  created_at: string;
  last_login_at: string | null;
}

export interface AuthStatus {
  setup_required: boolean;
  authenticated: boolean;
  user: User | null;
  embed_public: boolean;
  app_name: string;
  version: string;
}

export interface AuthResponse {
  user: User;
  csrf_token: string;
}

export interface Ingredient {
  name: string;
  amount: number | null;
  unit: string;
  note: string;
}

export interface IngredientGroup {
  title: string;
  items: Ingredient[];
}

export interface RecipeStep {
  text: string;
  timer_seconds: number | null;
}

export interface RecipeSummary {
  cache_key: string;
  source: string;
  source_label: string;
  title: string;
  subtitle: string;
  image_url: string | null;
  image_blurhash: string | null;
  rating: number | null;
  rating_count: number;
  prep_min: number | null;
  total_min: number | null;
  difficulty: number | null;
  category: string;
  url: string;
  is_favorite: boolean;
  is_saved: boolean;
  stale: boolean;
}

export interface RecipeDetail extends RecipeSummary {
  description: string;
  author: string;
  cook_min: number | null;
  base_servings: number | null;
  ingredient_groups: IngredientGroup[];
  steps: RecipeStep[];
  nutrition: Record<string, string | number> | null;
  tags: string[];
  categories: string[];
  image_count: number;
  fetched_at: string | null;
}

export interface SearchResponse {
  items: RecipeSummary[];
  total: number;
  page: number;
  limit: number;
  providers: string[];
  cached: boolean;
  stale: boolean;
  errors: string[];
  took_ms: number;
}

export interface RecipeListResponse {
  items: RecipeSummary[];
  total: number;
}

export interface ProviderInfo {
  name: string;
  label: string;
  can_search: boolean;
  enabled: boolean;
}

export interface AppSettings {
  app_name: string;
  default_theme: string;
  accent_color: string;
  embed_public: boolean;
  enabled_providers: string[];
  fetch: FetchConfig;
}

export interface FetchConfig {
  proxy_configured: boolean;
  proxy_host: string | null;
  proxy_for_images: boolean;
  flaresolverr_configured: boolean;
  flaresolverr_url: string | null;
  flaresolverr_timeout: number;
  max_retries: number;
  timeout: number;
  browser_impersonation: boolean;
  curl_cffi: boolean;
}

export interface FetchActive {
  domain: string;
  stage: string;
  label: string;
  tier: string;
  attempt: number;
  started_at: string | null;
}

export interface FetchDomain {
  domain: string;
  successes: number;
  failures: number;
  last_tier: string | null;
  last_success_at: string | null;
  circuit_open_until: string | null;
  rate_limited: boolean;
}

export interface FetchStatus {
  proxy_configured: boolean;
  proxy_host: string | null;
  proxy_for_images: boolean;
  flaresolverr_configured: boolean;
  flaresolverr_url: string | null;
  flaresolverr_timeout: number;
  max_retries: number;
  timeout: number;
  min_interval: number;
  browser_impersonation: boolean;
  curl_cffi: boolean;
  totals: {
    requests: number;
    successes: number;
    failures: number;
    blocked: number;
    by_tier: Record<string, number>;
  };
  active: FetchActive[];
  domains: FetchDomain[];
}

export interface FetchTestResult {
  ok: boolean;
  target: string;
  detail: string;
  status: number | null;
  tier: string | null;
  elapsed_ms: number | null;
}

export interface ApiKey {
  id: string;
  name: string;
  prefix: string;
  scopes: string[];
  created_at: string;
  expires_at: string | null;
  last_used_at: string | null;
  revoked_at: string | null;
}

export interface ApiKeyCreated extends ApiKey {
  secret: string;
}
