<script lang="ts">
  let { count = 8 }: { count?: number } = $props();
</script>

<div class="grid" aria-hidden="true">
  {#each Array(count) as _}
    <div class="skeleton-card">
      <div class="skeleton thumb"></div>
      <div class="lines">
        <div class="skeleton line w70"></div>
        <div class="skeleton line w45"></div>
        <div class="skeleton line w30 small"></div>
      </div>
    </div>
  {/each}
</div>

<style>
  .grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(215px, 1fr));
    gap: 1rem;
  }

  .skeleton-card {
    overflow: hidden;
    border-radius: 18px;
    border: 1px solid var(--border);
    background: var(--surface);
  }

  .thumb {
    aspect-ratio: 4 / 3;
  }

  .lines {
    display: flex;
    flex-direction: column;
    gap: 0.45rem;
    padding: 0.85rem;
  }

  .line {
    height: 12px;
    border-radius: 7px;
  }

  .line.small {
    height: 9px;
  }

  .w70 {
    width: 70%;
  }
  .w45 {
    width: 45%;
  }
  .w30 {
    width: 30%;
  }
</style>
