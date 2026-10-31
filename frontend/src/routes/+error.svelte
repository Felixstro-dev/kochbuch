<script lang="ts">
  import { page } from '$app/state';
  import { ChefHat, Home } from 'lucide-svelte';

  const status = $derived(page.status);
  const message = $derived(
    page.error?.message || 'Diese Seite konnte nicht geladen werden.'
  );
</script>

<svelte:head>
  <title>{status} · Kochbuch</title>
</svelte:head>

<div class="error-wrap">
  <span class="mark"><ChefHat size={30} /></span>
  <span class="code">{status}</span>
  <h1>{status === 404 ? 'Seite nicht gefunden' : 'Da ist etwas angebrannt'}</h1>
  <p>{message}</p>
  <a class="btn btn-primary" href="/"><Home size={16} /> Zur Startseite</a>
</div>

<style>
  .error-wrap {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 0.6rem;
    min-height: 60dvh;
    text-align: center;
    padding: 2rem 1rem;
  }

  .mark {
    display: grid;
    place-items: center;
    width: 64px;
    height: 64px;
    border-radius: 20px;
    background: var(--surface-2);
    color: var(--accent);
    margin-bottom: 0.4rem;
  }

  .code {
    font-size: 0.75rem;
    font-weight: 700;
    letter-spacing: 0.14em;
    color: var(--muted);
  }

  h1 {
    font-size: clamp(1.5rem, 4vw, 2.1rem);
  }

  p {
    color: var(--muted);
    max-width: 46ch;
    font-size: 0.9rem;
  }

  .btn {
    margin-top: 0.7rem;
  }
</style>
