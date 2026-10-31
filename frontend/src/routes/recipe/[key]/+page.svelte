<script lang="ts">
  import { goto } from '$app/navigation';
  import {
    ArrowLeft,
    Check,
    ChefHat,
    Clock,
    ExternalLink,
    Flame,
    Heart,
    ImageOff,
    Link2,
    Minus,
    Plus,
    Printer,
    Share2,
    Users,
    Utensils
  } from 'lucide-svelte';
  import { api } from '#lib/api';
  import {
    amountFactor,
    difficultyLabel,
    formatAmount,
    formatMinutes,
    timerLabel,
    viewTransitionKey
  } from '#lib/format';
  import { rememberRecipe, updateCachedRecipe } from '#lib/prefetch';
  import Stars from '#lib/components/Stars.svelte';
  import type { RecipeDetail } from '#lib/types';

  let { data }: { data: { cacheKey: string; recipe: RecipeDetail } } = $props();

  // svelte-ignore state_referenced_locally
  let recipe = $state<RecipeDetail>(data.recipe);
  let imageLoaded = $state(false);
  let imageFailed = $state(false);
  // svelte-ignore state_referenced_locally
  let servings = $state(data.recipe.base_servings ?? 4);
  let checked = $state<Set<string>>(new Set());
  let copied = $state(false);
  let busy = $state(false);
  let heroPopping = $state(false);

  const baseServings = $derived(recipe.base_servings ?? 4);
  const factor = $derived(amountFactor(baseServings, servings));
  const scaling = $derived(Math.abs(factor - 1) > 0.001);

  const allIngredients = $derived(
    recipe.ingredient_groups.flatMap((group, groupIndex) =>
      group.items.map((item, itemIndex) => ({
        ...item,
        key: `${groupIndex}:${itemIndex}`,
        groupTitle: group.title
      }))
    )
  );

  const allChecked = $derived(
    allIngredients.length > 0 && allIngredients.every((item) => checked.has(item.key))
  );

  $effect(() => {
    rememberRecipe(recipe);
  });

  $effect(() => {
    if (typeof localStorage === 'undefined') return;
    try {
      const raw = localStorage.getItem(`kochbuch-checks:${recipe.cache_key}`);
      if (raw) checked = new Set(JSON.parse(raw) as string[]);
    } catch {
      checked = new Set();
    }
  });

  function toggleCheck(key: string) {
    const next = new Set(checked);
    if (next.has(key)) next.delete(key);
    else next.add(key);
    checked = next;
    try {
      localStorage.setItem(`kochbuch-checks:${recipe.cache_key}`, JSON.stringify([...next]));
    } catch {
      // Storage may be unavailable (private mode).
    }
  }

  function toggleAll() {
    const next = allChecked ? new Set<string>() : new Set(allIngredients.map((item) => item.key));
    checked = next;
    try {
      localStorage.setItem(`kochbuch-checks:${recipe.cache_key}`, JSON.stringify([...next]));
    } catch {
      // Ignore.
    }
  }

  function adjust(delta: number) {
    servings = Math.min(50, Math.max(1, servings + delta));
  }

  async function toggleFavorite() {
    const next = !recipe.is_favorite;
    heroPopping = true;
    setTimeout(() => (heroPopping = false), 400);
    recipe = {
      ...recipe,
      is_favorite: next,
      is_saved: next ? true : recipe.is_saved
    };
    updateCachedRecipe(recipe.cache_key, {
      is_favorite: recipe.is_favorite,
      is_saved: recipe.is_saved
    });
    try {
      await api.patch<RecipeDetail>(`/recipes/${encodeURIComponent(recipe.cache_key)}`, {
        is_favorite: next
      });
    } catch {
      recipe = { ...recipe, is_favorite: !next };
      updateCachedRecipe(recipe.cache_key, { is_favorite: !next });
    }
  }

  async function toggleSaved() {
    const next = !recipe.is_saved;
    recipe = { ...recipe, is_saved: next };
    updateCachedRecipe(recipe.cache_key, { is_saved: next });
    try {
      await api.patch<RecipeDetail>(`/recipes/${encodeURIComponent(recipe.cache_key)}`, {
        is_saved: next
      });
    } catch {
      recipe = { ...recipe, is_saved: !next };
      updateCachedRecipe(recipe.cache_key, { is_saved: !next });
    }
  }

  async function share() {
    const url = `${window.location.origin}/recipe/${encodeURIComponent(recipe.cache_key)}`;
    try {
      if (navigator.share) {
        await navigator.share({ title: recipe.title, url });
        return;
      }
      await navigator.clipboard.writeText(url);
      copied = true;
      setTimeout(() => (copied = false), 2000);
    } catch {
      // User cancelled the share sheet.
    }
  }

  function print() {
    window.print();
  }

  function startCooking() {
    goto(`/recipe/${encodeURIComponent(recipe.cache_key)}/cook`);
  }

  const nutritionEntries = $derived(
    recipe.nutrition
      ? Object.entries(recipe.nutrition).filter(([, value]) => value !== null && value !== '')
      : []
  );

  const nutritionLabels: Record<string, string> = {
    kcal: 'Kalorien',
    protein: 'Protein',
    carbs: 'Kohlenhydrate',
    fat: 'Fett',
    fiber: 'Ballaststoffe',
    sugar: 'Zucker',
    sodium: 'Salz'
  };
