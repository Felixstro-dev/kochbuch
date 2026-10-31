<script lang="ts">
  import { CookingPot } from 'lucide-svelte';

  let { label = 'Rezepte werden gesucht …' }: { label?: string } = $props();
</script>

<div class="pot-loader" role="status" aria-live="polite">
  <div class="pot-wrap">
    <span class="steam s1"></span>
    <span class="steam s2"></span>
    <span class="steam s3"></span>
    <span class="pot"><CookingPot size={46} strokeWidth={1.6} /></span>
  </div>
  <p>{label}</p>
</div>

<style>
  .pot-loader {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 0.9rem;
    padding: 4rem 1rem;
    color: var(--muted);
  }

  .pot-wrap {
    position: relative;
    display: grid;
    place-items: center;
    width: 86px;
    height: 72px;
  }

  .pot {
    color: var(--accent);
    animation: pot-bob 1.6s ease-in-out infinite;
  }

  .steam {
    position: absolute;
    bottom: 44px;
    width: 7px;
    height: 7px;
    border-radius: 50%;
    background: var(--text-soft);
    opacity: 0;
    animation: steam 2.2s ease-in-out infinite;
  }

  .s1 {
    left: 34px;
    animation-delay: 0s;
  }
  .s2 {
    left: 43px;
    animation-delay: 0.5s;
  }
  .s3 {
    left: 52px;
    animation-delay: 1s;
  }

  p {
    font-size: 0.88rem;
    font-weight: 500;
  }
</style>
