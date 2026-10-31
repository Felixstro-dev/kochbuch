<script lang="ts">
  import { Clock, Heart, ImageOff } from 'lucide-svelte';
  import { formatMinutes, difficultyLabel, viewTransitionKey } from '#lib/format';
  import { prefetchRecipe } from '#lib/prefetch';
  import type { RecipeSummary } from '#lib/types';
  import Stars from './Stars.svelte';

  let {
    recipe,
    onToggleFavorite
  }: {
    recipe: RecipeSummary;
    onToggleFavorite?: (recipe: RecipeSummary) => void;
  } = $props();

  let imageLoaded = $state(false);
  let imageFailed = $state(false);
  let popping = $state(false);

  const href = $derived(`/recipe/${encodeURIComponent(recipe.cache_key)}`);

  function favorite(event: MouseEvent) {
    event.preventDefault();
    event.stopPropagation();
    popping = true;
    setTimeout(() => (popping = false), 400);
    onToggleFavorite?.(recipe);
  }
</script>

<a
  {href}
  class="card fade-up"
  onmouseenter={() => prefetchRecipe(recipe.cache_key)}
  onfocus={() => prefetchRecipe(recipe.cache_key)}
  style:view-transition-name={viewTransitionKey(recipe.cache_key)}
>
  <div class="thumb" class:has-blur={!imageLoaded && !!recipe.image_blurhash}>
    {#if recipe.image_url && !imageFailed}
      {#if !imageLoaded && recipe.image_blurhash}
        <img
          class="blur"
          src={`data:image/svg+xml,${encodeURIComponent(
            `<svg xmlns="http://www.w3.org/2000/svg" width="32" height="32"><rect width="32" height="32" fill="#2a251f"/></svg>`
          )}`}
          alt=""
          aria-hidden="true"
        />
      {/if}
      <img
        src={recipe.image_url}
        alt=""
        loading="lazy"
        decoding="async"
        class:loaded={imageLoaded}
        onload={() => (imageLoaded = true)}
        onerror={() => (imageFailed = true)}
      />
    {:else}
      <div class="placeholder"><ImageOff size={22} /></div>
    {/if}

    <div class="badges">
      <span class="chip source">{recipe.source_label}</span>
      {#if recipe.stale}<span class="chip">offline</span>{/if}
    </div>

    <button
      class="fav"
      class:active={recipe.is_favorite}
      class:heart-pop={popping}
      type="button"
      onclick={favorite}
      aria-label={recipe.is_favorite ? 'Aus Favoriten entfernen' : 'Zu Favoriten hinzufügen'}
      aria-pressed={recipe.is_favorite}
    >
      <Heart size={17} fill={recipe.is_favorite ? 'currentColor' : 'none'} />
    </button>
  </div>

  <div class="body">
    <h3 class="line-clamp-2">{recipe.title}</h3>
    {#if recipe.subtitle}
      <p class="line-clamp-2 sub">{recipe.subtitle}</p>
    {/if}

    <div class="meta">
      {#if recipe.rating !== null}
        <Stars rating={recipe.rating} count={recipe.rating_count} size={13} />
      {/if}
      {#if recipe.total_min}
        <span class="meta-item"><Clock size={13} />{formatMinutes(recipe.total_min)}</span>
      {/if}
      {#if recipe.difficulty}
        <span class="meta-item dot">{difficultyLabel(recipe.difficulty)}</span>
      {/if}
    </div>
  </div>
</a>

<style>
  .card {
    display: flex;
    flex-direction: column;
    overflow: hidden;
    border-radius: 18px;
    border: 1px solid var(--border);
    background: var(--surface);
    transition:
      transform 220ms cubic-bezier(0.22, 1, 0.36, 1),
      border-color 220ms ease,
      box-shadow 220ms ease;
  }

  .card:hover {
    transform: translateY(-3px);
    border-color: var(--border-strong);
    box-shadow: var(--shadow);
  }

  .thumb {
    position: relative;
    aspect-ratio: 4 / 3;
    background: var(--surface-2);
    overflow: hidden;
  }

  .thumb img {
    width: 100%;
    height: 100%;
    object-fit: cover;
    opacity: 0;
    transition:
      opacity 420ms ease,
      transform 600ms cubic-bezier(0.22, 1, 0.36, 1);
  }

  .thumb img.loaded {
    opacity: 1;
  }

  .card:hover .thumb img.loaded {
    transform: scale(1.04);
  }

  .thumb img.blur {
    position: absolute;
    inset: 0;
    opacity: 1;
    filter: blur(14px);
    transform: scale(1.1);
  }

  .placeholder {
    display: grid;
    place-items: center;
    height: 100%;
    color: var(--muted);
    background: linear-gradient(135deg, var(--surface-2), var(--surface-3));
  }

  .badges {
    position: absolute;
    top: 0.6rem;
    left: 0.6rem;
    display: flex;
    gap: 0.3rem;
  }

  .badges .chip {
    background: rgb(12 10 8 / 0.6);
    border-color: rgb(255 255 255 / 0.16);
    color: #f4eee5;
    backdrop-filter: blur(8px);
    font-size: 0.68rem;
    padding: 0.16rem 0.5rem;
  }

  .fav {
    position: absolute;
    top: 0.5rem;
    right: 0.5rem;
    display: grid;
    place-items: center;
    width: 36px;
    height: 36px;
    border-radius: 50%;
    border: 1px solid rgb(255 255 255 / 0.18);
    background: rgb(12 10 8 / 0.55);
    color: #f4eee5;
    backdrop-filter: blur(10px);
    transition:
      background 160ms ease,
      color 160ms ease,
      transform 160ms ease;
  }

  .fav:hover {
    background: rgb(12 10 8 / 0.8);
  }

  .fav.active {
    color: #e8695b;
  }

  .body {
    display: flex;
    flex-direction: column;
    gap: 0.35rem;
    padding: 0.8rem 0.85rem 0.9rem;
  }

  h3 {
    font-size: 0.97rem;
    line-height: 1.25;
    letter-spacing: -0.015em;
  }

  .sub {
    color: var(--muted);
    font-size: 0.78rem;
    line-height: 1.4;
  }

  .meta {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 0.5rem;
    margin-top: 0.15rem;
    font-size: 0.76rem;
    color: var(--muted);
  }

  .meta-item {
    display: inline-flex;
    align-items: center;
    gap: 0.25rem;
  }

  .dot::before {
    content: '·';
    margin-right: 0.3rem;
    color: var(--border-strong);
  }
</style>
