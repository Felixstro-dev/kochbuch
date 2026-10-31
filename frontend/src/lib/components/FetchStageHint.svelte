<script lang="ts">
  import { onMount } from 'svelte';

  let { active }: { active: boolean } = $props();

  const stages = [
    { after: 0, label: 'Seite wird geladen …' },
    { after: 2500, label: 'Zweiter Versuch mit anderer Signatur …' },
    { after: 6000, label: 'Schutzabfrage wird umgangen …' },
    { after: 14000, label: 'Das dauert länger als üblich – bitte dranbleiben …' }
  ];

  let elapsed = $state(0);

  onMount(() => {
    const started = Date.now();
    const timer = setInterval(() => {
      elapsed = Date.now() - started;
    }, 500);
    return () => clearInterval(timer);
  });

  const label = $derived(
    [...stages].reverse().find((stage) => elapsed >= stage.after)?.label ?? stages[0].label
  );
</script>

{#if active}
  <p class="fetch-stage" role="status" aria-live="polite">
    <span class="dot" aria-hidden="true"></span>
    {label}
  </p>
{/if}

<style>
  .fetch-stage {
    display: inline-flex;
    align-items: center;
    gap: 0.45rem;
    font-size: 0.8rem;
    color: var(--text-soft);
  }

  .dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: var(--accent);
    animation: pulse 1.4s ease-in-out infinite;
  }

  @keyframes pulse {
    0%,
    100% {
      opacity: 0.35;
      transform: scale(0.85);
    }
    50% {
      opacity: 1;
      transform: scale(1);
    }
  }

  @media (prefers-reduced-motion: reduce) {
    .dot {
      animation: none;
      opacity: 1;
    }
  }
</style>
