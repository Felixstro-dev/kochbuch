<script lang="ts">
  import {
    Check,
    CheckCheck,
    Plus,
    Sparkles,
    Trash2,
    Undo2
  } from 'lucide-svelte';
  import { api } from '#lib/api';
  import type { Wish } from '#lib/types';

  let { data }: { data: { wishes: Wish[]; error: string | null } } = $props();

  // svelte-ignore state_referenced_locally
  let wishes = $state<Wish[]>(data.wishes);
  let text = $state('');
  let note = $state('');
  let busy = $state(false);
  // svelte-ignore state_referenced_locally
  let notice = $state(data.error ?? '');
  let showDone = $state(false);

  const open = $derived(wishes.filter((wish) => wish.status !== 'done'));
  const done = $derived(wishes.filter((wish) => wish.status === 'done'));

  async function addWish() {
    const value = text.trim();
    if (!value || busy) return;
    busy = true;
    notice = '';
    try {
      const created = await api.post<Wish>('/wishes', { text: value, note: note.trim() });
      wishes = [created, ...wishes];
      text = '';
      note = '';
    } catch (cause) {
      notice = cause instanceof Error ? cause.message : 'Der Wunsch konnte nicht gespeichert werden.';
    } finally {
      busy = false;
    }
  }

  async function toggle(wish: Wish) {
    const next = wish.status === 'done' ? 'open' : 'done';
    // Optimistisch umschalten, damit die Liste sofort reagiert
    wishes = wishes.map((item) =>
      item.id === wish.id
        ? { ...item, status: next, done_at: next === 'done' ? new Date().toISOString() : null }
        : item
    );
    try {
      const updated = await api.patch<Wish>(`/wishes/${encodeURIComponent(wish.id)}`, { status: next });
      wishes = wishes.map((item) => (item.id === wish.id ? updated : item));
    } catch (cause) {
      wishes = wishes.map((item) => (item.id === wish.id ? wish : item));
      notice = cause instanceof Error ? cause.message : 'Der Status konnte nicht geändert werden.';
    }
  }

  async function remove(wish: Wish) {
    try {
      await api.delete(`/wishes/${encodeURIComponent(wish.id)}`);
      wishes = wishes.filter((item) => item.id !== wish.id);
    } catch (cause) {
      notice = cause instanceof Error ? cause.message : 'Der Wunsch konnte nicht gelöscht werden.';
    }
  }
</script>

<svelte:head>
  <title>Wünsche · Kochbuch</title>
</svelte:head>

<section class="head">
  <span class="eyebrow"><Sparkles size={14} /> Wunschzettel</span>
  <h1>Wünsche</h1>
  <p class="muted">
    Trag ein, worauf du Lust hast – auch ohne passendes Rezept. „Zwetschgenknödel", „Curry vom
    Vortag", alles was dir einfällt.
  </p>
</section>

<section class="surface composer">
  <input
    class="field wish-input"
    bind:value={text}
    maxlength="300"
    placeholder="Was hättest du gern? z. B. Zwetschgenknödel …"
    onkeydown={(event) => event.key === 'Enter' && (event.preventDefault(), addWish())}
  />
  <input
    class="field note-input"
    bind:value={note}
    maxlength="1000"
    placeholder="Notiz (optional) – z. B. mit Vanillesoße"
    onkeydown={(event) => event.key === 'Enter' && (event.preventDefault(), addWish())}
  />
  <button class="btn btn-primary" type="button" onclick={addWish} disabled={busy || !text.trim()}>
    <Plus size={16} /> {busy ? 'Speichere …' : 'Wünschen'}
  </button>
</section>

