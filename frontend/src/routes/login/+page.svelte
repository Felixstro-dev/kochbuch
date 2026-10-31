<script lang="ts">
  import { goto, invalidateAll } from '$app/navigation';
  import { page } from '$app/state';
  import { ChefHat, LoaderCircle, LogIn } from 'lucide-svelte';
  import { api, ApiError } from '#lib/api';
  import ThemeToggle from '#lib/components/ThemeToggle.svelte';
  import type { AuthResponse, AuthStatus } from '#lib/types';

  let { data }: { data: { status: AuthStatus } } = $props();

  let username = $state('');
  let password = $state('');
  let error = $state('');
  let busy = $state(false);

  const next = $derived(page.url.searchParams.get('next') || '/');

  async function submit(event: SubmitEvent) {
    event.preventDefault();
    if (busy) return;
    error = '';
    busy = true;
    try {
      await api.post<AuthResponse>('/auth/login', {
        username: username.trim(),
        password
      });
      await invalidateAll();
      await goto(next, { replace: true });
    } catch (cause) {
      error =
        cause instanceof ApiError
          ? cause.message
          : 'Anmeldung fehlgeschlagen. Bitte später erneut versuchen.';
    } finally {
      busy = false;
    }
  }
</script>

<svelte:head>
  <title>Anmelden · {data.status.app_name}</title>
</svelte:head>

<div class="auth-wrap">
  <div class="auth-top">
    <ThemeToggle />
  </div>

  <div class="auth-card fade-up">
    <div class="brand">
      <span class="brand-mark"><ChefHat size={26} strokeWidth={2.1} /></span>
      <div>
        <h1>{data.status.app_name}</h1>
        <p class="muted">Rezepte finden, kochen, genießen.</p>
      </div>
    </div>

    <form onsubmit={submit} class="form">
      <label class="label">
        <span>Benutzername</span>
        <input
          class="field"
          bind:value={username}
          type="text"
          autocomplete="username"
          autocapitalize="none"
          spellcheck="false"
          required
          placeholder="z. B. felix"
        />
      </label>

      <label class="label">
        <span>Passwort</span>
        <input
          class="field"
          bind:value={password}
          type="password"
          autocomplete="current-password"
          required
          placeholder="••••••••••"
        />
      </label>

      {#if error}
        <p class="error" role="alert">{error}</p>
      {/if}

      <button class="btn btn-primary submit" type="submit" disabled={busy}>
        {#if busy}
          <LoaderCircle class="spin" size={18} /> Anmelden …
        {:else}
          <LogIn size={18} /> Anmelden
        {/if}
      </button>
    </form>

    <p class="hint">
      Kein Konto? Ein Administrator kann dir eines in den Einstellungen anlegen.
    </p>
  </div>
</div>

<style>
  .auth-wrap {
    position: relative;
    display: grid;
    place-items: center;
    min-height: 100dvh;
    padding: 2rem 1.2rem;
  }

  .auth-top {
    position: absolute;
    top: 1rem;
    right: 1rem;
  }

  .auth-card {
    width: min(420px, 100%);
    padding: clamp(1.5rem, 4vw, 2.2rem);
    border-radius: 24px;
    border: 1px solid var(--border);
    background: color-mix(in srgb, var(--surface) 92%, transparent);
    box-shadow: var(--shadow);
    backdrop-filter: blur(20px);
  }

  .brand {
    display: flex;
    align-items: center;
    gap: 0.9rem;
    margin-bottom: 1.7rem;
  }

  .brand-mark {
    display: grid;
    place-items: center;
    width: 52px;
    height: 52px;
    border-radius: 16px;
    background: var(--accent);
    color: var(--accent-contrast);
    box-shadow: 0 12px 30px color-mix(in srgb, var(--accent) 28%, transparent);
  }

  h1 {
    font-size: 1.55rem;
  }

  .brand p {
    font-size: 0.82rem;
  }

  .form {
    display: flex;
    flex-direction: column;
    gap: 1rem;
  }

  .label {
    display: flex;
    flex-direction: column;
    gap: 0.4rem;
    font-size: 0.8rem;
    font-weight: 600;
    color: var(--text-soft);
  }

  .submit {
    margin-top: 0.3rem;
    min-height: 50px;
  }

  .error {
    padding: 0.65rem 0.8rem;
    border-radius: 12px;
    border: 1px solid color-mix(in srgb, var(--danger) 40%, var(--border));
    background: color-mix(in srgb, var(--danger) 12%, transparent);
    color: var(--danger);
    font-size: 0.82rem;
  }

  .hint {
    margin-top: 1.3rem;
    text-align: center;
    font-size: 0.78rem;
    color: var(--muted);
    line-height: 1.5;
  }

  :global(.spin) {
    animation: spin 900ms linear infinite;
  }

  @keyframes spin {
    to {
      transform: rotate(360deg);
    }
  }
</style>
