/* ── Search modal + add-to-collection ─────────────────────────── */

const modalOverlay  = document.getElementById('modal-overlay');
const modalClose    = document.getElementById('modal-close');
const stepSearch    = document.getElementById('modal-step-search');
const stepUrl       = document.getElementById('modal-step-url');
const stepForm      = document.getElementById('modal-step-form');
const searchInput   = document.getElementById('search-input');
const btnSearch     = document.getElementById('btn-search');
const searchLoading = document.getElementById('search-loading');
const searchResults = document.getElementById('search-results');
const selectedInfo  = document.getElementById('selected-card-info');
const addCardForm   = document.getElementById('add-card-form');
const variantSelect = document.getElementById('add-variant');
const btnBackSearch = document.getElementById('btn-back-search');

const btnShowUrlMode  = document.getElementById('btn-show-url-mode');
const btnBackToSearch = document.getElementById('btn-back-to-search');
const cmUrlInput      = document.getElementById('cm-url-input');
const btnFetchUrl     = document.getElementById('btn-fetch-url');
const urlLoading      = document.getElementById('url-loading');
const urlError        = document.getElementById('url-error');

let selectedCard = null;

function openAddModal() {
  selectedCard = null;
  stepSearch.classList.remove('hidden');
  stepUrl.classList.add('hidden');
  stepForm.classList.add('hidden');
  searchInput.value = '';
  searchResults.innerHTML = '';
  cmUrlInput.value = '';
  urlError.classList.add('hidden');
  urlError.textContent = '';
  modalOverlay.classList.remove('hidden');
  setTimeout(() => searchInput.focus(), 50);
}

function closeModal() {
  modalOverlay.classList.add('hidden');
}

modalClose.addEventListener('click', closeModal);
modalOverlay.addEventListener('click', e => {
  if (e.target === modalOverlay) closeModal();
});

btnBackSearch.addEventListener('click', () => {
  stepForm.classList.add('hidden');
  stepSearch.classList.remove('hidden');
});

// ── Toggle URL mode ──────────────────────────────────────────────
btnShowUrlMode.addEventListener('click', () => {
  stepSearch.classList.add('hidden');
  stepUrl.classList.remove('hidden');
  urlError.classList.add('hidden');
  urlError.textContent = '';
  setTimeout(() => cmUrlInput.focus(), 50);
});

btnBackToSearch.addEventListener('click', () => {
  stepUrl.classList.add('hidden');
  stepSearch.classList.remove('hidden');
});

// ── Search ───────────────────────────────────────────────────────
async function runSearch() {
  const q = searchInput.value.trim();
  if (q.length < 2) return;

  searchLoading.classList.remove('hidden');
  searchResults.innerHTML = '';

  try {
    const results = await apiFetch(`/search?q=${encodeURIComponent(q)}`);
    renderSearchResults(results);
  } catch (err) {
    searchResults.innerHTML = `<p class="text-muted" style="padding:0.75rem 0">Error: ${err.message}</p>`;
  } finally {
    searchLoading.classList.add('hidden');
  }
}

btnSearch.addEventListener('click', runSearch);
searchInput.addEventListener('keydown', e => { if (e.key === 'Enter') runSearch(); });