{#if notice}<p class="notice muted">{notice}</p>{/if}

<section class="surface board">
  <header class="board-head">
    <h2>Offen <span class="count">{open.length}</span></h2>
  </header>

  <ul class="wishes">
    {#each open as wish (wish.id)}
      <li class="wish">
        <button type="button" class="tick" onclick={() => toggle(wish)} aria-label="Als erledigt markieren">
          <Check size={14} />
        </button>
        <div class="wish-body">
          <span class="wish-text">{wish.text}</span>
          {#if wish.note}<span class="wish-note muted">{wish.note}</span>{/if}
        </div>
        <button type="button" class="remove" onclick={() => remove(wish)} aria-label="Wunsch löschen">
          <Trash2 size={14} />
        </button>
      </li>
    {:else}
      <li class="empty muted">Noch keine Wünsche. Trag oben deinen ersten ein.</li>
    {/each}
  </ul>
</section>

{#if done.length > 0}
  <section class="surface board done">
    <header class="board-head">
      <h2>
        <CheckCheck size={16} /> Erledigt <span class="count">{done.length}</span>
      </h2>
      <button class="btn btn-sm" type="button" onclick={() => (showDone = !showDone)}>
        {showDone ? 'Ausblenden' : 'Anzeigen'}
      </button>
    </header>

    {#if showDone}
      <ul class="wishes">
        {#each done as wish (wish.id)}
          <li class="wish done-item">
            <button type="button" class="tick tick-done" onclick={() => toggle(wish)} aria-label="Wieder öffnen">
              <Check size={14} />
            </button>
            <div class="wish-body">
              <span class="wish-text">{wish.text}</span>
              {#if wish.note}<span class="wish-note muted">{wish.note}</span>{/if}
            </div>
            <button type="button" class="reopen" onclick={() => toggle(wish)} aria-label="Wieder öffnen" title="Wieder öffnen">
              <Undo2 size={14} />
            </button>
            <button type="button" class="remove" onclick={() => remove(wish)} aria-label="Wunsch löschen">
              <Trash2 size={14} />
            </button>
          </li>
        {/each}
      </ul>
    {/if}
  </section>
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
    max-width: 52ch;
  }

  .composer {
    display: grid;
    grid-template-columns: minmax(0, 2fr) minmax(0, 1fr) auto;
    gap: 0.5rem;
    padding: 0.8rem;
    align-items: center;
    margin-bottom: 1rem;
  }

  .field {
    min-height: 44px;
    padding: 0.5rem 0.75rem;
    font-size: 0.92rem;
  }

  .notice {
    font-size: 0.8rem;
    margin-bottom: 0.7rem;
  }

  .board {
    padding: 1rem;
    display: flex;
    flex-direction: column;
    gap: 0.7rem;
  }

  .board + .board {
    margin-top: 1rem;
  }

  .board-head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 0.5rem;
  }

  .board-head h2 {
    display: inline-flex;
    align-items: center;
    gap: 0.4rem;
    font-size: 1rem;
  }

  .count {
    font-size: 0.75rem;
    font-weight: 600;
    color: var(--muted);
    background: var(--surface-2);
    border: 1px solid var(--border);
    border-radius: 999px;
    padding: 0.05rem 0.5rem;
  }

  .wishes {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    flex-direction: column;
    gap: 0.35rem;
  }

  .wish {
    display: flex;
    align-items: center;
    gap: 0.6rem;
    padding: 0.55rem 0.6rem;
    border-radius: 12px;
    background: var(--bg-elevated);
    border: 1px solid var(--border);
  }

  .wish-body {
    flex: 1;
    min-width: 0;
    display: flex;
    flex-direction: column;
    gap: 0.1rem;
  }

  .wish-text {
    font-size: 0.95rem;
    overflow-wrap: anywhere;
  }

  .wish-note {
    font-size: 0.78rem;
    overflow-wrap: anywhere;
  }

  .tick {
    width: 26px;
    height: 26px;
    flex: none;
    border-radius: 8px;
    border: 1px solid var(--border-strong);
    background: var(--surface-2);
    color: var(--accent);
    display: grid;
    place-items: center;
  }

  .tick:hover {
    border-color: var(--accent);
  }

  .tick-done {
    background: color-mix(in srgb, var(--accent) 22%, transparent);
  }

  .done-item .wish-text {
    text-decoration: line-through;
    color: var(--muted);
  }

  .remove,
  .reopen {
    border: 0;
    background: transparent;
    color: var(--muted);
    flex: none;
    display: grid;
    place-items: center;
    padding: 0.25rem;
  }

  .remove:hover {
    color: var(--danger);
  }

  .reopen:hover {
    color: var(--accent);
  }

  .empty {
    font-size: 0.85rem;
    padding: 0.6rem 0.2rem;
  }

  .btn-sm {
    min-height: 34px;
    padding: 0.3rem 0.7rem;
    font-size: 0.78rem;
  }

  .done {
    opacity: 0.95;
  }

  @media (max-width: 700px) {
    .composer {
      grid-template-columns: 1fr;
    }
  }
</style>
