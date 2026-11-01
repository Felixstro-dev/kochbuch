<script lang="ts">
  import '../app.css';
  import { page } from '$app/state';
  import { goto, invalidateAll } from '$app/navigation';
  import {
    ChefHat,
    Heart,
    LogOut,
    Menu,
    Search,
    Settings,
    Sparkles,
    X
  } from 'lucide-svelte';
  import { onMount } from 'svelte';
  import { showToast } from '#lib/toast.svelte';
  import type { Snippet } from 'svelte';
  import { api } from '#lib/api';
  import { applyTheme, initTheme } from '#lib/theme';
  import ThemeToggle from '#lib/components/ThemeToggle.svelte';
  import UpdateToast from '#lib/components/UpdateToast.svelte';
  import ToastContainer from '#lib/components/ToastContainer.svelte';
  import type { AuthStatus } from '#lib/types';

  let { data, children }: { data: { status: AuthStatus; embed: boolean; path: string }; children: Snippet } = $props();
  let searchQuery = $state('');
  let menuOpen = $state(false);
  let searchInput = $state<HTMLInputElement | null>(null);

  const status = $derived(data.status);
  const user = $derived(status.user);
  const embed = $derived(data.embed);
  const isAuthPage = $derived(data.path === '/login' || data.path === '/setup');
  const nav = [
    { href: '/', label: 'Suche', icon: Search },
    { href: '/favorites', label: 'Favoriten', icon: Heart },
    { href: '/wishes', label: 'Wünsche', icon: Sparkles },
    { href: '/settings', label: 'Einstellungen', icon: Settings }
  ];

  onMount(() => {
    initTheme();
    const themeParam = page.url.searchParams.get('theme');
    if (themeParam === 'dark' || themeParam === 'light') {
      applyTheme(themeParam);
    }
    const onKey = (event: KeyboardEvent) => {
      const target = event.target as HTMLElement | null;
      const typing =
        target?.tagName === 'INPUT' ||
        target?.tagName === 'TEXTAREA' ||
        target?.tagName === 'SELECT' ||
        target?.isContentEditable;
      if (event.key === '/' && !typing && !isAuthPage && !embed) {
        event.preventDefault();
        searchInput?.focus();
      }
    };
    const onMessage = (event: MessageEvent) => {
      const value = event.data?.theme;
      if (value === 'dark' || value === 'light' || value === 'system') applyTheme(value);
    };
    window.addEventListener('keydown', onKey);
    window.addEventListener('message', onMessage);
    window.addEventListener('error', (e) => {
      showToast(e.message || 'Ein interner Fehler ist aufgetreten.', 'error');
    });
    return () => {
      window.removeEventListener('keydown', onKey);
      window.removeEventListener('message', onMessage);
      window.removeEventListener('error', (e) => {
        showToast(e.message || 'Ein interner Fehler ist aufgetreten.', 'error');
      });
    };
  });

  function submitSearch(event: SubmitEvent) {
    event.preventDefault();
    const query = searchQuery.trim();
    if (!query) return;
    goto(`/?q=${encodeURIComponent(query)}`);
    searchInput?.blur();
  }

  async function logout() {
    try {
      await api.post('/auth/logout');
    } catch {
      // Session may already be gone.
    }
    await goto('/login');
    await invalidateAll();
  }

  $effect(() => {
    menuOpen = false;
  });
</script>

