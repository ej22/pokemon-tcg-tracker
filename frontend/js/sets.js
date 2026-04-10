/* ── Sets browser ─────────────────────────────────────────────── */

const setsLoading    = document.getElementById('sets-loading');
const setsEmpty      = document.getElementById('sets-empty');
const setsGrid       = document.getElementById('sets-grid');
const setDetail      = document.getElementById('set-detail');
const setDetailTitle = document.getElementById('set-detail-title');
const setCardsLoading = document.getElementById('set-cards-loading');
const setCardsTbody  = document.getElementById('set-cards-tbody');
const btnBackSets    = document.getElementById('btn-back-sets');

async function loadSets() {
  setsLoading.classList.remove('hidden');
  setsGrid.classList.add('hidden');
  setsEmpty.classList.add('hidden');
  setDetail.classList.add('hidden');

  try {
    const sets = await apiFetch('/sets');
    renderSetsGrid(sets);
  } catch (e) {
    toast(`Failed to load sets: ${e.message}`, 'error');
  } finally {
    setsLoading.classList.add('hidden');
  }
}

function renderSetsGrid(sets) {
  if (!sets.length) {
    setsEmpty.classList.remove('hidden');
    return;
  }

  const subtitle = document.getElementById('sets-subtitle');
  if (subtitle) subtitle.textContent = `${sets.length} sets available`;

  setsGrid.innerHTML = sets.map(s => `
    <div class="set-card" data-id="${s.set_id}">
      <div class="set-card-header">
        <span class="set-card-name">${s.name}</span>
        ${s.set_code ? `<span class="chip chip-default" style="font-size:0.7rem;padding:0.15rem 0.45rem">${s.set_code}</span>` : ''}
      </div>
      <div class="set-card-meta">
        ${s.card_count ? `<span>${s.card_count} cards</span>` : ''}
        ${s.release_date ? `<span>${s.release_date.slice(0, 10)}</span>` : ''}
        ${s.language ? `<span>${s.language}</span>` : ''}
      </div>
    </div>
  `).join('');

  setsGrid.classList.remove('hidden');

  setsGrid.querySelectorAll('.set-card').forEach(el => {
    el.addEventListener('click', () => {
      const set = sets.find(s => s.set_id === el.dataset.id);
      if (set) openSetDetail(set);
    });
  });
}

async function openSetDetail(set) {
  setsGrid.classList.add('hidden');
  setDetail.classList.remove('hidden');
  setDetailTitle.textContent = `${set.name}${set.set_code ? ` (${set.set_code})` : ''}`;
  setCardsTbody.innerHTML = '';
  setCardsLoading.classList.remove('hidden');

  try {
    const cards = await apiFetch(`/sets/${set.set_id}/cards`);
    renderSetCards(cards);
  } catch (e) {
    toast(`Failed to load set cards: ${e.message}`, 'error');
  } finally {
    setCardsLoading.classList.add('hidden');
  }
}

function renderSetCards(cards) {
  if (!cards.length) {
    setCardsTbody.innerHTML = `
      <tr>
        <td colspan="6" style="text-align:center;padding:2rem;font-size:0.825rem;color:var(--text-subtle)">
          No cards cached for this set.
        </td>
      </tr>`;
    return;
  }

  setCardsTbody.innerHTML = cards.map(c => `
    <tr>
      <td><span class="cell-mono">${c.card_number || '—'}</span></td>
      <td><strong>${c.name}</strong></td>
      <td>${c.rarity || '<span class="text-muted">—</span>'}</td>
      <td>${c.card_type || '<span class="text-muted">—</span>'}</td>
      <td><span class="cell-mono">${c.hp || '—'}</span></td>
      <td>
        <button class="btn btn-primary btn-sm"
          onclick="addCardFromSet(${JSON.stringify(c).replace(/"/g, '&quot;')})">
          + Add
        </button>
      </td>
    </tr>
  `).join('');
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
