<script lang="ts">
  import {
    AlertTriangle,
    Check,
    Globe2,
    LoaderCircle,
    Network,
    Palette,
    PlugZap,
    RefreshCw,
    Save,
    Settings2,
    ShieldCheck,
    Trash2
  } from 'lucide-svelte';
  import { api, ApiError } from '#lib/api';
  import type { AppSettings, FetchStatus, FetchTestResult } from '#lib/types';

  let { data }: {
    data: {
      settings: AppSettings | null;
      status: FetchStatus | null;
      isAdmin: boolean;
      error?: string;
    };
  } = $props();

  // svelte-ignore state_referenced_locally
  const settings = data.settings;
  // svelte-ignore state_referenced_locally
  const isAdmin = data.isAdmin;

  let appName = $state(settings?.app_name ?? 'Kochbuch');
  let theme = $state(settings?.default_theme ?? 'dark');
  let accent = $state(settings?.accent_color ?? '#e6a15c');
  let providers = $state<string[]>(settings?.enabled_providers ?? []);

  let proxyUrl = $state('');
  let proxyForImages = $state(settings?.fetch.proxy_for_images ?? true);
  let flareUrl = $state(settings?.fetch.flaresolverr_url ?? '');
  let flareTimeout = $state(settings?.fetch.flaresolverr_timeout ?? 60);
  let maxRetries = $state(settings?.fetch.max_retries ?? 3);
  let fetchTimeout = $state(settings?.fetch.timeout ?? 15);
  let impersonation = $state(settings?.fetch.browser_impersonation ?? true);

  // svelte-ignore state_referenced_locally
  let fetchStatus = $state<FetchStatus | null>(data.status);
  let saving = $state(false);
  let message = $state('');
  let error = $state('');
  let testing = $state<string | null>(null);
  let checkingUpdate = $state(false);
  let updateMessage = $state('');
  let testResults = $state<Record<string, FetchTestResult>>({});

  const accents = ['#e6a15c', '#d97757', '#7fb685', '#6f9fce', '#b48ead', '#d8b45a'];
  const providerOptions = [
    { name: 'chefkoch', label: 'Chefkoch', hint: 'Suche und Rezepte über die Chefkoch-API' },
    { name: 'web', label: 'Web / URL-Import', hint: 'recipe-scrapers und JSON-LD für beliebige Seiten' },
    { name: 'local', label: 'Eigene Rezepte', hint: 'Lokal gespeicherte Rezepte' }
  ];

  const proxyConfigured = $derived(fetchStatus?.proxy_configured ?? false);
  const flareConfigured = $derived(fetchStatus?.flaresolverr_configured ?? false);

  function toggleProvider(name: string) {
    providers = providers.includes(name)
      ? providers.filter((item) => item !== name)
      : [...providers, name];
  }

  function pickAccent(color: string) {
    accent = color;
    if (typeof document !== 'undefined') {
      document.documentElement.style.setProperty('--accent', color);
    }
  }

  function applySettings(next: AppSettings) {
    fetchStatus = {
      ...(fetchStatus ?? ({} as FetchStatus)),
      ...next.fetch,
      min_interval: fetchStatus?.min_interval ?? 0,
      totals: fetchStatus?.totals ?? {
        requests: 0,
        successes: 0,
        failures: 0,
        blocked: 0,
        by_tier: {}
      },
      active: fetchStatus?.active ?? [],
      domains: fetchStatus?.domains ?? []
    };
    proxyUrl = '';
    proxyForImages = next.fetch.proxy_for_images;
    flareUrl = next.fetch.flaresolverr_url ?? '';
    flareTimeout = next.fetch.flaresolverr_timeout;
    maxRetries = next.fetch.max_retries;
    fetchTimeout = next.fetch.timeout;
    impersonation = next.fetch.browser_impersonation;
  }

  async function save() {
    if (saving || !isAdmin) return;
    saving = true;
    message = '';
    error = '';
    const payload: Record<string, unknown> = {
      app_name: appName.trim(),
      default_theme: theme,
      accent_color: accent,
      enabled_providers: providers,
      fetch: {
        proxy_for_images: proxyForImages,
        flaresolverr_url: flareUrl.trim(),
        flaresolverr_timeout: Number(flareTimeout),
        max_retries: Number(maxRetries),
        timeout: Number(fetchTimeout),
        browser_impersonation: impersonation
      }
    };
    if (proxyUrl.trim()) {
      (payload.fetch as Record<string, unknown>).proxy_url = proxyUrl.trim();
    }
    try {
      const next = await api.patch<AppSettings>('/settings', payload);
      applySettings(next);
      message = 'Einstellungen gespeichert.';
      await refreshStatus();
    } catch (cause) {
      error =
        cause instanceof ApiError ? cause.message : 'Speichern fehlgeschlagen. Bitte erneut versuchen.';
    } finally {
      saving = false;
    }
  }

  async function clearProxy() {
    if (!isAdmin || saving) return;
    saving = true;
    error = '';
    message = '';
    try {
      const next = await api.patch<AppSettings>('/settings', { fetch: { proxy_url: '' } });
      applySettings(next);
      message = 'Proxy entfernt.';
      await refreshStatus();
    } catch (cause) {
      error = cause instanceof ApiError ? cause.message : 'Proxy konnte nicht entfernt werden.';
    } finally {
      saving = false;
    }
  }

  async function refreshStatus() {
    if (!isAdmin) return;
    try {
      fetchStatus = await api.get<FetchStatus>('/system/fetch-status');
    } catch {
      // Keep the previous snapshot.
    }
  }

  async function test(target: 'direct' | 'proxy' | 'flaresolverr') {
    if (testing || !isAdmin) return;
    testing = target;
    try {
      testResults = {
        ...testResults,
        [target]: await api.post<FetchTestResult>('/system/fetch/test', { target })
      };
    } catch (cause) {
      testResults = {
        ...testResults,
        [target]: {
          ok: false,
          target,
          detail: cause instanceof ApiError ? cause.message : 'Test fehlgeschlagen.',
          status: null,
          tier: null,
          elapsed_ms: null
        }
      };
    } finally {
      testing = null;
    }
  async function checkForUpdates() {
    if (checkingUpdate || !isAdmin) return;
    checkingUpdate = true;
    updateMessage = '';
    try {
      const result = await api.post<{ available?: boolean; dokploy_url?: string }>('/system/update-check');
      updateMessage = result?.available
        ? 'Update verfügbar – im Dokploy bereitstellen.'
        : 'Kein Update verfügbar. Du bist auf dem neuesten Stand.';
    } catch (cause) {
      updateMessage = cause instanceof ApiError ? cause.message : 'Update-Prüfung fehlgeschlagen.';
    } finally {
      checkingUpdate = false;
    }
  }
  }
