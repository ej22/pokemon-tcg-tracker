/* ── Collection view ──────────────────────────────────────────── */

const collectionGrid  = document.getElementById('collection-grid');
const collectionEmpty = document.getElementById('collection-empty');

async function loadCollection() {
  showSkeletonCards();

  try {
    const entries = await apiFetch('/collection');
    renderCollection(entries);
  } catch (e) {
    toast(`Failed to load collection: ${e.message}`, 'error');
    collectionGrid.innerHTML = '';
  }
}

function showSkeletonCards(n = 12) {
  collectionGrid.classList.remove('hidden');
  collectionEmpty.classList.add('hidden');
  collectionGrid.innerHTML = Array.from({ length: n }, () =>
    `<div class="poster-skeleton skeleton"></div>`
  ).join('');
}

function conditionChip(cond) {
  const cls = { NM: 'chip-nm', LP: 'chip-lp', MP: 'chip-mp', HP: 'chip-hp', DMG: 'chip-dmg' }[cond] || 'chip-default';
  return `<span class="chip ${cls}">${cond}</span>`;
}

function bestPrice(prices, variant) {
  if (!prices || !prices.length) return null;
  // Accept PokéWallet CardMarket prices and PriceCharting-scraped prices
  const cm = prices.filter(p => p.source === 'cardmarket' || p.source === 'pricecharting_scrape');
  if (!cm.length) return null;
  const matched = variant ? cm.find(p => p.variant_type === variant) : null;
  const p = matched || cm[0];
  return p.trend_price ?? p.avg_price ?? p.mid_price ?? null;
}

function isPriceStale(prices, ttlHours = 48) {
  if (!prices || !prices.length) return false;
  const cm = prices.filter(p => p.source === 'cardmarket' || p.source === 'pricecharting_scrape');
  if (!cm.length) return false;
  const now = Date.now();
  return cm.every(p => {
    const fetched = new Date(p.last_fetched_at).getTime();
    return (now - fetched) > ttlHours * 3600 * 1000;
  });
}

