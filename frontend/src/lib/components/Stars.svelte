<script lang="ts">
  import { Star } from 'lucide-svelte';
  import { formatRating } from '#lib/format';

  let {
    rating,
    count = 0,
    size = 14
  }: { rating: number | null; count?: number; size?: number } = $props();

  const rounded = $derived(rating ? Math.round(rating * 2) / 2 : 0);
</script>

{#if rating !== null}
  <span class="rating" aria-label={`Bewertung ${formatRating(rating)} von 5`}>
    <span class="stars" aria-hidden="true">
      {#each [1, 2, 3, 4, 5] as star}
        <Star
          size={size}
          strokeWidth={1.8}
          fill={star <= rounded ? 'currentColor' : 'none'}
          class={star > rounded ? 'dim' : ''}
        />
      {/each}
    </span>
    <strong>{formatRating(rating)}</strong>
    {#if count}<span class="count">({count.toLocaleString('de-DE')})</span>{/if}
  </span>
{/if}

<style>
  .rating {
    display: inline-flex;
    align-items: center;
    gap: 0.35rem;
    color: var(--text-soft);
    font-size: 0.8rem;
  }

  .stars {
    display: inline-flex;
    gap: 1px;
    color: var(--accent);
  }

  .stars :global(.dim) {    color: color-mix(in srgb, var(--muted) 45%, transparent);
  }

  strong {
    font-weight: 700;
    color: var(--text);
  }

  .count {
    color: var(--muted);
    font-size: 0.75rem;
  }
</style>
