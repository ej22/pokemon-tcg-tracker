/* ── Collection view ──────────────────────────────────────────── */

const collectionTable  = document.getElementById('collection-table');
const collectionTbody  = document.getElementById('collection-tbody');
const collectionLoad   = document.getElementById('collection-loading');
const collectionEmpty  = document.getElementById('collection-empty');

async function loadCollection() {
  collectionLoad.classList.remove('hidden');
  collectionTable.classList.add('hidden');
  collectionEmpty.classList.add('hidden');

  try {
    const entries = await apiFetch('/collection');
    renderCollection(entries);
  } catch (e) {
    toast(`Failed to load collection: ${e.message}`, 'error');
  } finally {
    collectionLoad.classList.add('hidden');
  }
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
  if (!entries.length) {
    collectionEmpty.classList.remove('hidden');
    return;
  }

  collectionTbody.innerHTML = entries.map(e => {
    const price = bestPrice(e.prices, e.variant);
    const lastUpdated = e.prices?.[0]?.last_fetched_at
      ? fmtDate(e.prices[0].last_fetched_at)
      : '<span class="text-muted">—</span>';

    return `
      <tr>
        <td><strong>${e.card.name}</strong></td>
        <td>${e.card.set_code || '<span class="text-muted">—</span>'}</td>
        <td>${e.card.card_number || '<span class="text-muted">—</span>'}</td>
        <td>${e.language}</td>
        <td>${e.variant || '<span class="text-muted">—</span>'}</td>
        <td>${e.condition}</td>
        <td>${e.quantity}</td>
        <td>${e.purchase_price ? fmtEur(e.purchase_price) : '<span class="text-muted">—</span>'}</td>
        <td class="price-value">${fmtEur(price)}</td>
        <td>${pnlHtml(e.purchase_price, price, e.quantity)}</td>
        <td>${lastUpdated}</td>
        <td>
          <button class="btn btn-secondary btn-sm" onclick="openEditModal(${JSON.stringify(e).replace(/"/g, '&quot;')})">Edit</button>
          <button class="btn btn-danger btn-sm" onclick="deleteEntry(${e.id})">✕</button>
        </td>
      </tr>`;
  }).join('');

  collectionTable.classList.remove('hidden');
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
const editOverlay   = document.getElementById('edit-modal-overlay');
const editForm      = document.getElementById('edit-card-form');
const editModalClose = document.getElementById('edit-modal-close');

function openEditModal(entry) {
  const f = editForm.elements;
  f.entry_id.value       = entry.id;
  f.quantity.value        = entry.quantity;
  f.condition.value       = entry.condition;
  f.language.value        = entry.language;
  f.variant.value         = entry.variant || '';
  f.purchase_price.value  = entry.purchase_price || '';
  f.date_acquired.value   = entry.date_acquired || '';
  f.notes.value           = entry.notes || '';
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
    await apiFetch(`/collection/${id}`, {
      method: 'PUT',
      body: JSON.stringify(body),
    });
    toast('Entry updated');
    editOverlay.classList.add('hidden');
    loadCollection();
  } catch (e) {
    toast(`Error: ${e.message}`, 'error');
  }
});

document.getElementById('btn-add-card').addEventListener('click', () => {
  openAddModal();
});
