<script lang="ts">
  import { goto } from '$app/navigation';
  import { page } from '$app/state';
  import {
    ArrowRight,
    Clock3,
    Gauge,
    Link2,
    LoaderCircle,
    RefreshCw,
    Search,
    Sparkles,
    X
  } from 'lucide-svelte';
  import { api, ApiError } from '#lib/api';
  import FetchStageHint from '#lib/components/FetchStageHint.svelte';
  import PotLoader from '#lib/components/PotLoader.svelte';
  import RecipeCard from '#lib/components/RecipeCard.svelte';
  import SkeletonGrid from '#lib/components/SkeletonGrid.svelte';
  import type { RecipeDetail, RecipeSummary, SearchResponse } from '#lib/types';

  const suggestions = ['Lasagne', 'Curry', 'Pfannkuchen', 'Salat', 'Suppe', 'Kuchen'];

  let inputValue = $state(page.url.searchParams.get('q') ?? '');
  let results = $state<RecipeSummary[]>([]);
  let total = $state(0);
  let providers = $state<string[]>([]);
  let errors = $state<string[]>([]);
  let loading = $state(false);
  let loadingMore = $state(false);
  let searched = $state(false);
  let error = $state('');
  let tookMs = $state(0);

  let urlPanelOpen = $state(false);
  let urlValue = $state('');
  let urlBusy = $state(false);
  let urlError = $state('');

  let debounceTimer: ReturnType<typeof setTimeout> | undefined;
  let activeToken = 0;
  let pushedQuery = page.url.searchParams.get('q') ?? '';

  const urlQuery = $derived(page.url.searchParams.get('q') ?? '');
  const maxTime = $derived(page.url.searchParams.get('max_time') ?? '');
  const difficulty = $derived(page.url.searchParams.get('difficulty') ?? '');
  const sort = $derived(page.url.searchParams.get('sort') ?? 'relevance');
  const hasQuery = $derived(urlQuery.trim().length > 0);

  function setParam(key: string, value: string | null) {
    const url = new URL(page.url.href);
    if (value === null || value === '') url.searchParams.delete(key);
    else url.searchParams.set(key, value);
    if (key === 'q') pushedQuery = value ?? '';
    goto(`/?${url.searchParams.toString()}`, { replace: true, reset: false });
  }

  function onInput() {
    clearTimeout(debounceTimer);
    debounceTimer = setTimeout(() => {
      const value = inputValue.trim();
      if (value === urlQuery) return;
      setParam('q', value || null);
    }, 320);
  }

  function submit(event: SubmitEvent) {
    event.preventDefault();
    clearTimeout(debounceTimer);
    setParam('q', inputValue.trim() || null);
  }

  function clearSearch() {
    clearTimeout(debounceTimer);
    inputValue = '';
    setParam('q', null);
  }

  function useSuggestion(value: string) {
    inputValue = value;
    setParam('q', value);
  }

  async function fetchPage(
    q: string,
    mt: string,
    diff: string,
    sortValue: string,
    pageNumber: number
  ): Promise<SearchResponse> {
    return api.get<SearchResponse>('/search', {
      query: {
        q,
        page: pageNumber,
        limit: 24,
        max_time: mt || null,
        difficulty: diff || null,
        sort: sortValue
      }
    });
  }

  async function runSearch(q: string, mt: string, diff: string, sortValue: string) {
    if (!q.trim()) {
      results = [];
      total = 0;
      searched = false;
      loading = false;
      error = '';
      return;
    }
    const token = ++activeToken;
    loading = true;
    error = '';
    try {
      const response = await fetchPage(q, mt, diff, sortValue, 1);
      if (token !== activeToken) return;
      results = response.items;
      total = response.total;
      providers = response.providers;
      errors = response.errors;
      tookMs = response.took_ms;
      searched = true;
    } catch (cause) {
      if (token !== activeToken) return;
      error =
        cause instanceof ApiError
          ? cause.message
          : 'Die Suche ist fehlgeschlagen. Bitte erneut versuchen.';
      results = [];
      total = 0;
    } finally {
      if (token === activeToken) loading = false;
    }
  }

  async function loadMore() {
    if (loadingMore || !hasQuery || results.length >= total) return;
    const nextPage = Math.floor(results.length / 24) + 1;
    loadingMore = true;
    try {
      const response = await fetchPage(urlQuery, maxTime, difficulty, sort, nextPage);
      const existing = new Set(results.map((item) => item.cache_key));
      results = [...results, ...response.items.filter((item) => !existing.has(item.cache_key))];
      total = Math.max(total, response.total);
    } catch {
      // Keep the existing results; the button can be retried.
    } finally {
      loadingMore = false;
    }
  }

  async function toggleFavorite(recipe: RecipeSummary) {
    const next = !recipe.is_favorite;
    results = results.map((item) =>
      item.cache_key === recipe.cache_key
        ? { ...item, is_favorite: next, is_saved: next || item.is_saved }
        : item
    );
    try {
      await api.patch<RecipeDetail>(`/recipes/${encodeURIComponent(recipe.cache_key)}`, {
        is_favorite: next
      });
    } catch {
      results = results.map((item) =>
        item.cache_key === recipe.cache_key ? { ...item, is_favorite: !next } : item
      );
    }
  }

  async function importUrl(event: SubmitEvent) {
    event.preventDefault();
    const value = urlValue.trim();
    if (!value || urlBusy) return;
    urlBusy = true;
    urlError = '';
    try {
      const detail = await api.post<RecipeDetail>('/recipes/resolve', { url: value });
      urlValue = '';
      urlPanelOpen = false;
      await goto(`/recipe/${encodeURIComponent(detail.cache_key)}`);
    } catch (cause) {
      urlError =
        cause instanceof ApiError
          ? cause.message
          : 'Das Rezept konnte nicht importiert werden.';
    } finally {
      urlBusy = false;
    }
  }

  $effect(() => {
    const q = page.url.searchParams.get('q') ?? '';
    const mt = page.url.searchParams.get('max_time') ?? '';
    const diff = page.url.searchParams.get('difficulty') ?? '';
    const sortValue = page.url.searchParams.get('sort') ?? 'relevance';
    if (q !== pushedQuery) inputValue = q;
    void runSearch(q, mt, diff, sortValue);
  });

  $effect(() => () => clearTimeout(debounceTimer));
