<script lang="ts">
  import { onMount } from 'svelte';
  import { goto } from '$app/navigation';
  import {
    CalendarDays,
    Check,
    ClipboardCopy,
    Plus,
    Search,
    ShoppingBasket,
    Trash2,
    X
  } from 'lucide-svelte';
  import { api } from '#lib/api';
  import type { RecipeDetail, RecipeSummary } from '#lib/types';

  let { data }: { data: { recipes: RecipeSummary[] } } = $props();

  const DAYS = ['Mo', 'Di', 'Mi', 'Do', 'Fr', 'Sa', 'So'] as const;
  const PLAN_KEY = 'kochbuch.plan.v1';
  const SHOP_KEY = 'kochbuch.shopping.v1';

  type ShoppingItem = { id: string; text: string; checked: boolean };

  let plan = $state<Record<string, string[]>>({});
  let shopping = $state<ShoppingItem[]>([]);
  let manual = $state('');
  let busy = $state(false);
  let notice = $state('');
  let selected = $state<Record<string, string>>({});

  const byKey = $derived(new Map(data.recipes.map((recipe) => [recipe.cache_key, recipe])));

  onMount(() => {
    try {
      const rawPlan = localStorage.getItem(PLAN_KEY);
      if (rawPlan) plan = JSON.parse(rawPlan);
      const rawShop = localStorage.getItem(SHOP_KEY);
      if (rawShop) shopping = JSON.parse(rawShop);
    } catch {
      // ignore corrupt storage
    }
  });

  function persistPlan() {
    localStorage.setItem(PLAN_KEY, JSON.stringify(plan));
  }

  function persistShop() {
    localStorage.setItem(SHOP_KEY, JSON.stringify(shopping));
  }

  function addToDay(day: string) {
    const key = selected[day];
    if (!key) return;
    const current = plan[day] ?? [];
    if (!current.includes(key)) {
      plan = { ...plan, [day]: [...current, key] };
      persistPlan();
    }
    selected = { ...selected, [day]: '' };
  }

  function removeFromDay(day: string, key: string) {
    plan = { ...plan, [day]: (plan[day] ?? []).filter((item) => item !== key) };
    persistPlan();
  }

  async function buildShoppingList() {
    const keys = [...new Set(Object.values(plan).flat())];
    if (keys.length === 0) {
      notice = 'Plane zuerst ein Rezept ein.';
      return;
    }
    busy = true;
    notice = '';
    try {
      const details = await Promise.all(
        keys.map((key) =>
          api
            .get<RecipeDetail>(`/recipes/${encodeURIComponent(key)}`)
            .catch(() => null)
        )
      );
      const merged = new Map<string, string>();
      for (const detail of details) {
        if (!detail) continue;
        for (const group of detail.ingredient_groups ?? []) {
          for (const ing of group.items ?? []) {
            if (!ing.name) continue;
            const text = [ing.amount ?? '', ing.unit ?? '', ing.name]
              .filter((part) => String(part).trim() !== '')
              .join(' ')
              .trim();
            const id = text.toLowerCase();
            if (!merged.has(id)) merged.set(id, text);
          }
        }
      }
      const existing = new Set(shopping.map((item) => item.text.toLowerCase()));
      const additions: ShoppingItem[] = [...merged.values()]
        .filter((text) => !existing.has(text.toLowerCase()))
        .map((text) => ({ id: crypto.randomUUID(), text, checked: false }));
      shopping = [...shopping, ...additions];
      persistShop();
      notice =
        additions.length > 0
          ? `${additions.length} Zutaten zur Einkaufsliste hinzugefügt.`
          : 'Alle Zutaten stehen bereits auf der Liste.';
    } catch {
      notice = 'Zutaten konnten nicht geladen werden.';
    } finally {
      busy = false;
    }
  }

  function addManual() {
    const text = manual.trim();
    if (!text) return;
    shopping = [...shopping, { id: crypto.randomUUID(), text, checked: false }];
    manual = '';
    persistShop();
  }

  function toggleItem(id: string) {
    shopping = shopping.map((item) =>
      item.id === id ? { ...item, checked: !item.checked } : item
    );
    persistShop();
  }

  function removeItem(id: string) {
    shopping = shopping.filter((item) => item.id !== id);
    persistShop();
  }

  function clearChecked() {
    shopping = shopping.filter((item) => !item.checked);
    persistShop();
  }

  async function copyList() {
    const lines = shopping
      .filter((item) => !item.checked)
      .map((item) => `- ${item.text}`)
      .join('\n');
    try {
      await navigator.clipboard.writeText(lines || 'Einkaufsliste ist leer.');
      notice = 'Einkaufsliste kopiert.';
    } catch {
      notice = 'Kopieren nicht möglich.';
    }
  }
