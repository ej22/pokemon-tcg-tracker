/* ── Collection view ──────────────────────────────────────────── */

const collectionTable = document.getElementById('collection-table');
const collectionTbody = document.getElementById('collection-tbody');
const collectionEmpty = document.getElementById('collection-empty');

async function loadCollection() {
  showSkeletonRows();
  collectionTable.classList.remove('hidden');
  collectionEmpty.classList.add('hidden');

  try {
    const entries = await apiFetch('/collection');
    renderCollection(entries);
  } catch (e) {
    toast(`Failed to load collection: ${e.message}`, 'error');
    collectionTbody.innerHTML = '';
  }
}

function showSkeletonRows(n = 6) {
  collectionTbody.innerHTML = Array.from({ length: n }, () => `
    <tr class="skeleton-row">
      <td><div class="skeleton skeleton-cell" style="width:75%"></div></td>
      <td><div class="skeleton skeleton-cell" style="width:55%"></div></td>
      <td><div class="skeleton skeleton-cell" style="width:35%"></div></td>
      <td><div class="skeleton skeleton-cell" style="width:50%"></div></td>
      <td><div class="skeleton skeleton-cell" style="width:55%"></div></td>
      <td><div class="skeleton skeleton-badge"></div></td>
      <td><div class="skeleton skeleton-cell" style="width:25%"></div></td>
      <td><div class="skeleton skeleton-cell" style="width:50%"></div></td>
      <td><div class="skeleton skeleton-cell" style="width:55%"></div></td>
      <td><div class="skeleton skeleton-cell" style="width:55%"></div></td>
      <td><div class="skeleton skeleton-cell" style="width:55%"></div></td>
      <td></td>
    </tr>
  `).join('');
}

function conditionChip(cond) {
  const cls = { NM: 'chip-nm', LP: 'chip-lp', MP: 'chip-mp', HP: 'chip-hp', DMG: 'chip-dmg' }[cond] || 'chip-default';
  return `<span class="chip ${cls}">${cond}</span>`;
}

function bestPrice(prices, variant) {
  if (!prices || !prices.length) return null;
  const cm = prices.filter(p => p.source === 'cardmarket');
  if (!cm.length) return null;
  const matched = variant ? cm.find(p => p.variant_type === variant) : null;
  const p = matched || cm[0];
  return p.trend_price ?? p.avg_price ?? p.mid_price ?? null;
}

function renderCollection(entries) {
  const subtitle = document.getElementById('collection-subtitle');
  if (subtitle) {
    subtitle.textContent = entries.length
      ? `${entries.length} entr${entries.length === 1 ? 'y' : 'ies'}`
      : 'No cards yet';
  }

  if (!entries.length) {
    collectionTbody.innerHTML = '';
    collectionEmpty.classList.remove('hidden');
    updateSidebarStats(0, null);
    return;
  }

  let totalValue = 0;
  let totalCards = 0;

  collectionTbody.innerHTML = entries.map(e => {
    const price = bestPrice(e.prices, e.variant);
    const lastUpdated = e.prices?.[0]?.last_fetched_at
      ? fmtDate(e.prices[0].last_fetched_at)
      : '<span class="text-muted">—</span>';

    if (price != null) totalValue += parseFloat(price) * (e.quantity || 1);
    totalCards += (e.quantity || 1);

    const priceHtml = price != null
      ? `<span class="cell-price">€${parseFloat(price).toFixed(2)}</span>`
      : '<span class="text-muted">—</span>';

    const boughtHtml = e.purchase_price != null
      ? `<span class="cell-mono">€${parseFloat(e.purchase_price).toFixed(2)}</span>`
      : '<span class="text-muted">—</span>';

    const entryJson = JSON.stringify(e).replace(/"/g, '&quot;');

    return `
      <tr>
        <td><strong>${e.card.name}</strong></td>
        <td><span class="cell-mono">${e.card.set_code || '<span class="text-muted">—</span>'}</span></td>
        <td><span class="cell-mono">${e.card.card_number || '<span class="text-muted">—</span>'}</span></td>
        <td>${e.language}</td>
        <td>${e.variant || '<span class="text-muted">—</span>'}</td>
        <td>${conditionChip(e.condition)}</td>
        <td><span class="cell-mono">${e.quantity}</span></td>
        <td>${boughtHtml}</td>
        <td>${priceHtml}</td>
        <td>${pnlHtml(e.purchase_price, price, e.quantity)}</td>
        <td><span class="cell-mono" style="font-size:0.775rem">${lastUpdated}</span></td>
        <td style="white-space:nowrap">
          <button class="btn btn-ghost btn-icon btn-sm" title="Edit"
            onclick="openEditModal(${entryJson})">
            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.75" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" d="m16.862 4.487 1.687-1.688a1.875 1.875 0 1 1 2.652 2.652L10.582 16.07a4.5 4.5 0 0 1-1.897 1.13L6 18l.8-2.685a4.5 4.5 0 0 1 1.13-1.897l8.932-8.931Zm0 0L19.5 7.125" /></svg>
          </button>
          <button class="btn btn-ghost btn-icon btn-sm" title="Remove" style="color:var(--red)"
            onclick="deleteEntry(${e.id})">
            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.75" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" d="m14.74 9-.346 9m-4.788 0L9.26 9m9.968-3.21c.342.052.682.107 1.022.166m-1.022-.165L18.16 19.673a2.25 2.25 0 0 1-2.244 2.077H8.084a2.25 2.25 0 0 1-2.244-2.077L4.772 5.79m14.456 0a48.108 48.108 0 0 0-3.478-.397m-12 .562c.34-.059.68-.114 1.022-.165m0 0a48.11 48.11 0 0 1 3.478-.397m7.5 0v-.916c0-1.18-.91-2.164-2.09-2.201a51.964 51.964 0 0 0-3.32 0c-1.18.037-2.09 1.022-2.09 2.201v.916m7.5 0a48.667 48.667 0 0 0-7.5 0" /></svg>
          </button>
        </td>
      </tr>`;
  }).join('');

  updateSidebarStats(totalCards, totalValue > 0 ? totalValue : null);
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