</script>

<svelte:head>
  <title>{hasQuery ? `${urlQuery} · Suche` : 'Rezepte finden'}</title>
</svelte:head>

<section class="hero" class:compact={hasQuery}>
  <div class="hero-copy">
    <span class="eyebrow"><Sparkles size={14} /> Ohne Anmeldung bei Chefkoch & Co.</span>
    <h1>
      {#if hasQuery}
        Ergebnisse für <span class="accent">„{urlQuery}“</span>
      {:else}
        Was kochst du <span class="accent">heute?</span>
      {/if}
    </h1>
    <p>
      {#if hasQuery}
        {#if loading}Suche läuft …{:else}{total.toLocaleString('de-DE')} Rezepte gefunden{/if}{#if tookMs && !loading}
          <span class="muted">· {tookMs} ms</span>{/if}
      {:else}
        Durchsuche tausende Rezepte und starte sofort im Kochmodus – speichern kannst du später.
      {/if}
    </p>
  </div>

  <form class="searchbar" onsubmit={submit} role="search">
    <Search size={20} />
    <input
      bind:value={inputValue}
      oninput={onInput}
      type="search"
      placeholder="Zutat, Gericht oder Rezeptname …"
      aria-label="Rezepte durchsuchen"
      autocomplete="off"
    />
    {#if inputValue}
      <button class="clear" type="button" onclick={clearSearch} aria-label="Suche leeren">
        <X size={16} />
      </button>
    {/if}
    <button class="btn btn-primary go" type="submit">
      Suchen <ArrowRight size={16} />
    </button>
  </form>

  {#if !hasQuery}
    <div class="suggestions">
      <span class="muted">Vielleicht:</span>
      {#each suggestions as suggestion}
        <button class="chip suggestion" type="button" onclick={() => useSuggestion(suggestion)}>
          {suggestion}
        </button>
      {/each}
      <button class="chip suggestion url-toggle" type="button" onclick={() => (urlPanelOpen = !urlPanelOpen)}>
        <Link2 size={13} /> Rezept-URL einfügen
      </button>
    </div>
  {/if}

  {#if urlPanelOpen}
    <form class="url-import surface" onsubmit={importUrl}>
      <div class="url-copy">
        <strong>Rezept von einer Website holen</strong>
        <span class="muted">Zum Beispiel von einem Foodblog oder Magazin.</span>
      </div>
      <div class="url-row">
        <input
          class="field"
          bind:value={urlValue}
          type="url"
          placeholder="https://…"
          aria-label="Rezept-URL"
          required
        />
        <button class="btn btn-primary" type="submit" disabled={urlBusy}>
          {#if urlBusy}<LoaderCircle class="spin" size={17} />{:else}<Link2 size={17} />{/if}
          Importieren
        </button>
      </div>
      <FetchStageHint active={urlBusy} />
      {#if urlError}<p class="error" role="alert">{urlError}</p>{/if}
    </form>
  {/if}
</section>

{#if hasQuery}
  <div class="toolbar">
    <div class="filters">
      <span class="filter-label"><Clock3 size={14} /> Zeit</span>
      {#each [
        ['', 'Egal'],
        ['30', '≤ 30 Min.'],
        ['60', '≤ 60 Min.'],
        ['120', '≤ 2 Std.']
      ] as [value, label]}
        <button
          class="chip filter"
          class:accent-chip={maxTime === value}
          type="button"
          onclick={() => setParam('max_time', value)}
        >
          {label}
        </button>
      {/each}
    </div>

    <div class="filters">
      <span class="filter-label"><Gauge size={14} /> Niveau</span>
      {#each [
        ['', 'Alle'],
        ['1', 'Einfach'],
        ['2', 'Mittel'],
        ['3', 'Anspruchsvoll']
      ] as [value, label]}
        <button
          class="chip filter"
          class:accent-chip={difficulty === value}
          type="button"
          onclick={() => setParam('difficulty', value)}
        >
          {label}
        </button>
      {/each}
    </div>

    <label class="sort">
      <span class="muted">Sortieren</span>
      <select
        class="field select"
        value={sort}
        onchange={(event) => setParam('sort', event.currentTarget.value)}
      >
        <option value="relevance">Relevanz</option>
        <option value="rating">Bewertung</option>
        <option value="time">Schnellste</option>
      </select>
    </label>
  </div>

  {#if errors.length}
    <div class="notice">
      <span>Einige Quellen waren nicht erreichbar:</span>
      {#each errors as message}<span class="chip">{message}</span>{/each}
      <button class="btn btn-ghost btn-icon refresh" type="button" onclick={() => goto(page.url.href)} aria-label="Erneut suchen">
        <RefreshCw size={15} />
      </button>
    </div>
  {/if}
{/if}

{#if error}
  <div class="state surface">
    <h2>Das hat nicht geklappt</h2>
    <p>{error}</p>
    <button class="btn btn-primary" type="button" onclick={() => setParam('q', urlQuery)}>
      <RefreshCw size={16} /> Nochmal versuchen
    </button>
  </div>
{:else if loading && results.length === 0}
  <SkeletonGrid />
{:else if loading && results.length > 0}
  <div class="grid">
    {#each results as recipe (recipe.cache_key)}
      <RecipeCard {recipe} onToggleFavorite={toggleFavorite} />
    {/each}
  </div>
  <PotLoader label="Weitere Rezepte werden gesucht …" />
{:else if hasQuery && results.length === 0 && searched}
  <div class="state surface">
    <div class="state-icon"><Search size={26} /></div>
    <h2>Nichts gefunden</h2>
    <p>Versuche einen anderen Begriff oder entferne Filter.</p>
    <div class="state-actions">
      <button class="btn" type="button" onclick={() => useSuggestion('Nudeln')}>Nudeln probieren</button>
      <button class="btn btn-ghost" type="button" onclick={() => setParam('max_time', null)}>Filter zurücksetzen</button>
    </div>
  </div>
{:else if hasQuery}
  <div class="grid">
    {#each results as recipe (recipe.cache_key)}
      <RecipeCard {recipe} onToggleFavorite={toggleFavorite} />
    {/each}
  </div>

  {#if results.length < total}
    <div class="more">
      <button class="btn" type="button" onclick={loadMore} disabled={loadingMore}>
        {#if loadingMore}<LoaderCircle class="spin" size={17} />{:else}<ArrowRight size={16} />{/if}
        Mehr laden
        <span class="muted">({results.length} von {total.toLocaleString('de-DE')})</span>
      </button>
    </div>
  {/if}
{:else}
  <section class="start">
    <div class="start-card surface">
      <div>
        <h2>Einfach lostippen</h2>
        <p class="muted">
          Die Suche fragt Chefkoch und deine eigenen Rezepte parallel ab. Favoriten rücken
          automatisch nach oben.
        </p>
      </div>
      <div class="start-badges">
        <span class="chip chip-accent"><Clock3 size={13} /> Zeitfilter</span>
        <span class="chip chip-accent"><Gauge size={13} /> Schwierigkeit</span>
        <span class="chip chip-accent"><Link2 size={13} /> URL-Import</span>
      </div>
    </div>
  </section>
{/if}

<style>
  .hero {
    display: flex;
    flex-direction: column;
    gap: 1.15rem;
    padding: clamp(1.2rem, 4vw, 2.8rem) 0 clamp(0.9rem, 2.5vw, 1.5rem);
  }

  .eyebrow {
    display: inline-flex;
    align-items: center;
    gap: 0.35rem;
    font-size: 0.72rem;
    font-weight: 700;
    letter-spacing: 0.09em;
    text-transform: uppercase;
    color: var(--accent);
    margin-bottom: 0.55rem;
  }

  h1 {
    font-size: clamp(2rem, 5vw, 3.35rem);
    line-height: 1.02;
    max-width: 20ch;
  }

  .compact h1 {
    font-size: clamp(1.55rem, 3.4vw, 2.35rem);
  }

  .hero-copy p {
    margin-top: 0.6rem;
    color: var(--muted);
    font-size: clamp(0.88rem, 1.4vw, 0.98rem);
    max-width: 62ch;
  }

  .searchbar {
    display: flex;
    align-items: center;
    gap: 0.6rem;
    width: min(760px, 100%);
    padding: 0.4rem 0.4rem 0.4rem 1rem;
    border-radius: 999px;
    border: 1px solid var(--border);
    background: var(--surface);
    color: var(--muted);
    box-shadow: 0 18px 40px rgb(0 0 0 / 0.18);
    transition:
      border-color 180ms ease,
      box-shadow 180ms ease;
  }

  .searchbar:focus-within {
    border-color: var(--accent);
    box-shadow: 0 0 0 4px color-mix(in srgb, var(--accent) 16%, transparent);
  }

  .searchbar input {
    flex: 1;
    min-width: 0;
    height: 44px;
    border: 0;
    background: transparent;
    outline: none;
    color: var(--text);
    font-size: 1rem;
  }

  .clear {
    display: grid;
    place-items: center;
    width: 32px;
    height: 32px;
    border: 0;
    border-radius: 50%;
    background: var(--surface-2);
    color: var(--muted);
  }

  .go {
    min-height: 44px;
    padding-inline: 1.15rem;
  }

  .suggestions {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 0.4rem;
    font-size: 0.8rem;
  }

  .suggestion {
    background: transparent;
    transition:
      border-color 150ms ease,
      color 150ms ease;
  }

  .suggestion:hover {
    border-color: var(--accent);
    color: var(--accent);
  }

  .url-toggle {
    color: var(--accent);
  }

  .url-import {
    display: flex;
    flex-direction: column;
    gap: 0.7rem;
    width: min(760px, 100%);
    padding: 1rem;
    background: var(--bg-elevated);
  }

  .url-copy {
    display: flex;
    flex-direction: column;
    gap: 0.1rem;
    font-size: 0.85rem;
  }

  .url-copy strong {
    font-size: 0.88rem;
  }

  .url-row {
    display: flex;
    gap: 0.5rem;
  }

  .url-row .field {
    flex: 1;
  }

  .error {
    color: var(--danger);
    font-size: 0.82rem;
  }

  .toolbar {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 0.55rem 1.1rem;
    padding: 0.6rem 0 1rem;
    border-bottom: 1px solid var(--border);
    margin-bottom: 1.1rem;
  }

  .filters {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 0.35rem;
  }

  .filter-label {
    display: inline-flex;
    align-items: center;
    gap: 0.3rem;
    font-size: 0.72rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: var(--muted);
    margin-right: 0.15rem;
  }

  .filter {
    background: transparent;
    font-size: 0.76rem;
    transition:
      background 140ms ease,
      border-color 140ms ease,
      color 140ms ease;
  }

  .filter:hover {
    border-color: var(--border-strong);
  }

  .accent-chip {
    background: color-mix(in srgb, var(--accent) 16%, var(--surface));
    border-color: color-mix(in srgb, var(--accent) 45%, var(--border));
    color: var(--accent);
  }

  .sort {
    display: inline-flex;
    align-items: center;
    gap: 0.45rem;
    margin-left: auto;
    font-size: 0.76rem;
    font-weight: 600;
  }

  .select {
    min-height: 36px;
    width: auto;
    padding: 0.25rem 0.6rem;
    font-size: 0.8rem;
    border-radius: 10px;
  }

  .notice {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 0.4rem;
    padding: 0.5rem 0.7rem;
    margin-bottom: 1rem;
    border-radius: 12px;
    border: 1px dashed var(--border-strong);
    color: var(--muted);
    font-size: 0.76rem;
  }

  .refresh {
    margin-left: auto;
    width: 34px;
    min-width: 34px;
    min-height: 34px;
  }

  .grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(215px, 1fr));
    gap: 1rem;
  }

  .more {
    display: flex;
    justify-content: center;
    padding: 2rem 0 1rem;
  }

  .state {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 0.6rem;
    text-align: center;
    padding: clamp(2rem, 6vw, 3.4rem) 1.2rem;
    margin-top: 1rem;
  }

  .state h2 {
    font-size: 1.3rem;
  }

  .state p {
    color: var(--muted);
    max-width: 46ch;
    font-size: 0.9rem;
  }

  .state-icon {
    display: grid;
    place-items: center;
    width: 54px;
    height: 54px;
    border-radius: 50%;
    background: var(--surface-2);
    color: var(--muted);
    margin-bottom: 0.3rem;
  }

  .state-actions {
    display: flex;
    gap: 0.5rem;
    flex-wrap: wrap;
    justify-content: center;
    margin-top: 0.5rem;
  }

  .start-card {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    justify-content: space-between;
    gap: 1rem;
    padding: 1.3rem;
    background: linear-gradient(135deg, var(--surface), var(--bg-elevated));
  }

  .start-card h2 {
    font-size: 1.1rem;
    margin-bottom: 0.3rem;
  }

  .start-card p {
    font-size: 0.86rem;
    max-width: 52ch;
  }

  .start-badges {
    display: flex;
    flex-wrap: wrap;
    gap: 0.35rem;
  }

  :global(.spin) {
    animation: spin 900ms linear infinite;
  }

  @keyframes spin {
    to {
      transform: rotate(360deg);
    }
  }

  @media (max-width: 600px) {
    .searchbar {
      padding-left: 0.8rem;
    }

    .go {
      padding-inline: 0.85rem;
    }

    .go :global(svg) {
      display: none;
    }

    .sort {
      margin-left: 0;
    }

    .grid {
      grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
    }
  }
</style>