</script>

<svelte:head>
  <title>Plan · Kochbuch</title>
</svelte:head>

<section class="head">
  <span class="eyebrow"><CalendarDays size={14} /> Wochenplan</span>
  <h1>Plan</h1>
  <p class="muted">Plane Rezepte für die Woche und erzeuge daraus deine Einkaufsliste – ohne externes Konto.</p>
</section>

<div class="layout">
  <section class="surface week">
    {#each DAYS as day (day)}
      <article class="day">
        <header><strong>{day}</strong></header>
        <div class="chips">
          {#each plan[day] ?? [] as key (key)}
            <span class="chip chip-accent">
              {byKey.get(key)?.title ?? 'Rezept'}
              <button type="button" class="chip-x" onclick={() => removeFromDay(day, key)} aria-label="Entfernen">
                <X size={13} />
              </button>
            </span>
          {/each}
          {#if (plan[day] ?? []).length === 0}
            <span class="empty-day muted">Nichts geplant</span>
          {/if}
        </div>
        <div class="day-add">
          <select class="field" bind:value={selected[day]}>
            <option value="">Rezept wählen …</option>
            {#each data.recipes as recipe (recipe.cache_key)}
              <option value={recipe.cache_key}>{recipe.title}</option>
            {/each}
          </select>
          <button class="btn btn-icon" type="button" onclick={() => addToDay(day)} aria-label="Hinzufügen">
            <Plus size={16} />
          </button>
        </div>
      </article>
    {/each}

    {#if data.recipes.length === 0}
      <div class="no-recipes">
        <p class="muted">Noch keine gespeicherten Rezepte. Markiere Rezepte als Favorit oder speichere sie.</p>
        <button class="btn btn-primary" type="button" onclick={() => goto('/')}>
          <Search size={16} /> Rezepte entdecken
        </button>
      </div>
    {/if}
  </section>

  <aside class="surface shopping">
    <header class="shop-head">
      <h2><ShoppingBasket size={18} /> Einkaufsliste</h2>
      <div class="shop-actions">
        <button class="btn btn-primary btn-sm" type="button" onclick={buildShoppingList} disabled={busy}>
          {busy ? 'Sammle …' : 'Aus Plan erzeugen'}
        </button>
      </div>
    </header>

    {#if notice}<p class="notice muted">{notice}</p>{/if}

    <div class="manual">
      <input
        class="field"
        bind:value={manual}
        placeholder="Zutat hinzufügen …"
        onkeydown={(event) => event.key === 'Enter' && (event.preventDefault(), addManual())}
      />
      <button class="btn btn-icon" type="button" onclick={addManual} aria-label="Hinzufügen">
        <Plus size={16} />
      </button>
    </div>

    <ul class="items">
      {#each shopping as item (item.id)}
        <li class:checked={item.checked}>
          <button type="button" class="tick" onclick={() => toggleItem(item.id)} aria-label="Abhaken">
            {#if item.checked}<Check size={14} />{/if}
          </button>
          <span class="item-text">{item.text}</span>
          <button type="button" class="remove" onclick={() => removeItem(item.id)} aria-label="Löschen">
            <Trash2 size={14} />
          </button>
        </li>
      {:else}
        <li class="empty-list muted">Die Einkaufsliste ist leer.</li>
      {/each}
    </ul>

    <footer class="shop-foot">
      <button class="btn btn-sm" type="button" onclick={copyList}>
        <ClipboardCopy size={15} /> Kopieren
      </button>
      <button class="btn btn-sm btn-ghost" type="button" onclick={clearChecked} disabled={!shopping.some((i) => i.checked)}>
        Erledigte löschen
      </button>
    </footer>
  </aside>
</div>

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
  }

  .layout {
    display: grid;
    grid-template-columns: minmax(0, 1fr) 340px;
    gap: 1rem;
    align-items: start;
  }

  .week {
    padding: 1rem;
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
    gap: 0.8rem;
  }

  .day {
    border: 1px solid var(--border);
    border-radius: 14px;
    padding: 0.7rem;
    background: var(--surface-2);
    display: flex;
    flex-direction: column;
    gap: 0.6rem;
  }

  .day header strong {
    font-size: 0.95rem;
    color: var(--accent);
  }

  .chips {
    display: flex;
    flex-wrap: wrap;
    gap: 0.35rem;
    min-height: 1.6rem;
  }

  .chip-x {
    display: inline-flex;
    border: 0;
    background: transparent;
    color: inherit;
    padding: 0;
    margin-left: 0.1rem;
  }

  .empty-day {
    font-size: 0.78rem;
  }

  .day-add {
    display: flex;
    gap: 0.4rem;
  }

  .day-add .field {
    min-height: 40px;
    padding: 0.4rem 0.6rem;
    font-size: 0.82rem;
  }

  .no-recipes {
    grid-column: 1 / -1;
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 0.6rem;
    padding: 1.4rem;
    text-align: center;
  }

  .shopping {
    padding: 1rem;
    display: flex;
    flex-direction: column;
    gap: 0.7rem;
    position: sticky;
    top: calc(var(--header-height) + 0.8rem);
  }

  .shop-head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 0.5rem;
  }

  .shop-head h2 {
    display: inline-flex;
    align-items: center;
    gap: 0.4rem;
    font-size: 1rem;
  }

  .btn-sm {
    min-height: 36px;
    padding: 0.35rem 0.75rem;
    font-size: 0.8rem;
  }

  .notice {
    font-size: 0.78rem;
  }

  .manual {
    display: flex;
    gap: 0.4rem;
  }

  .manual .field {
    min-height: 40px;
    padding: 0.4rem 0.7rem;
    font-size: 0.85rem;
  }

  .items {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    flex-direction: column;
    gap: 0.3rem;
    max-height: 50vh;
    overflow-y: auto;
  }

  .items li {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    padding: 0.4rem 0.5rem;
    border-radius: 10px;
    background: var(--bg-elevated);
    font-size: 0.86rem;
  }

  .items li.checked .item-text {
    text-decoration: line-through;
    color: var(--muted);
  }

  .tick {
    width: 22px;
    height: 22px;
    flex: none;
    border-radius: 7px;
    border: 1px solid var(--border-strong);
    background: var(--surface-2);
    color: var(--accent);
    display: grid;
    place-items: center;
  }

  .item-text {
    flex: 1;
    min-width: 0;
    overflow-wrap: anywhere;
  }

  .remove {
    border: 0;
    background: transparent;
    color: var(--muted);
    flex: none;
  }

  .remove:hover {
    color: var(--danger);
  }

  .empty-list {
    font-size: 0.82rem;
    padding: 0.5rem;
  }

  .shop-foot {
    display: flex;
    gap: 0.5rem;
    flex-wrap: wrap;
  }

  @media (max-width: 900px) {
    .layout {
      grid-template-columns: 1fr;
    }

    .shopping {
      position: static;
    }
  }
</style>
