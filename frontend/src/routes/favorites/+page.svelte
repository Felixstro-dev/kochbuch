<script lang="ts">
  import { goto } from '$app/navigation';
  import { Heart, Search } from 'lucide-svelte';
  import { api } from '#lib/api';
  import RecipeCard from '#lib/components/RecipeCard.svelte';
  import type { RecipeDetail, RecipeSummary } from '#lib/types';

  let { data }: { data: { items: RecipeSummary[]; total: number } } = $props();
  // svelte-ignore state_referenced_locally
  let items = $state(data.items);

  async function toggleFavorite(recipe: RecipeSummary) {
    const next = !recipe.is_favorite;
    items = items.map((item) =>
      item.cache_key === recipe.cache_key ? { ...item, is_favorite: next } : item
    );
    try {
      await api.patch<RecipeDetail>(`/recipes/${encodeURIComponent(recipe.cache_key)}`, {
        is_favorite: next
      });
      if (!next) items = items.filter((item) => item.cache_key !== recipe.cache_key);
    } catch {
      items = items.map((item) =>
        item.cache_key === recipe.cache_key ? { ...item, is_favorite: !next } : item
      );
    }
  }
</script>

<svelte:head>
  <title>Favoriten · Kochbuch</title>
</svelte:head>

<section class="head">
  <span class="eyebrow"><Heart size={14} /> Deine Sammlung</span>
  <h1>Favoriten</h1>
  <p class="muted">
    {items.length === 0
      ? 'Markierte Rezepte erscheinen hier und steigen in der Suche nach oben.'
      : `${items.length} ${items.length === 1 ? 'Rezept' : 'Rezepte'} – bereit zum Nachkochen.`}
  </p>
</section>

{#if items.length === 0}
  <div class="empty surface">
    <div class="empty-icon"><Heart size={26} /></div>
    <h2>Noch nichts gespeichert</h2>
    <p>Suche ein Rezept und tippe auf das Herz, um es hier zu sammeln.</p>
    <button class="btn btn-primary" type="button" onclick={() => goto('/')}>
      <Search size={16} /> Rezepte entdecken
    </button>
  </div>
{:else}
  <div class="grid">
    {#each items as recipe (recipe.cache_key)}
      <RecipeCard {recipe} onToggleFavorite={toggleFavorite} />
    {/each}
  </div>
{/if}

<style>
  .head {
    padding: 0.5rem 0 1.3rem;
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
    margin-bottom: 0.5rem;
  }

  h1 {
    font-size: clamp(1.9rem, 4vw, 2.8rem);
  }

  .head p {
    margin-top: 0.4rem;
    font-size: 0.9rem;
  }

  .grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(215px, 1fr));
    gap: 1rem;
  }

  .empty {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 0.6rem;
    text-align: center;
    padding: clamp(2.4rem, 7vw, 4rem) 1.2rem;
  }

  .empty-icon {
    display: grid;
    place-items: center;
    width: 56px;
    height: 56px;
    border-radius: 50%;
    background: color-mix(in srgb, #e8695b 14%, var(--surface-2));
    color: #e8695b;
    margin-bottom: 0.3rem;
  }

  .empty h2 {
    font-size: 1.25rem;
  }

  .empty p {
    color: var(--muted);
    font-size: 0.9rem;
    max-width: 42ch;
  }

  .empty .btn {
    margin-top: 0.5rem;
  }

  @media (max-width: 600px) {
    .grid {
      grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
    }
  }
</style>