{#if embed || isAuthPage}
  {@render children()}
{:else}
  <div class="app-shell">
    <aside class="sidebar no-print">
      <a href="/" class="brand" aria-label="Zur Suche">
        <span class="brand-mark"><ChefHat size={23} strokeWidth={2.2} /></span>
        <span>
          <strong>{status.app_name}</strong>
          <small>Rezepte, sofort</small>
        </span>
      </a>

      <nav aria-label="Hauptnavigation">
        {#each nav as item}
          <a
            href={item.href}
            class="nav-link"
            class:active={item.href === '/'
              ? page.url.pathname === '/'
              : page.url.pathname.startsWith(item.href)}
            aria-current={item.href === '/'
              ? page.url.pathname === '/'
                ? 'page'
                : undefined
              : page.url.pathname.startsWith(item.href)
                ? 'page'
                : undefined}
          >
            <item.icon size={19} />
            <span>{item.label}</span>
          </a>
        {/each}
      </nav>

      <div class="sidebar-foot">
        <div class="user-card">
          <span class="avatar">{user?.display_name?.slice(0, 1).toUpperCase() ?? 'K'}</span>
          <span class="user-copy">
            <strong>{user?.display_name ?? 'Kochbuch'}</strong>
            <small>{user?.role === 'admin' ? 'Administrator' : 'Mitglied'}</small>
          </span>
        </div>
        <button class="btn btn-ghost btn-icon" type="button" onclick={logout} title="Abmelden" aria-label="Abmelden">
          <LogOut size={18} />
        </button>
      </div>
    </aside>

    <div class="main-column">
      <header class="topbar no-print">
        <a href="/" class="mobile-brand" aria-label="Zur Suche">
          <span class="brand-mark small"><ChefHat size={20} /></span>
          <strong>{status.app_name}</strong>
        </a>
        <form class="global-search" onsubmit={submitSearch} role="search">
          <Search size={17} />
          <input
            bind:this={searchInput}
            bind:value={searchQuery}
            type="search"
            placeholder="Rezept suchen …"
            aria-label="Rezepte durchsuchen"
          />
          <kbd>/</kbd>
        </form>
        <div class="top-actions">
          <ThemeToggle />
          <button
            class="btn btn-ghost btn-icon mobile-menu"
            type="button"
            onclick={() => (menuOpen = !menuOpen)}
            aria-label="Menü"
            aria-expanded={menuOpen}
          >
            {#if menuOpen}<X size={19} />{:else}<Menu size={19} />{/if}
          </button>
        </div>
      </header>

      {#if menuOpen}
        <div class="mobile-menu-panel no-print">
          {#each nav as item}
            <a href={item.href} class="nav-link" onclick={() => (menuOpen = false)}>
              <item.icon size={18} />
              <span>{item.label}</span>
            </a>
          {/each}
          <button class="nav-link" type="button" onclick={logout}>
            <LogOut size={18} />
            <span>Abmelden</span>
          </button>
        </div>
      {/if}

      <main class="main-content">
        {@render children()}
      </main>

      <nav class="bottom-nav no-print" aria-label="Hauptnavigation mobil">
        {#each nav as item}
          <a
            href={item.href}
            class="bottom-link"
            class:active={item.href === '/'
              ? page.url.pathname === '/'
              : page.url.pathname.startsWith(item.href)}
          >
            <item.icon size={21} />
            <span>{item.label}</span>
          </a>
        {/each}
      </nav>
    </div>
  </div>

  {#if !embed && !isAuthPage}
    <UpdateToast />
    <ToastContainer />
  {/if}
{/if}

<style>
  .app-shell {
    display: flex;
    min-height: 100dvh;
  }

  .sidebar {
    position: fixed;
    inset: 0 auto 0 0;
    width: 236px;
    display: flex;
    flex-direction: column;
    gap: 1.6rem;
    padding: 1.35rem 1rem;
    background: color-mix(in srgb, var(--bg-elevated) 88%, transparent);
    border-right: 1px solid var(--border);
    backdrop-filter: blur(18px);
    z-index: 20;
  }

  .brand,
  .mobile-brand {
    display: flex;
    align-items: center;
    gap: 0.7rem;
  }

  .brand-mark {
    display: grid;
    place-items: center;
    width: 42px;
    height: 42px;
    border-radius: 14px;
    background: var(--accent);
    color: var(--accent-contrast);
    box-shadow: 0 10px 26px color-mix(in srgb, var(--accent) 26%, transparent);
  }

  .brand-mark.small {
    width: 34px;
    height: 34px;
    border-radius: 11px;
  }

  .brand strong {
    display: block;
    font-size: 1.05rem;
    letter-spacing: -0.02em;
  }

  .brand small {
    display: block;
    color: var(--muted);
    font-size: 0.7rem;
    letter-spacing: 0.04em;
    text-transform: uppercase;
  }

  nav {
    display: flex;
    flex-direction: column;
    gap: 0.3rem;
  }

  .nav-link {
    display: flex;
    align-items: center;
    gap: 0.7rem;
    min-height: 44px;
    padding: 0.55rem 0.75rem;
    border-radius: 12px;
    color: var(--text-soft);
    font-weight: 600;
    font-size: 0.92rem;
    transition:
      background 150ms ease,
      color 150ms ease;
  }

  .nav-link:hover {
    background: var(--surface-2);
    color: var(--text);
  }

  .nav-link.active {
    background: color-mix(in srgb, var(--accent) 13%, var(--surface));
    color: var(--accent);
  }

  .sidebar-foot {
    margin-top: auto;
    display: flex;
    align-items: center;
    gap: 0.5rem;
    padding-top: 1rem;
    border-top: 1px solid var(--border);
  }

  .user-card {
    display: flex;
    align-items: center;
    gap: 0.55rem;
    min-width: 0;
    flex: 1;
  }

  .avatar {
    display: grid;
    place-items: center;
    width: 34px;
    height: 34px;
    flex: none;
    border-radius: 50%;
    background: var(--surface-3);
    color: var(--accent);
    font-weight: 700;
  }

  .user-copy {
    min-width: 0;
  }

  .user-copy strong,
  .user-copy small {
    display: block;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .user-copy strong {
    font-size: 0.82rem;
  }

  .user-copy small {
    color: var(--muted);
    font-size: 0.7rem;
  }

  .main-column {
    flex: 1;
    min-width: 0;
    margin-left: 236px;
  }

  .topbar {
    position: sticky;
    top: 0;
    z-index: 15;
    display: flex;
    align-items: center;
    gap: 1rem;
    min-height: var(--header-height);
    padding: 0.7rem clamp(1rem, 3vw, 2.4rem);
    background: color-mix(in srgb, var(--bg) 82%, transparent);
    backdrop-filter: blur(18px);
    border-bottom: 1px solid color-mix(in srgb, var(--border) 65%, transparent);
  }

  .mobile-brand {
    display: none;
  }

  .global-search {
    display: flex;
    align-items: center;
    gap: 0.55rem;
    width: min(480px, 46vw);
    min-height: 42px;
    padding: 0 0.8rem;
    border-radius: 999px;
    border: 1px solid var(--border);
    background: var(--surface);
    color: var(--muted);
    transition: border-color 150ms ease;
  }

  .global-search:focus-within {
    border-color: var(--accent);
  }

  .global-search input {
    flex: 1;
    min-width: 0;
    border: 0;
    background: transparent;
    outline: none;
    color: var(--text);
    font-size: 0.9rem;
  }

  .global-search kbd {
    border: 1px solid var(--border);
    border-radius: 6px;
    padding: 0 0.35rem;
    font-size: 0.7rem;
    color: var(--muted);
  }

  .top-actions {
    margin-left: auto;
    display: flex;
    align-items: center;
    gap: 0.3rem;
  }

  .mobile-menu {
    display: none;
  }

  .mobile-menu-panel {
    position: fixed;
    top: calc(var(--header-height) + 0.5rem);
    right: 1rem;
    z-index: 30;
    min-width: 220px;
    padding: 0.5rem;
    border: 1px solid var(--border);
    border-radius: 16px;
    background: var(--surface);
    box-shadow: var(--shadow);
  }

  .main-content {
    width: min(1240px, 100%);
    margin: 0 auto;
    padding: clamp(1.1rem, 3vw, 2.4rem) clamp(1rem, 3vw, 2.4rem) 5rem;
  }

  .bottom-nav {
    display: none;
  }

  @media (max-width: 900px) {
    .sidebar {
      display: none;
    }

    .main-column {
      margin-left: 0;
    }

    .mobile-brand {
      display: flex;
    }

    .global-search {
      display: none;
    }

    .mobile-menu {
      display: inline-flex;
    }

    .bottom-nav {
      position: fixed;
      left: 0;
      right: 0;
      bottom: 0;
      z-index: 25;
      display: flex;
      justify-content: space-around;
      gap: 0.2rem;
      padding: 0.45rem 0.4rem calc(0.45rem + env(safe-area-inset-bottom));
      background: color-mix(in srgb, var(--bg-elevated) 92%, transparent);
      backdrop-filter: blur(20px);
      border-top: 1px solid var(--border);
    }

    .bottom-link {
      display: flex;
      flex-direction: column;
      align-items: center;
      gap: 0.15rem;
      flex: 1;
      padding: 0.35rem 0.2rem;
      border-radius: 10px;
      color: var(--muted);
      font-size: 0.63rem;
      font-weight: 600;
      letter-spacing: 0.01em;
    }

    .bottom-link.active {
      color: var(--accent);
      background: color-mix(in srgb, var(--accent) 10%, transparent);
    }

    .main-content {
      padding-bottom: calc(5.4rem + env(safe-area-inset-bottom));
    }
  }

  @media (min-width: 901px) {
    .topbar {
      padding-left: 2.2rem;
    }
  }
</style>
