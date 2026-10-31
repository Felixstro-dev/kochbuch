<script lang="ts">
  import { goto, invalidateAll } from '$app/navigation';
  import { ChefHat, LoaderCircle, ShieldCheck } from 'lucide-svelte';
  import { api, ApiError } from '#lib/api';
  import ThemeToggle from '#lib/components/ThemeToggle.svelte';
  import type { AuthResponse, AuthStatus } from '#lib/types';

  let { data }: { data: { status: AuthStatus } } = $props();

  let username = $state('');
  let displayName = $state('');
  let password = $state('');
  let confirm = $state('');
  let error = $state('');
  let busy = $state(false);

  async function submit(event: SubmitEvent) {
    event.preventDefault();
    if (busy) return;
    error = '';
    if (password !== confirm) {
      error = 'Die Passwörter stimmen nicht überein.';
      return;
    }
    if (password.length < 10) {
      error = 'Das Passwort muss mindestens 10 Zeichen lang sein.';
      return;
    }
    busy = true;
    try {
      await api.post<AuthResponse>('/auth/setup', {
        username: username.trim(),
        display_name: displayName.trim() || undefined,
        password
      });
      await invalidateAll();
      await goto('/', { replace: true });
    } catch (cause) {
      error =
        cause instanceof ApiError
          ? cause.message
          : 'Die Einrichtung ist fehlgeschlagen. Bitte erneut versuchen.';
    } finally {
      busy = false;
    }
  }
</script>

<svelte:head>
  <title>Einrichten · {data.status.app_name}</title>
</svelte:head>

<div class="auth-wrap">
  <div class="auth-top">
    <ThemeToggle />
  </div>

  <div class="auth-card fade-up">
    <div class="brand">
      <span class="brand-mark"><ChefHat size={26} strokeWidth={2.1} /></span>
      <div>
        <h1>{data.status.app_name} einrichten</h1>
        <p class="muted">Lege das erste Konto an – es wird Administrator.</p>
      </div>
    </div>

    <form onsubmit={submit} class="form">
      <div class="row">
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
            minlength="2"
            placeholder="felix"
          />
        </label>
        <label class="label">
          <span>Anzeigename <small>(optional)</small></span>
          <input
            class="field"
            bind:value={displayName}
            type="text"
            autocomplete="name"
            placeholder="Felix"
          />
        </label>
      </div>

      <label class="label">
        <span>Passwort</span>
        <input
          class="field"
          bind:value={password}
          type="password"
          autocomplete="new-password"
          required
          minlength="10"
          placeholder="mindestens 10 Zeichen"
        />
      </label>

      <label class="label">
        <span>Passwort wiederholen</span>
        <input
          class="field"
          bind:value={confirm}
          type="password"
          autocomplete="new-password"
          required
          placeholder="••••••••••"
        />
      </label>

      {#if error}
        <p class="error" role="alert">{error}</p>
      {/if}

      <button class="btn btn-primary submit" type="submit" disabled={busy}>
        {#if busy}
          <LoaderCircle class="spin" size={18} /> Wird eingerichtet …
        {:else}
          <ShieldCheck size={18} /> Kochbuch starten
        {/if}
      </button>
    </form>

    <p class="hint">
      Weitere Konten für deinen Haushalt legst du später in den Einstellungen an.
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
    width: min(480px, 100%);
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
    flex: none;
    border-radius: 16px;
    background: var(--accent);
    color: var(--accent-contrast);
    box-shadow: 0 12px 30px color-mix(in srgb, var(--accent) 28%, transparent);
  }

  h1 {
    font-size: 1.35rem;
  }

  .brand p {
    font-size: 0.8rem;
    margin-top: 0.2rem;
  }

  .form {
    display: flex;
    flex-direction: column;
    gap: 1rem;
  }

  .row {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 0.8rem;
  }

  @media (max-width: 460px) {
    .row {
      grid-template-columns: 1fr;
    }
  }

  .label {
    display: flex;
    flex-direction: column;
    gap: 0.4rem;
    font-size: 0.8rem;
    font-weight: 600;
    color: var(--text-soft);
  }

  .label small {
    color: var(--muted);
    font-weight: 500;
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
