<script lang="ts">
  import { Monitor, Moon, Sun } from 'lucide-svelte';
  import { cycleTheme, initTheme, themeMode } from '#lib/theme';

  initTheme();
  const labels = { dark: 'Dunkel', light: 'Hell', system: 'System' } as const;
</script>

<button
  class="btn btn-icon btn-ghost"
  type="button"
  onclick={() => cycleTheme()}
  title="Design wechseln"
  aria-label={`Design: ${$themeMode === 'dark' ? 'Dunkel' : $themeMode === 'light' ? 'Hell' : 'System'}`}
>
  {#if $themeMode === 'dark'}
    <Moon size={18} />
  {:else if $themeMode === 'light'}
    <Sun size={18} />
  {:else}
    <Monitor size={18} />
  {/if}
</button>
