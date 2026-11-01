<script lang="ts">
  import { onMount } from 'svelte';
  import { ExternalLink, Sparkles, X } from 'lucide-svelte';
  import { api } from '#lib/api';
  import type { UpdateStatus } from '#lib/types';

  let status = $state<UpdateStatus | null>(null);
  let dismissedKey = $state('');
  let closed = $state(false);

  const DISMISS_PREFIX = 'kochbuch.update.dismissed.';

  function isDismissed(state: UpdateStatus): boolean {
    try {
      // Pro Update-Version (Digest) einmal wegklappen – ein neues Bild
      // meldet sich trotzdem wieder.
      return localStorage.getItem(DISMISS_PREFIX + (state.latest_digest ?? '')) === '1';
    } catch {
      return false;
    }
  }

  async function check() {
    try {
      const result = await api.get<UpdateStatus>('/system/update-status');
      status = result;
      dismissedKey = DISMISS_PREFIX + (result.latest_digest ?? '');
      closed = isDismissed(result);
    } catch {
      // Nicht angemeldet / kein Admin / alter Server: still bleiben.
      status = null;
    }
  }

  function dismiss() {
    closed = true;
    try {
      localStorage.setItem(dismissedKey, '1');
    } catch {
      // localStorage nicht verfügbar – Toast bleibt trotzdem zu.
    }
  }

  function openDokploy() {
    if (status?.dokploy_url) window.open(status.dokploy_url, '_blank', 'noopener');
  }

  onMount(() => {
    check();
    // Hintergrund-Check im Backend läuft stündlich; hier zusätzlich
    // nachziehen, damit auch ein frisch geöffneter Tab ihn sieht.
    const interval = window.setInterval(check, 60 * 60 * 1000);
    return () => window.clearInterval(interval);
  });
</script>

{#if status && status.enabled && status.update_available && !closed}
  <div class="update-toast surface" role="status">
    <div class="toast-icon"><Sparkles size={18} /></div>
    <div class="toast-body">
      <strong>Update verfügbar</strong>
      <span class="muted">
        {#if status.last_error}
          {status.last_error}
        {:else}
          Eine neue Version ist bereit (läuft: {status.current_short ?? 'unbekannt'}).
        {/if}
      </span>
    </div>
    <div class="toast-actions">
      {#if status.dokploy_url}
        <button class="btn btn-primary btn-sm" type="button" onclick={openDokploy}>
          <ExternalLink size={14} /> Zu Dokploy
        </button>
      {/if}
      <button class="btn btn-sm" type="button" onclick={dismiss} aria-label="Hinweis ausblenden">
        <X size={14} /> Später
      </button>
    </div>
  </div>
{/if}

<style>
  .update-toast {
    position: fixed;
    right: 1rem;
    bottom: 1rem;
    z-index: 60;
    display: flex;
    align-items: center;
    gap: 0.7rem;
    max-width: min(420px, calc(100vw - 2rem));
    padding: 0.75rem 0.85rem;
    box-shadow: 0 12px 32px rgb(0 0 0 / 0.35);
    animation: toast-in 0.25s ease-out;
  }

  @keyframes toast-in {
    from {
      opacity: 0;
      transform: translateY(0.6rem);
    }
    to {
      opacity: 1;
      transform: none;
    }
  }

  .toast-icon {
    flex: none;
    display: grid;
    place-items: center;
    width: 32px;
    height: 32px;
    border-radius: 10px;
    background: color-mix(in srgb, var(--accent) 20%, transparent);
    color: var(--accent);
  }

  .toast-body {
    display: flex;
    flex-direction: column;
    gap: 0.1rem;
    min-width: 0;
    font-size: 0.85rem;
  }

  .toast-body .muted {
    font-size: 0.78rem;
    overflow-wrap: anywhere;
  }

  .toast-actions {
    display: flex;
    align-items: center;
    gap: 0.35rem;
    flex: none;
    margin-left: auto;
  }

  .btn-sm {
    min-height: 34px;
    padding: 0.3rem 0.7rem;
    font-size: 0.78rem;
    white-space: nowrap;
  }

  @media (max-width: 560px) {
    .update-toast {
      left: 1rem;
      right: 1rem;
      max-width: none;
      flex-wrap: wrap;
    }

    .toast-actions {
      margin-left: 0;
      width: 100%;
      justify-content: flex-end;
    }
  }
</style>
