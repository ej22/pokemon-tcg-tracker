/* ── Sets browser ─────────────────────────────────────────────── */

const setsLoading   = document.getElementById('sets-loading');
const setsEmpty     = document.getElementById('sets-empty');
const setsGrid      = document.getElementById('sets-grid');
const setDetail     = document.getElementById('set-detail');
const setDetailTitle = document.getElementById('set-detail-title');
const setCardsLoading = document.getElementById('set-cards-loading');
const setCardsTbody = document.getElementById('set-cards-tbody');
const btnBackSets   = document.getElementById('btn-back-sets');

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

  setsGrid.innerHTML = sets.map(s => `
    <div class="set-card" data-id="${s.set_id}">
      <div class="set-name">${s.name}</div>
      <div class="set-meta">
        ${s.set_code ? `${s.set_code} · ` : ''}
        ${s.card_count} cards
        ${s.release_date ? ` · ${s.release_date.slice(0,10)}` : ''}
        ${s.language ? ` · ${s.language}` : ''}
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
    renderSetCards(cards, set);
  } catch (e) {
    toast(`Failed to load set cards: ${e.message}`, 'error');
  } finally {
    setCardsLoading.classList.add('hidden');
  }
}

function renderSetCards(cards, set) {
  if (!cards.length) {
    setCardsTbody.innerHTML = '<tr><td colspan="6" class="text-muted" style="text-align:center;padding:2rem">No cards cached for this set.</td></tr>';
    return;
  }

  setCardsTbody.innerHTML = cards.map(c => `
    <tr>
      <td>${c.card_number || '—'}</td>
      <td><strong>${c.name}</strong></td>
      <td>${c.rarity || '—'}</td>
      <td>${c.card_type || '—'}</td>
      <td>${c.hp || '—'}</td>
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
  // Pre-fill the search modal with this card directly
  pickCard({
    api_id:     card.api_id,
    name:       card.name,
    set_name:   '',
    set_code:   card.set_code || '',
    card_number: card.card_number || '',
    rarity:     card.rarity || '',
  });
  modalOverlay.classList.remove('hidden');
}

btnBackSets.addEventListener('click', () => {
  setDetail.classList.add('hidden');
  setsGrid.classList.remove('hidden');
});
