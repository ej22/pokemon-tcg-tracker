/* ── Sets browser ─────────────────────────────────────────────── */

const setsLoading     = document.getElementById('sets-loading');
const setsEmpty       = document.getElementById('sets-empty');
const setsGrid        = document.getElementById('sets-grid');
const setDetail       = document.getElementById('set-detail');
const setDetailTitle  = document.getElementById('set-detail-title');
const setCardsLoading = document.getElementById('set-cards-loading');
const setCardsGrid    = document.getElementById('set-cards-grid');
const btnBackSets     = document.getElementById('btn-back-sets');

async function loadSets() {
  setsLoading.classList.remove('hidden');
  setsGrid.classList.add('hidden');
  setsEmpty.classList.add('hidden');
  setDetail.classList.add('hidden');

  try {
    const sets = await apiFetch('/sets/mine');
    renderSetsGrid(sets);
  } catch (e) {
    toast(`Failed to load sets: ${e.message}`, 'error');
  } finally {
    setsLoading.classList.add('hidden');
  }
}

function setPlaceholder(label) {
  return `<div class="poster-placeholder"><div class="poster-placeholder-icon">${label.slice(0, 2)}</div></div>`;
}

function renderSetsGrid(sets) {
  if (!sets.length) {
    setsEmpty.classList.remove('hidden');
    return;
  }

  const subtitle = document.getElementById('sets-subtitle');
  if (subtitle) subtitle.textContent = `${sets.length} set${sets.length === 1 ? '' : 's'} in your collection`;

  setsGrid.innerHTML = sets.map(s => {
    const code      = s.set_code || String(s.set_id);
    const imageUrl  = `/api/sets/${code}/image`;
    const relDate   = s.release_date ? s.release_date.slice(0, 10) : '';

    return `
      <div class="poster-card set-poster" data-id="${s.set_id}" role="button" tabindex="0"
           aria-label="${s.name}"
           onclick="openSetDetail(${JSON.stringify(s).replace(/"/g, '&quot;')})"
           onkeydown="if(event.key==='Enter')openSetDetail(${JSON.stringify(s).replace(/"/g, '&quot;')})">
        <img src="${imageUrl}" alt="${s.name}" onerror="this.parentElement.innerHTML=setPlaceholder('${code}')">

        <div class="poster-badges">
          <span class="poster-qty-badge">${s.owned_count} owned</span>
          ${code ? `<span class="poster-set-code">${code}</span>` : ''}
        </div>

        <div class="poster-overlay">
          <div class="poster-name">${s.name}</div>
          <div class="poster-meta">
            <span>${relDate}</span>
            <span>${s.card_count ? `${s.card_count} cards` : ''}</span>
          </div>
        </div>
      </div>`;
  }).join('');

  setsGrid.classList.remove('hidden');
}

async function openSetDetail(set) {
  setsGrid.classList.add('hidden');
  setDetail.classList.remove('hidden');
  setDetailTitle.textContent = `${set.name}${set.set_code ? ` (${set.set_code})` : ''}`;
  setCardsGrid.innerHTML = Array.from({ length: 12 }, () =>
    `<div class="poster-skeleton skeleton"></div>`
  ).join('');
  setCardsLoading.classList.add('hidden');

  try {
    const cards = await apiFetch(`/sets/${set.set_id}/cards`);
    renderSetCards(cards);
  } catch (e) {
    toast(`Failed to load set cards: ${e.message}`, 'error');
  }
}

function renderSetCards(cards) {
  if (!cards.length) {
    setCardsGrid.innerHTML = `
      <div style="grid-column:1/-1;text-align:center;padding:3rem 2rem;font-size:0.825rem;color:var(--text-subtle)">
        No cards cached for this set yet.
      </div>`;
    return;
  }

  setCardsGrid.innerHTML = cards.map(c => {
    const imageUrl  = `/api/images/${c.api_id}`;
    const cardJson  = JSON.stringify(c).replace(/"/g, '&quot;');
    const rarityBadge = c.rarity
      ? `<span class="chip chip-default" style="font-size:0.6rem;padding:0.1rem 0.35rem;backdrop-filter:blur(6px);background:rgba(0,0,0,0.55);border-color:rgba(255,255,255,0.15);color:#fff">${c.rarity}</span>`
      : '';

    return `
      <div class="poster-card set-poster-card">
        <img src="${imageUrl}" alt="${c.name}" onerror="this.parentElement.innerHTML=cardPlaceholder()">

        <div class="poster-badges">
          ${rarityBadge}
        </div>

        <div class="poster-actions" onclick="event.stopPropagation()">
          <button class="poster-action-btn poster-action-add" title="Add to collection"
            onclick="addCardFromSet(${cardJson})">
            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" d="M12 4.5v15m7.5-7.5h-15" /></svg>
          </button>
        </div>

        <div class="poster-overlay">
          <div class="poster-name">${c.name}</div>
          <div class="poster-meta">
            <span class="poster-card-number">${c.card_number || ''}</span>
            ${c.hp ? `<span>HP ${c.hp}</span>` : ''}
          </div>
        </div>
      </div>`;
  }).join('');
}

function addCardFromSet(card) {
  pickCard({
    api_id:      card.api_id,
    name:        card.name,
    set_name:    '',
    set_code:    card.set_code || '',
    card_number: card.card_number || '',
    rarity:      card.rarity || '',
  });
  modalOverlay.classList.remove('hidden');
}

btnBackSets.addEventListener('click', () => {
  setDetail.classList.add('hidden');
  setsGrid.classList.remove('hidden');
});