</script>

<svelte:head>
  <title>{recipe.title} · Kochbuch</title>
  <meta name="description" content={recipe.description || recipe.subtitle} />
</svelte:head>

<div class="detail fade-up">
  <button class="back no-print" type="button" onclick={() => history.length > 1 ? history.back() : goto('/')}>
    <ArrowLeft size={17} /> Zurück
  </button>

  <section class="hero" style:view-transition-name={viewTransitionKey(recipe.cache_key)}>
    <div class="hero-media">
      {#if recipe.image_url && !imageFailed}
        <img
          src={recipe.image_url}
          alt=""
          class:loaded={imageLoaded}
          onload={() => (imageLoaded = true)}
          onerror={() => (imageFailed = true)}
        />
      {:else}
        <div class="hero-placeholder"><ImageOff size={34} /></div>
      {/if}
      <div class="scrim"></div>

      <div class="hero-badges">
        <span class="chip source">{recipe.source_label}</span>
        {#if recipe.category}<span class="chip">{recipe.category}</span>{/if}
        {#if recipe.stale}<span class="chip">aus dem Cache</span>{/if}
      </div>
    </div>

    <div class="hero-body">
      <div class="hero-top">
        <h1>{recipe.title}</h1>
        <div class="hero-actions no-print">
          <button
            class="btn btn-icon"
            class:active={recipe.is_favorite}
            class:heart-pop={heroPopping}
            type="button"
            onclick={toggleFavorite}
            aria-pressed={recipe.is_favorite}
            aria-label={recipe.is_favorite ? 'Aus Favoriten entfernen' : 'Zu Favoriten hinzufügen'}
          >
            <Heart size={19} fill={recipe.is_favorite ? 'currentColor' : 'none'} />
          </button>
          <button class="btn btn-icon" type="button" onclick={share} aria-label="Teilen">
            {#if copied}<Check size={19} />{:else}<Share2 size={19} />{/if}
          </button>
          <button class="btn btn-icon" type="button" onclick={print} aria-label="Drucken">
            <Printer size={19} />
          </button>
        </div>
      </div>

      {#if recipe.subtitle}
        <p class="subtitle">{recipe.subtitle}</p>
      {/if}

      <div class="meta">
        {#if recipe.rating !== null}
          <Stars rating={recipe.rating} count={recipe.rating_count} size={15} />
        {/if}
        {#if recipe.prep_min}
          <span class="meta-item"><Clock size={15} /> {formatMinutes(recipe.prep_min)}</span>
        {/if}
        {#if recipe.cook_min}
          <span class="meta-item"><Flame size={15} /> {formatMinutes(recipe.cook_min)}</span>
        {/if}
        {#if recipe.total_min}
          <span class="meta-item"><Utensils size={15} /> {formatMinutes(recipe.total_min)}</span>
        {/if}
        {#if recipe.difficulty}
          <span class="meta-item"><ChefHat size={15} /> {difficultyLabel(recipe.difficulty)}</span>
        {/if}
        {#if recipe.base_servings}
          <span class="meta-item"><Users size={15} /> {recipe.base_servings} Portionen</span>
        {/if}
      </div>

      <div class="cta-row no-print">
        <button class="btn btn-primary" type="button" onclick={startCooking}>
          <ChefHat size={18} /> Kochmodus starten
        </button>
        <button class="btn" class:active={recipe.is_saved} type="button" onclick={toggleSaved}>
          {#if recipe.is_saved}<Check size={17} /> Gespeichert{:else}<Plus size={17} /> Merken{/if}
        </button>
      </div>
    </div>
  </section>

  {#if recipe.description && recipe.description !== recipe.subtitle}
    <p class="description">{recipe.description}</p>
  {/if}

  <div class="columns">
    <aside class="ingredients surface">
      <div class="section-head">
        <h2>Zutaten</h2>
        <div class="portion-control no-print" aria-label="Portionen anpassen">
          <button class="step-btn" type="button" onclick={() => adjust(-1)} aria-label="Weniger Portionen" disabled={servings <= 1}>
            <Minus size={15} />
          </button>
          <input
            class="portion-input"
            type="number"
            min="1"
            max="50"
            bind:value={servings}
            aria-label="Portionen"
          />
          <button class="step-btn" type="button" onclick={() => adjust(1)} aria-label="Mehr Portionen" disabled={servings >= 50}>
            <Plus size={15} />
          </button>
          <span class="portion-label">Portionen</span>
        </div>
      </div>

      {#if scaling}
        <p class="scale-note">Mengen für {servings} Portionen (Basis: {baseServings}).</p>
      {/if}

      {#if allIngredients.length === 0}
        <p class="muted empty">Für dieses Rezept wurden keine Zutaten gefunden.</p>
      {:else}
        <button class="check-all no-print" type="button" onclick={toggleAll}>
          {#if allChecked}<Check size={14} /> Alle abhaken{:else}Alle abhaken{/if}
        </button>

        {#each recipe.ingredient_groups as group, groupIndex}
          {#if group.items.length}
            {#if group.title}
              <h3 class="group-title">{group.title}</h3>
            {/if}
            <ul class="ingredient-list">
              {#each group.items as ingredient, itemIndex}
                {@const key = `${groupIndex}:${itemIndex}`}
                <li>
                  <label class="ingredient" class:done={checked.has(key)}>
                    <input
                      type="checkbox"
                      checked={checked.has(key)}
                      onchange={() => toggleCheck(key)}
                    />
                    <span class="tick" aria-hidden="true"><Check size={12} /></span>
                    <span class="amount">
                      {formatAmount(ingredient.amount, factor)}{ingredient.unit ? ` ${ingredient.unit}` : ''}
                    </span>
                    <span class="name">
                      {ingredient.name}
                      {#if ingredient.note}<span class="note">· {ingredient.note}</span>{/if}
                    </span>
                  </label>
                </li>
              {/each}
            </ul>
          {/if}
        {/each}
      {/if}
    </aside>

    <div class="steps-column">
      <section class="steps">
        <h2>Zubereitung</h2>
        {#if recipe.steps.length === 0}
          <p class="muted empty">Für dieses Rezept wurden keine Schritte gefunden.</p>
        {:else}
          <ol class="step-list">
            {#each recipe.steps as step, index}
              <li class="step">
                <span class="step-number">{index + 1}</span>
                <div class="step-body">
                  <p>{step.text}</p>
                  {#if step.timer_seconds}
                    <span class="chip chip-accent timer"><Clock size={12} /> {timerLabel(step.timer_seconds)}</span>
                  {/if}
                </div>
              </li>
            {/each}
          </ol>
        {/if}
      </section>

      {#if nutritionEntries.length}
        <section class="nutrition surface">
          <h2>Nährwerte <span class="muted">pro Portion</span></h2>
          <div class="nutrition-grid">
            {#each nutritionEntries as [key, value]}
              <div class="nutrient">
                <strong>{value}</strong>
                <span>{nutritionLabels[key] ?? key}</span>
              </div>
            {/each}
          </div>
        </section>
      {/if}

      {#if recipe.tags.length || recipe.author || recipe.url}
        <section class="footer-info surface">
          {#if recipe.author}
            <p class="byline">Von <strong>{recipe.author}</strong></p>
          {/if}
          {#if recipe.tags.length}
            <div class="tags">
              {#each recipe.tags.slice(0, 14) as tag}
                <span class="chip">{tag}</span>
              {/each}
            </div>
          {/if}
          {#if recipe.url}
            <a class="source-link" href={recipe.url} target="_blank" rel="noopener noreferrer">
              <Link2 size={15} /> Originalrezept ansehen <ExternalLink size={13} />
            </a>
          {/if}
        </section>
      {/if}
    </div>
  </div>
</div>

<style>
  .detail {
    display: flex;
    flex-direction: column;
    gap: 1.1rem;
  }

  .back {
    display: inline-flex;
    align-items: center;
    gap: 0.35rem;
    align-self: flex-start;
    padding: 0.35rem 0.6rem 0.35rem 0;
    border: 0;
    background: transparent;
    color: var(--muted);
    font-size: 0.82rem;
    font-weight: 600;
  }

  .back:hover {
    color: var(--text);
  }

  .hero {
    overflow: hidden;
    border-radius: 24px;
    border: 1px solid var(--border);
    background: var(--surface);
  }

  .hero-media {
    position: relative;
    aspect-ratio: 21 / 9;
    max-height: 420px;
    background: var(--surface-2);
  }

  .hero-media img {
    width: 100%;
    height: 100%;
    object-fit: cover;
    opacity: 0;
    transition: opacity 500ms ease;
  }

  .hero-media img.loaded {
    opacity: 1;
  }

  .hero-placeholder {
    display: grid;
    place-items: center;
    height: 100%;
    color: var(--muted);
    background: linear-gradient(135deg, var(--surface-2), var(--surface-3));
  }

  .scrim {
    position: absolute;
    inset: 0;
    background: linear-gradient(to top, rgb(10 8 6 / 0.55), transparent 55%);
    pointer-events: none;
  }

  .hero-badges {
    position: absolute;
    top: 0.8rem;
    left: 0.8rem;
    display: flex;
    flex-wrap: wrap;
    gap: 0.35rem;
  }

  .hero-badges .chip {
    background: rgb(12 10 8 / 0.6);
    border-color: rgb(255 255 255 / 0.18);
    color: #f4eee5;
    backdrop-filter: blur(8px);
  }

  .hero-body {
    display: flex;
    flex-direction: column;
    gap: 0.6rem;
    padding: clamp(1rem, 2.5vw, 1.6rem);
  }

  .hero-top {
    display: flex;
    align-items: flex-start;
    gap: 1rem;
  }

  h1 {
    font-size: clamp(1.6rem, 3.6vw, 2.6rem);
    flex: 1;
  }

  .hero-actions {
    display: flex;
    gap: 0.3rem;
    flex: none;
  }

  .hero-actions .btn.active {
    color: #e8695b;
    border-color: color-mix(in srgb, #e8695b 40%, var(--border));
    background: color-mix(in srgb, #e8695b 12%, var(--surface));
  }

  .subtitle {
    color: var(--muted);
    font-size: 0.92rem;
    max-width: 80ch;
  }

  .meta {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 0.5rem 1rem;
    color: var(--text-soft);
    font-size: 0.83rem;
  }

  .meta-item {
    display: inline-flex;
    align-items: center;
    gap: 0.3rem;
  }

  .cta-row {
    display: flex;
    flex-wrap: wrap;
    gap: 0.5rem;
    margin-top: 0.35rem;
  }

  .cta-row .btn.active {
    border-color: color-mix(in srgb, var(--success) 45%, var(--border));
    color: var(--success);
    background: color-mix(in srgb, var(--success) 12%, var(--surface));
  }

  .description {
    color: var(--text-soft);
    font-size: 0.92rem;
    line-height: 1.65;
    max-width: 85ch;
  }

  .columns {
    display: grid;
    grid-template-columns: minmax(280px, 360px) 1fr;
    gap: 1.2rem;
    align-items: start;
  }

  .ingredients {
    position: sticky;
    top: calc(var(--header-height) + 1rem);
    padding: 1.1rem;
    max-height: calc(100dvh - var(--header-height) - 2rem);
    overflow: auto;
  }

  .section-head {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    justify-content: space-between;
    gap: 0.6rem;
    margin-bottom: 0.6rem;
  }

  h2 {
    font-size: 1.15rem;
  }

  h2 .muted {
    font-size: 0.7rem;
    font-weight: 500;
  }

  .portion-control {
    display: flex;
    align-items: center;
    gap: 0.2rem;
    padding: 0.2rem;
    border-radius: 999px;
    border: 1px solid var(--border);
    background: var(--bg-elevated);
  }

  .step-btn {
    display: grid;
    place-items: center;
    width: 28px;
    height: 28px;
    border: 0;
    border-radius: 50%;
    background: var(--surface-2);
    color: var(--text);
  }

  .step-btn:disabled {
    opacity: 0.35;
    cursor: not-allowed;
  }

  .portion-input {
    width: 38px;
    border: 0;
    background: transparent;
    text-align: center;
    font-weight: 700;
    font-size: 0.9rem;
    outline: none;
    appearance: textfield;
    -moz-appearance: textfield;
  }

  .portion-input::-webkit-outer-spin-button,
  .portion-input::-webkit-inner-spin-button {
    -webkit-appearance: none;
    margin: 0;
  }

  .portion-label {
    padding-right: 0.5rem;
    font-size: 0.7rem;
    color: var(--muted);
  }

  .scale-note {
    margin-bottom: 0.5rem;
    font-size: 0.74rem;
    color: var(--accent);
  }

  .check-all {
    display: inline-flex;
    align-items: center;
    gap: 0.3rem;
    margin-bottom: 0.6rem;
    padding: 0.25rem 0.5rem;
    border-radius: 8px;
    border: 1px solid var(--border);
    background: transparent;
    color: var(--muted);
    font-size: 0.72rem;
  }

  .group-title {
    margin: 0.8rem 0 0.35rem;
    font-size: 0.78rem;
    font-weight: 700;
    letter-spacing: 0.03em;
    text-transform: uppercase;
    color: var(--accent);
  }

  .ingredient-list {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    flex-direction: column;
  }

  .ingredient {
    position: relative;
    display: grid;
    grid-template-columns: 18px 56px 1fr;
    align-items: baseline;
    gap: 0.45rem;
    padding: 0.45rem 0.35rem;
    border-radius: 9px;
    cursor: pointer;
    font-size: 0.87rem;
    transition: background 140ms ease;
  }

  .ingredient:hover {
    background: var(--surface-2);
  }

  .ingredient input {
    position: absolute;
    opacity: 0;
    pointer-events: none;
  }

  .tick {
    display: grid;
    place-items: center;
    width: 18px;
    height: 18px;
    border-radius: 6px;
    border: 1.5px solid var(--border-strong);
    color: transparent;
    transform: translateY(1px);
    transition:
      background 140ms ease,
      border-color 140ms ease,
      color 140ms ease;
  }

  .ingredient input:focus-visible + .tick {
    outline: 2px solid var(--accent);
    outline-offset: 2px;
  }

  .ingredient.done .tick {
    background: var(--accent);
    border-color: var(--accent);
    color: var(--accent-contrast);
  }

  .ingredient.done .amount,
  .ingredient.done .name {
    color: var(--muted);
    text-decoration: line-through;
  }

  .amount {
    color: var(--accent);
    font-weight: 700;
    font-variant-numeric: tabular-nums;
  }

  .name {
    line-height: 1.35;
  }

  .note {
    color: var(--muted);
    font-size: 0.8em;
  }

  .steps-column {
    display: flex;
    flex-direction: column;
    gap: 1.2rem;
    min-width: 0;
  }

  .steps h2 {
    margin-bottom: 0.8rem;
  }

  .step-list {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    flex-direction: column;
    gap: 0.9rem;
  }

  .step {
    display: flex;
    gap: 0.85rem;
    padding: 0.95rem 1rem;
    border-radius: 16px;
    border: 1px solid var(--border);
    background: var(--surface);
  }

  .step-number {
    display: grid;
    place-items: center;
    width: 30px;
    height: 30px;
    flex: none;
    border-radius: 50%;
    background: color-mix(in srgb, var(--accent) 16%, var(--surface-2));
    color: var(--accent);
    font-weight: 700;
    font-size: 0.82rem;
  }

  .step-body {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
    min-width: 0;
  }

  .step-body p {
    font-size: 0.92rem;
    line-height: 1.65;
    color: var(--text-soft);
    white-space: pre-line;
  }

  .timer {
    align-self: flex-start;
  }

  .nutrition {
    padding: 1rem 1.1rem;
  }

  .nutrition-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(90px, 1fr));
    gap: 0.7rem;
    margin-top: 0.7rem;
  }

  .nutrient {
    display: flex;
    flex-direction: column;
    gap: 0.1rem;
    padding: 0.55rem 0.65rem;
    border-radius: 12px;
    background: var(--surface-2);
  }

  .nutrient strong {
    font-size: 0.95rem;
    color: var(--accent);
  }

  .nutrient span {
    font-size: 0.7rem;
    color: var(--muted);
  }

  .footer-info {
    display: flex;
    flex-direction: column;
    gap: 0.7rem;
    padding: 1rem 1.1rem;
  }

  .byline {
    font-size: 0.82rem;
    color: var(--muted);
  }

  .byline strong {
    color: var(--text-soft);
  }

  .tags {
    display: flex;
    flex-wrap: wrap;
    gap: 0.35rem;
  }

  .source-link {
    display: inline-flex;
    align-items: center;
    gap: 0.35rem;
    align-self: flex-start;
    font-size: 0.8rem;
    font-weight: 600;
    color: var(--accent);
  }

  .source-link:hover {
    text-decoration: underline;
  }

  .empty {
    font-size: 0.85rem;
    padding: 0.5rem 0;
  }

  .heart-pop {
    animation: heart-pop 380ms ease;
  }

  @media (max-width: 860px) {
    .columns {
      grid-template-columns: 1fr;
    }

    .ingredients {
      position: static;
      max-height: none;
    }

    .hero-media {
      aspect-ratio: 16 / 10;
    }
  }

  @media print {
    .ingredients {
      position: static;
      max-height: none;
      border: 0;
      padding: 0;
    }

    .step {
      break-inside: avoid;
      border-color: #ddd;
    }
  }
</style>
