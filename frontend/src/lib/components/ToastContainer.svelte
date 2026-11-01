<script lang="ts">
  import { toasts, dismissToast } from '#lib/toast.svelte';
  import { Check, AlertTriangle, Info, X } from 'lucide-svelte';
</script>

<div class="toast-stack" aria-live="polite">
  {#each $toasts as toast (toast.id)}
    <div class="toast" class:success={toast.kind === 'success'} class:warning={toast.kind === 'warning'} class:error={toast.kind === 'error'}>
      <span class="toast-icon">
        {#if toast.kind === 'success'}<Check size={16} />{:else if toast.kind === 'warning'}<AlertTriangle size={16} />{:else if toast.kind === 'error'}<AlertTriangle size={16} />{:else}<Info size={16} />{/if}
      </span>
      <span class="toast-msg">{toast.message}</span>
      <button class="toast-close" type="button" onclick={() => dismissToast(toast.id)} aria-label="Schließen">
        <X size={14} />
      </button>
    </div>
  {/each}
</div>

<style>
  .toast-stack {
    position: fixed;
    bottom: 1.2rem;
    right: 1.2rem;
    z-index: 100;
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
    max-width: min(420px, 90vw);
  }
  .toast {
    display: flex;
    align-items: center;
    gap: 0.6rem;
    padding: 0.7rem 0.85rem;
    border-radius: 12px;
    border: 1px solid var(--border);
    background: var(--surface);
    box-shadow: var(--shadow);
    color: var(--text);
    font-size: 0.88rem;
  }
  .toast.info { border-color: color-mix(in srgb, var(--accent) 30%, var(--border)); }
  .toast.warning { border-color: color-mix(in srgb, #e8a317 45%, var(--border)); color: #c58a0a; background: color-mix(in srgb, #e8a317 8%, var(--surface)); }
  .toast.success { border-color: color-mix(in srgb, var(--success) 45%, var(--border)); }
  .toast.error { border-color: color-mix(in srgb, var(--danger) 45%, var(--border)); color: var(--danger); }
  .toast-icon { flex: none; }
  .toast-msg { flex: 1; }
  .toast-close { border: 0; background: transparent; color: var(--muted); cursor: pointer; }
</style>