</script>

<svelte:head>
  <title>Einstellungen · Kochbuch</title>
</svelte:head>

<section class="head">
  <span class="eyebrow"><Settings2 size={14} /> Haushalt & Technik</span>
  <h1>Einstellungen</h1>
  <p class="muted">
    {isAdmin
      ? 'Aussehen, Quellen und der robuste Abruf für blockierende Seiten.'
      : 'Diese Übersicht ist nur lesbar – Änderungen sind Administratoren vorbehalten.'}
  </p>
</section>

{#if data.error}
  <div class="state surface">
    <h2>Nicht erreichbar</h2>
    <p>{data.error}</p>
  </div>
{:else if settings}
  <div class="layout">
    <section class="card surface">
      <header class="card-head">
        <span class="icon"><Palette size={18} /></span>
        <div>
          <h2>Darstellung</h2>
          <p class="muted">Gilt als Standard für neue Geräte und den Haushalt.</p>
        </div>
      </header>

      <div class="fields">
        <label class="label">
          <span>Name der App</span>
          <input class="field" bind:value={appName} disabled={!isAdmin} maxlength="60" />
        </label>

        <label class="label">
          <span>Standard-Theme</span>
          <select class="field" bind:value={theme} disabled={!isAdmin}>
            <option value="dark">Dunkel</option>
            <option value="light">Hell</option>
            <option value="system">System folgen</option>
          </select>
        </label>

        <div class="label">
          <span>Akzentfarbe</span>
          <div class="accents">
            {#each accents as color}
              <button
                class="swatch"
                class:active={accent.toLowerCase() === color}
                style:background={color}
                type="button"
                disabled={!isAdmin}
                onclick={() => pickAccent(color)}
                aria-label={`Akzentfarbe ${color}`}
              >
                {#if accent.toLowerCase() === color}<Check size={14} />{/if}
              </button>
            {/each}
            <input
              class="field color-field"
              type="color"
              bind:value={accent}
              disabled={!isAdmin}
              aria-label="Eigene Akzentfarbe"
            />
          </div>
        </div>
      </div>
    </section>

    <section class="card surface">
      <header class="card-head">
        <span class="icon"><Globe2 size={18} /></span>
        <div>
          <h2>Quellen</h2>
          <p class="muted">Die Suche fragt alle aktiven Quellen parallel ab.</p>
        </div>
      </header>

      <div class="providers">
        {#each providerOptions as provider}
          <button
            class="provider"
            class:active={providers.includes(provider.name)}
            type="button"
            disabled={!isAdmin}
            onclick={() => toggleProvider(provider.name)}
            aria-pressed={providers.includes(provider.name)}
          >
            <span class="provider-check">
              {#if providers.includes(provider.name)}<Check size={13} />{/if}
            </span>
            <span class="provider-copy">
              <strong>{provider.label}</strong>
              <small>{provider.hint}</small>
            </span>
          </button>
        {/each}
      </div>
    </section>

    <section class="card surface fetch-card">
      <header class="card-head">
        <span class="icon"><Network size={18} /></span>
        <div>
          <h2>Robuster Abruf</h2>
          <p class="muted">
            Erst direkt, dann über Proxy, zuletzt per FlareSolverr – nur so weit wie nötig.
          </p>
        </div>
        <div class="badges">
          <span class="chip" class:on={proxyConfigured}>
            Proxy {proxyConfigured ? 'aktiv' : 'aus'}
          </span>
          <span class="chip" class:on={flareConfigured}>
            FlareSolverr {flareConfigured ? 'aktiv' : 'aus'}
          </span>
          {#if fetchStatus?.curl_cffi}
            <span class="chip on">curl_cffi</span>
          {/if}
        </div>
      </header>

      <div class="fields">
        <label class="label wide">
          <span>
            Proxy-URL
            {#if proxyConfigured}<small class="ok">konfiguriert: {fetchStatus?.proxy_host}</small>{/if}
          </span>
          <input
            class="field"
            bind:value={proxyUrl}
            disabled={!isAdmin}
            placeholder={proxyConfigured ? 'leer lassen, um Proxy zu behalten' : 'socks5://user:pass@host:1080'}
            autocomplete="off"
            spellcheck="false"
          />
          <small class="hint">HTTP, HTTPS, SOCKS4 oder SOCKS5. Zugangsdaten werden nie zurückgegeben.</small>
        </label>

        <label class="check">
          <input type="checkbox" bind:checked={proxyForImages} disabled={!isAdmin} />
          <span>Proxy auch für Bilder verwenden</span>
        </label>

        <label class="label wide">
          <span>FlareSolverr-URL</span>
          <input
            class="field"
            bind:value={flareUrl}
            disabled={!isAdmin}
            placeholder="http://flaresolverr:8191"
            autocomplete="off"
            spellcheck="false"
          />
          <small class="hint">Nur für HTML-Seiten mit Schutzabfrage – die Chefkoch-API bleibt direkt.</small>
        </label>

        <div class="row">
          <label class="label">
            <span>FlareSolverr-Timeout (s)</span>
            <input class="field" type="number" min="5" max="300" bind:value={flareTimeout} disabled={!isAdmin} />
          </label>
          <label class="label">
            <span>Versuche pro Stufe</span>
            <input class="field" type="number" min="1" max="8" bind:value={maxRetries} disabled={!isAdmin} />
          </label>
          <label class="label">
            <span>Request-Timeout (s)</span>
            <input class="field" type="number" min="3" max="120" bind:value={fetchTimeout} disabled={!isAdmin} />
          </label>
        </div>

        <label class="check">
          <input type="checkbox" bind:checked={impersonation} disabled={!isAdmin} />
          <span>Browser-Fingerprint-Imitation, wenn curl_cffi installiert ist</span>
        </label>
      </div>

      <div class="tests">
        <span class="tests-label"><PlugZap size={14} /> Verbindung testen</span>
        <div class="test-buttons">
          <button class="btn btn-ghost" type="button" onclick={() => test('direct')} disabled={!isAdmin || testing !== null}>
            {#if testing === 'direct'}<LoaderCircle class="spin" size={15} />{:else}<Globe2 size={15} />{/if}
            Direkt
          </button>
          <button
            class="btn btn-ghost"
            type="button"
            onclick={() => test('proxy')}
            disabled={!isAdmin || testing !== null || !proxyConfigured}
          >
            {#if testing === 'proxy'}<LoaderCircle class="spin" size={15} />{:else}<Network size={15} />{/if}
            Proxy
          </button>
          <button
            class="btn btn-ghost"
            type="button"
            onclick={() => test('flaresolverr')}
            disabled={!isAdmin || testing !== null || !flareConfigured}
          >
            {#if testing === 'flaresolverr'}<LoaderCircle class="spin" size={15} />{:else}<ShieldCheck size={15} />{/if}
            FlareSolverr
          </button>
          {#if proxyConfigured}
            <button class="btn btn-ghost danger" type="button" onclick={clearProxy} disabled={!isAdmin || saving}>
              <Trash2 size={15} /> Proxy entfernen
            </button>
          {/if}
        </div>

        <div class="test-results">
          {#each Object.entries(testResults) as [target, result]}
            <p class:ok={result.ok} class:fail={!result.ok} class="test-result">
              {#if result.ok}<Check size={14} />{:else}<AlertTriangle size={14} />{/if}
              <strong>{target}</strong> – {result.detail}
              {#if result.elapsed_ms !== null}<span class="muted">({result.elapsed_ms} ms)</span>{/if}
            </p>
          {/each}
        </div>
      </div>

      <div class="stats">
        <div class="stats-head">
          <h3>Abruf-Statistik</h3>
          <button class="btn btn-ghost btn-icon" type="button" onclick={refreshStatus} disabled={!isAdmin} aria-label="Statistik aktualisieren">
            <RefreshCw size={15} />
          </button>
        </div>
        {#if fetchStatus}
          <div class="totals">
            <span><strong>{fetchStatus.totals.successes ?? 0}</strong> erfolgreich</span>
            <span><strong>{fetchStatus.totals.failures ?? 0}</strong> fehlgeschlagen</span>
            <span><strong>{fetchStatus.totals.blocked ?? 0}</strong> pausiert</span>
            <span>via Proxy <strong>{fetchStatus.totals.by_tier?.proxy ?? 0}</strong></span>
            <span>via FlareSolverr <strong>{fetchStatus.totals.by_tier?.flaresolverr ?? 0}</strong></span>
          </div>
          {#if fetchStatus.domains.length}
            <div class="domain-table">
              <div class="domain-row domain-head">
                <span>Domain</span><span>OK</span><span>Fehler</span><span>Letzte Stufe</span>
              </div>
              {#each fetchStatus.domains.slice(0, 12) as domain}
                <div class="domain-row">
                  <span class="domain-name">{domain.domain}</span>
                  <span>{domain.successes}</span>
                  <span>{domain.failures}</span>
                  <span class="muted">
                    {domain.rate_limited
                      ? 'pausiert'
                      : domain.last_tier === 'flaresolverr'
                        ? 'FlareSolverr'
                        : domain.last_tier === 'proxy'
                          ? 'Proxy'
                          : domain.last_tier === 'direct'
                            ? 'direkt'
                            : '–'}
                  </span>
                </div>
              {/each}
            </div>
          {:else}
            <p class="muted empty">Noch keine Abrufe seit dem Start.</p>
          {/if}
        {:else}
          <p class="muted empty">Statistik ist nur für Administratoren sichtbar.</p>
        {/if}
      </div>
    </section>
    <section class="card surface">
      <header class="card-head">
        <span class="icon"><RefreshCw size={18} /></span>
        <div>
          <h2>Updates</h2>
          <p class="muted">Prüft, ob eine neuere Version verfügbar ist.</p>
        </div>
      </header>
      <div class="fields">
        <button class="btn btn-ghost" type="button" onclick={checkForUpdates} disabled={!isAdmin || checkingUpdate}>
          {#if checkingUpdate}<LoaderCircle class="spin" size={15} />{:else}<RefreshCw size={15} />{/if}
          Auf Updates prüfen
        </button>
        {#if updateMessage}<p class="muted">{updateMessage}</p>{/if}
      </div>
    </section>
  </div>

  {#if isAdmin}
    <div class="savebar">
      <div class="save-status">
        {#if error}<p class="error" role="alert"><AlertTriangle size={15} /> {error}</p>{/if}
        {#if message}<p class="success" role="status"><Check size={15} /> {message}</p>{/if}
      </div>
      <button class="btn btn-primary" type="button" onclick={save} disabled={saving}>
        {#if saving}<LoaderCircle class="spin" size={17} />{:else}<Save size={17} />{/if}
        Speichern
      </button>
    </div>
  {/if}
{/if}

<style>
  .head {
    padding: 0.5rem 0 1.3rem;
  }

  .eyebrow {
    display: inline-flex;
    align-items: center;
    gap: 0.35rem;
    font-size: 0.72rem;
    font-weight: 700;
    letter-spacing: 0.09em;
    text-transform: uppercase;
    color: var(--accent);
    margin-bottom: 0.5rem;
  }

  h1 {
    font-size: clamp(1.9rem, 4vw, 2.8rem);
  }

  .head p {
    margin-top: 0.4rem;
    font-size: 0.9rem;
    max-width: 70ch;
  }

  .layout {
    display: flex;
    flex-direction: column;
    gap: 1rem;
    padding-bottom: 6rem;
  }

  .card {
    padding: 1.1rem 1.2rem;
  }

  .card-head {
    display: flex;
    align-items: flex-start;
    gap: 0.75rem;
    margin-bottom: 1rem;
  }

  .card-head h2 {
    font-size: 1.1rem;
  }

  .card-head p {
    font-size: 0.82rem;
    margin-top: 0.15rem;
    max-width: 62ch;
  }

  .icon {
    display: grid;
    place-items: center;
    width: 38px;
    height: 38px;
    flex: none;
    border-radius: 12px;
    background: color-mix(in srgb, var(--accent) 14%, var(--surface-2));
    color: var(--accent);
  }

  .badges {
    display: flex;
    flex-wrap: wrap;
    gap: 0.3rem;
    margin-left: auto;
  }

  .badges .chip.on {
    border-color: color-mix(in srgb, var(--success) 45%, var(--border));
    color: var(--success);
    background: color-mix(in srgb, var(--success) 10%, transparent);
  }

  .fields {
    display: flex;
    flex-direction: column;
    gap: 0.9rem;
  }

  .label {
    display: flex;
    flex-direction: column;
    gap: 0.35rem;
    font-size: 0.8rem;
    font-weight: 600;
    color: var(--text-soft);
  }

  .label small {
    font-weight: 500;
    font-size: 0.72rem;
    color: var(--muted);
  }

  .label small.ok {
    color: var(--success);
  }

  .hint {
    color: var(--muted);
    font-size: 0.72rem;
    font-weight: 400;
    line-height: 1.4;
  }

  .row {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
    gap: 0.8rem;
  }

  .check {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    font-size: 0.82rem;
    color: var(--text-soft);
    cursor: pointer;
  }

  .check input {
    width: 16px;
    height: 16px;
    accent-color: var(--accent);
  }

  .accents {
    display: flex;
    align-items: center;
    gap: 0.4rem;
    flex-wrap: wrap;
  }

  .swatch {
    display: grid;
    place-items: center;
    width: 32px;
    height: 32px;
    border-radius: 50%;
    border: 2px solid transparent;
    color: #1a1208;
    transition:
      transform 150ms ease,
      border-color 150ms ease;
  }

  .swatch:hover {
    transform: scale(1.07);
  }

  .swatch.active {
    border-color: var(--text);
  }

  .color-field {
    width: 48px;
    height: 32px;
    min-height: 32px;
    padding: 0.15rem;
  }

  .providers {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
    gap: 0.5rem;
  }

  .provider {
    display: flex;
    align-items: flex-start;
    gap: 0.6rem;
    padding: 0.7rem 0.8rem;
    border-radius: 14px;
    border: 1px solid var(--border);
    background: var(--bg-elevated);
    text-align: left;
    transition:
      border-color 150ms ease,
      background 150ms ease;
  }

  .provider:hover {
    border-color: var(--border-strong);
  }

  .provider.active {
    border-color: color-mix(in srgb, var(--accent) 55%, var(--border));
    background: color-mix(in srgb, var(--accent) 8%, var(--bg-elevated));
  }

  .provider-check {
    display: grid;
    place-items: center;
    width: 20px;
    height: 20px;
    flex: none;
    margin-top: 0.1rem;
    border-radius: 6px;
    border: 1.5px solid var(--border-strong);
    color: transparent;
  }

  .provider.active .provider-check {
    background: var(--accent);
    border-color: var(--accent);
    color: var(--accent-contrast);
  }

  .provider-copy {
    display: flex;
    flex-direction: column;
    gap: 0.15rem;
    min-width: 0;
  }

  .provider-copy strong {
    font-size: 0.85rem;
  }

  .provider-copy small {
    font-size: 0.72rem;
    color: var(--muted);
    line-height: 1.35;
  }

  .fetch-card {
    display: flex;
    flex-direction: column;
    gap: 0.4rem;
  }

  .tests {
    display: flex;
    flex-direction: column;
    gap: 0.6rem;
    padding-top: 1rem;
    margin-top: 0.4rem;
    border-top: 1px solid var(--border);
  }

  .tests-label {
    display: inline-flex;
    align-items: center;
    gap: 0.35rem;
    font-size: 0.75rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: var(--muted);
  }

  .test-buttons {
    display: flex;
    flex-wrap: wrap;
    gap: 0.4rem;
  }

  .btn.danger {
    color: var(--danger);
  }

  .test-results {
    display: flex;
    flex-direction: column;
    gap: 0.3rem;
  }

  .test-result {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 0.35rem;
    font-size: 0.79rem;
  }

  .test-result.ok {
    color: var(--success);
  }

  .test-result.fail {
    color: var(--danger);
  }

  .stats {
    margin-top: 1rem;
    padding-top: 1rem;
    border-top: 1px solid var(--border);
  }

  .stats-head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 0.5rem;
  }

  .stats-head h3 {
    font-size: 0.82rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: var(--muted);
  }

  .totals {
    display: flex;
    flex-wrap: wrap;
    gap: 0.4rem 1.1rem;
    margin: 0.6rem 0 0.8rem;
    font-size: 0.78rem;
    color: var(--muted);
  }

  .totals strong {
    color: var(--text);
  }

  .domain-table {
    display: flex;
    flex-direction: column;
    gap: 1px;
    overflow: hidden;
    border-radius: 10px;
    border: 1px solid var(--border);
  }

  .domain-row {
    display: grid;
    grid-template-columns: 1fr 48px 60px 110px;
    gap: 0.5rem;
    padding: 0.42rem 0.6rem;
    font-size: 0.76rem;
    background: var(--bg-elevated);
  }

  .domain-head {
    background: var(--surface-2);
    font-weight: 700;
    color: var(--muted);
    font-size: 0.7rem;
    text-transform: uppercase;
    letter-spacing: 0.04em;
  }

  .domain-name {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .empty {
    font-size: 0.8rem;
    padding: 0.4rem 0;
  }

  .savebar {
    position: fixed;
    left: 0;
    right: 0;
    bottom: 0;
    z-index: 20;
    display: flex;
    align-items: center;
    justify-content: flex-end;
    gap: 1rem;
    padding: 0.7rem clamp(1rem, 4vw, 2.4rem);
    border-top: 1px solid var(--border);
    background: color-mix(in srgb, var(--bg) 88%, transparent);
    backdrop-filter: blur(16px);
  }

  .save-status {
    margin-right: auto;
  }

  .save-status .error,
  .save-status .success {
    display: inline-flex;
    align-items: center;
    gap: 0.35rem;
    font-size: 0.82rem;
  }

  .save-status .error {
    color: var(--danger);
  }

  .save-status .success {
    color: var(--success);
  }

  :global(.spin) {
    animation: spin 900ms linear infinite;
  }

  @keyframes spin {
    to {
      transform: rotate(360deg);
    }
  }

  @media (max-width: 760px) {
    .badges {
      margin-left: 0;
      width: 100%;
      padding-left: 3.3rem;
    }

    .domain-row {
      grid-template-columns: 1fr 40px 50px 90px;
    }

    .savebar {
      padding-bottom: calc(0.7rem + env(safe-area-inset-bottom));
    }
  }
</style>