function renderSearchResults(results) {
  if (!results.length) {
    searchResults.innerHTML = '<p class="text-muted" style="padding:0.75rem 0">No results found.</p>';
    return;
  }

  searchResults.innerHTML = results.map(r => `
    <div class="search-result-item" data-id="${r.api_id}">
      <span class="card-name">${r.name}</span>
      <span class="card-meta">
        ${r.set_name || ''}${r.set_code ? ` (${r.set_code})` : ''}
        ${r.card_number ? ` · #${r.card_number}` : ''}
        ${r.rarity ? ` · ${r.rarity}` : ''}
      </span>
    </div>
  `).join('');

  searchResults._results = results;

  searchResults.querySelectorAll('.search-result-item').forEach(el => {
    el.addEventListener('click', () => {
      const card = searchResults._results.find(r => r.api_id === el.dataset.id);
      if (card) pickCard(card);
    });
  });
}

// ── Fetch by CardMarket URL ───────────────────────────────────────
async function fetchByUrl() {
  const raw = cmUrlInput.value.trim();
  if (!raw) return;

  try {
    await requireAuth();
  } catch (_) { return; }

  urlLoading.classList.remove('hidden');
  urlError.classList.add('hidden');
  urlError.textContent = '';
  btnFetchUrl.disabled = true;

  try {
    const card = await apiFetch('/cards/manual', {
      method: 'POST',
      body: JSON.stringify({ url: raw }),
    });
    stepUrl.classList.add('hidden');
    pickCard(card);
  } catch (err) {
    urlError.textContent = err.message || 'Failed to fetch card from CardMarket.';
    urlError.classList.remove('hidden');
  } finally {
    urlLoading.classList.add('hidden');
    btnFetchUrl.disabled = false;
  }
}

btnFetchUrl.addEventListener('click', fetchByUrl);
cmUrlInput.addEventListener('keydown', e => { if (e.key === 'Enter') fetchByUrl(); });

// ── Pick card → show add form ────────────────────────────────────
async function pickCard(card) {
  selectedCard = card;

  selectedInfo.querySelector('.selected-card-name').textContent = card.name;
  selectedInfo.querySelector('.selected-card-meta').textContent = [
    card.set_name || '',
    card.set_code ? `(${card.set_code})` : '',
    card.card_number ? `#${card.card_number}` : '',
    card.rarity || '',
    card.source === 'pricecharting_scrape' ? '• PriceCharting' : '',
  ].filter(Boolean).join(' · ');

  // Show the track_price row only in collection_only mode
  const trackPriceRow = document.getElementById('add-track-price-row');
  if (trackPriceRow) {
    trackPriceRow.style.display =
      window.appSettings?.pricing_mode === 'collection_only' ? '' : 'none';
  }

  // Populate variant dropdown from price API
  variantSelect.innerHTML = '<option value="">— select —</option>';
  try {
    const prices = await apiFetch(`/prices/${card.api_id}`);
    const variants = [...new Set(prices.map(p => p.variant_type))];
    variants.forEach(v => {
      const opt = document.createElement('option');
      opt.value = v;
      opt.textContent = v;
      variantSelect.appendChild(opt);
    });
    if (variants.length === 1) variantSelect.value = variants[0];
  } catch (_) {
    ['normal', 'holo', 'Holofoil', 'Reverse Holofoil'].forEach(v => {
      const opt = document.createElement('option');
      opt.value = v;
      opt.textContent = v;
      variantSelect.appendChild(opt);
    });
  }

  stepSearch.classList.add('hidden');
  stepUrl.classList.add('hidden');
  stepForm.classList.remove('hidden');
}

// ── Submit add form ──────────────────────────────────────────────
addCardForm.addEventListener('submit', async e => {
  e.preventDefault();
  if (!selectedCard) return;

  const f = addCardForm.elements;
  const body = {
    card_api_id:       selectedCard.api_id,
    quantity:          parseInt(f.quantity.value, 10),
    condition:         f.condition.value,
    language:          f.language.value,
    variant:           f.variant.value || null,
    purchase_price:    f.purchase_price.value ? parseFloat(f.purchase_price.value) : null,
    purchase_currency: 'EUR',
    date_acquired:     f.date_acquired.value || null,
    notes:             f.notes.value || null,
    for_trade:         f.for_trade?.checked || false,
    track_price:       f.track_price?.checked || false,
  };

  try {
    await requireAuth();
    await apiFetch('/collection', { method: 'POST', body: JSON.stringify(body) });
    toast(`${selectedCard.name} added to collection`);
    closeModal();
    loadCollection();
    // If a set detail is open, refresh it so the card's ownership status updates
    if (typeof _currentSet !== 'undefined' && _currentSet) openSetDetail(_currentSet);
  } catch (err) {
    if (err.message !== 'Login cancelled') toast(`Error: ${err.message}`, 'error');
  }
});