function renderCollection(entries) {
  const subtitle = document.getElementById('collection-subtitle');
  if (subtitle) {
    subtitle.textContent = entries.length
      ? `${entries.length} entr${entries.length === 1 ? 'y' : 'ies'}`
      : 'No cards yet';
  }

  if (!entries.length) {
    collectionGrid.innerHTML = '';
    collectionGrid.classList.add('hidden');
    collectionEmpty.classList.remove('hidden');
    updateSidebarStats(0, null);
    return;
  }

  collectionEmpty.classList.add('hidden');
  collectionGrid.classList.remove('hidden');

  let totalValue = 0;
  let totalCards = 0;

  collectionGrid.innerHTML = entries.map(e => {
    const price = bestPrice(e.prices, e.variant);
    if (price != null) totalValue += parseFloat(price) * (e.quantity || 1);
    totalCards += (e.quantity || 1);

    const priceStr  = price != null ? `€${parseFloat(price).toFixed(2)}` : null;
    const imageUrl  = `/api/images/${e.card.api_id}`;
    const entryJson = JSON.stringify(e).replace(/"/g, '&quot;');
    const qty       = e.quantity > 1 ? `<span class="poster-qty-badge">×${e.quantity}</span>` : '';

    // P&L indicator dot
    let pnlDot = '';
    if (e.purchase_price != null && price != null) {
      const diff = parseFloat(price) - parseFloat(e.purchase_price);
      pnlDot = diff >= 0
        ? `<span class="poster-pnl-dot pnl-pos" title="+€${diff.toFixed(2)}"></span>`
        : `<span class="poster-pnl-dot pnl-neg" title="€${diff.toFixed(2)}"></span>`;
    }

    const imgContent = `<img src="${imageUrl}" alt="${e.card.name}" onerror="this.parentElement.innerHTML=cardPlaceholder()">`;

    const isScraped  = e.card.source === 'pricecharting_scrape';
    const isStale    = isScraped && isPriceStale(e.prices);
    const pcBadge    = isScraped ? `<span class="chip chip-cm" title="Price from PriceCharting (USD→EUR)">PC</span>` : '';
    const staleBadge = isStale   ? `<span class="chip chip-stale" title="Price may be outdated">Stale</span>` : '';

    return `
      <div class="poster-card" role="button" tabindex="0"
           aria-label="${e.card.name}"
           data-entry="${entryJson}"
           onkeydown="if(event.key==='Enter')openEditModal(JSON.parse(this.dataset.entry))">
        ${imgContent}

        <div class="poster-badges">
          ${conditionChip(e.condition)}
          ${qty}
          ${pcBadge}
          ${staleBadge}
        </div>

        <div class="poster-actions" onclick="event.stopPropagation()">
          <button class="poster-action-btn poster-action-edit" title="Edit"
            onclick="openEditModal(${entryJson})">
            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.75" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" d="m16.862 4.487 1.687-1.688a1.875 1.875 0 1 1 2.652 2.652L10.582 16.07a4.5 4.5 0 0 1-1.897 1.13L6 18l.8-2.685a4.5 4.5 0 0 1 1.13-1.897l8.932-8.931Zm0 0L19.5 7.125" /></svg>
          </button>
          <button class="poster-action-btn poster-action-delete" title="Remove"
            onclick="deleteEntry(${e.id})">
            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.75" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" d="m14.74 9-.346 9m-4.788 0L9.26 9m9.968-3.21c.342.052.682.107 1.022.166m-1.022-.165L18.16 19.673a2.25 2.25 0 0 1-2.244 2.077H8.084a2.25 2.25 0 0 1-2.244-2.077L4.772 5.79m14.456 0a48.108 48.108 0 0 0-3.478-.397m-12 .562c.34-.059.68-.114 1.022-.165m0 0a48.11 48.11 0 0 1 3.478-.397m7.5 0v-.916c0-1.18-.91-2.164-2.09-2.201a51.964 51.964 0 0 0-3.32 0c-1.18.037-2.09 1.022-2.09 2.201v.916m7.5 0a48.667 48.667 0 0 0-7.5 0" /></svg>
          </button>
        </div>

        <div class="poster-overlay">
          <div class="poster-name">${e.card.name}</div>
          <div class="poster-meta">
            <span>${e.card.set_code || ''}${e.card.card_number ? ` · ${e.card.card_number}` : ''}</span>
            <span class="poster-price-row">
              ${pnlDot}
              ${priceStr ? `<span class="poster-price">${priceStr}</span>` : '<span class="poster-no-price">—</span>'}
            </span>
          </div>
        </div>
      </div>`;
  }).join('');

  updateSidebarStats(totalCards, totalValue > 0 ? totalValue : null);
}

function cardPlaceholder() {
  return `<div class="poster-placeholder"><div class="poster-placeholder-icon">P</div></div>`;
}

async function deleteEntry(id) {
  if (!confirm('Remove this card from your collection?')) return;
  try {
    await apiFetch(`/collection/${id}`, { method: 'DELETE' });
    toast('Card removed');
    loadCollection();
  } catch (e) {
    toast(`Error: ${e.message}`, 'error');
  }
}

// ── Edit Modal ───────────────────────────────────────────────────
const editOverlay    = document.getElementById('edit-modal-overlay');
const editForm       = document.getElementById('edit-card-form');
const editModalClose = document.getElementById('edit-modal-close');

function openEditModal(entry) {
  document.querySelectorAll('.poster-card.tapped').forEach(c => c.classList.remove('tapped'));
  const f = editForm.elements;
  f.entry_id.value      = entry.id;
  f.quantity.value       = entry.quantity;
  f.condition.value      = entry.condition;
  f.language.value       = entry.language;
  f.variant.value        = entry.variant || '';
  f.purchase_price.value = entry.purchase_price || '';
  f.date_acquired.value  = entry.date_acquired || '';
  f.notes.value          = entry.notes || '';
  editOverlay.classList.remove('hidden');
}

editModalClose.addEventListener('click', () => editOverlay.classList.add('hidden'));
editOverlay.addEventListener('click', e => {
  if (e.target === editOverlay) editOverlay.classList.add('hidden');
});

editForm.addEventListener('submit', async e => {
  e.preventDefault();
  const f = editForm.elements;
  const id = f.entry_id.value;
  const body = {
    quantity:       parseInt(f.quantity.value, 10),
    condition:      f.condition.value,
    language:       f.language.value,
    variant:        f.variant.value || null,
    purchase_price: f.purchase_price.value ? parseFloat(f.purchase_price.value) : null,
    date_acquired:  f.date_acquired.value || null,
    notes:          f.notes.value || null,
  };

  try {
    await apiFetch(`/collection/${id}`, { method: 'PUT', body: JSON.stringify(body) });
    toast('Entry updated');
    editOverlay.classList.add('hidden');
    loadCollection();
  } catch (e) {
    toast(`Error: ${e.message}`, 'error');
  }
});

document.getElementById('btn-add-card').addEventListener('click', () => openAddModal());

// ── Tap-to-reveal actions (touch devices) ────────────────────────
// First tap: reveal edit/delete buttons. Second tap: open edit modal.
collectionGrid.addEventListener('click', e => {
  const card = e.target.closest('.poster-card[data-entry]');
  if (!card) return;
  if (window.matchMedia('(hover: none)').matches) {
    if (!card.classList.contains('tapped')) {
      document.querySelectorAll('.poster-card.tapped').forEach(c => c.classList.remove('tapped'));
      card.classList.add('tapped');
      return;
    }
    card.classList.remove('tapped');
  }
  openEditModal(JSON.parse(card.dataset.entry));
});
