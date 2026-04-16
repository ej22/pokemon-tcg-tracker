/* ── Collection view ──────────────────────────────────────────── */

const collectionGrid  = document.getElementById('collection-grid');
const collectionEmpty = document.getElementById('collection-empty');

// ── View mode (flat grid vs grouped by set) ──────────────────────
let collectionViewMode = localStorage.getItem('collectionViewMode') || 'flat';
let showMissingCards   = localStorage.getItem('showMissingCards') !== 'false';
let reorderMode             = false;
let _lastEntries            = null;
let _dragSrcEl              = null;
let _savedCollapseStates    = null;

function setCollectionViewMode(mode) {
  collectionViewMode = mode;
  localStorage.setItem('collectionViewMode', mode);
  const iconGrouped = document.getElementById('view-icon-grouped');
  const iconGrid    = document.getElementById('view-icon-grid');
  if (iconGrouped && iconGrid) {
    iconGrouped.classList.toggle('hidden', mode === 'grouped');
    iconGrid.classList.toggle('hidden', mode === 'flat');
  }
  const btn = document.getElementById('btn-toggle-view');
  if (btn) btn.classList.toggle('active', mode === 'grouped');
  // Show reorder button only in grouped mode; exit reorder mode when leaving grouped
  const reorderBtn = document.getElementById('btn-reorder-sets');
  if (reorderBtn) reorderBtn.classList.toggle('hidden', mode !== 'grouped');
  if (mode !== 'grouped' && reorderMode) {
    reorderMode = false;
    _savedCollapseStates = null;
    if (reorderBtn) reorderBtn.classList.remove('active');
  }
}

function setReorderMode(active) {
  reorderMode = active;
  const btn = document.getElementById('btn-reorder-sets');
  if (btn) btn.classList.toggle('active', active);

  if (active) {
    // Snapshot current collapse states from the DOM before re-render
    _savedCollapseStates = {};
    collectionGrid.querySelectorAll('.set-group').forEach(g => {
      _savedCollapseStates[g.dataset.setId] = g.classList.contains('collapsed');
    });
  }

  // Re-render to add/remove drag handles, draggable attrs, and move buttons
  if (_lastEntries && collectionViewMode === 'grouped') {
    renderCollection(_lastEntries);
  }

  // Manipulate collapse state directly in the DOM after re-render — more
  // reliable than trying to communicate via localStorage through the render cycle
  if (active) {
    collectionGrid.querySelectorAll('.set-group').forEach(g => {
      g.classList.add('collapsed');
      g.querySelector('.set-group-header')?.setAttribute('aria-expanded', 'false');
    });
  } else if (_savedCollapseStates) {
    collectionGrid.querySelectorAll('.set-group').forEach(g => {
      const wasCollapsed = _savedCollapseStates[g.dataset.setId] ?? false;
      g.classList.toggle('collapsed', wasCollapsed);
      g.querySelector('.set-group-header')?.setAttribute('aria-expanded', String(!wasCollapsed));
    });
    _savedCollapseStates = null;
  }
}

function moveSetGroup(setId, direction) {
  const currentOrder = JSON.parse(localStorage.getItem('setGroupOrder') || 'null')
    || [...collectionGrid.querySelectorAll('.set-group')].map(g => g.dataset.setId);
  const idx = currentOrder.indexOf(setId);
  if (idx < 0) return;
  const newIdx = idx + direction;
  if (newIdx < 0 || newIdx >= currentOrder.length) return;
  const newOrder = [...currentOrder];
  [newOrder[idx], newOrder[newIdx]] = [newOrder[newIdx], newOrder[idx]];
  localStorage.setItem('setGroupOrder', JSON.stringify(newOrder));
  if (_lastEntries) renderCollection(_lastEntries);
}

function saveSetGroupOrder() {
  const order = [...collectionGrid.querySelectorAll('.set-group')].map(g => g.dataset.setId);
  localStorage.setItem('setGroupOrder', JSON.stringify(order));
}

function initSetGroupDragDrop() {
  const groups = [...collectionGrid.querySelectorAll('.set-group[draggable="true"]')];

  groups.forEach(group => {
    group.addEventListener('dragstart', e => {
      _dragSrcEl = group;
      requestAnimationFrame(() => group.classList.add('dragging'));
      e.dataTransfer.effectAllowed = 'move';
    });

    group.addEventListener('dragend', () => {
      _dragSrcEl = null;
      collectionGrid.querySelectorAll('.set-group').forEach(g =>
        g.classList.remove('dragging', 'drag-over-top', 'drag-over-bottom')
      );
      saveSetGroupOrder();
    });

    group.addEventListener('dragover', e => {
      e.preventDefault();
      e.dataTransfer.dropEffect = 'move';
      if (!_dragSrcEl || _dragSrcEl === group) return;

      collectionGrid.querySelectorAll('.set-group').forEach(g =>
        g.classList.remove('drag-over-top', 'drag-over-bottom')
      );

      const rect = group.getBoundingClientRect();
      const isAfter = e.clientY > rect.top + rect.height / 2;
      group.classList.add(isAfter ? 'drag-over-bottom' : 'drag-over-top');

      if (isAfter) {
        collectionGrid.insertBefore(_dragSrcEl, group.nextSibling);
      } else {
        collectionGrid.insertBefore(_dragSrcEl, group);
      }
    });
  });
}

function applyMissingFilter() {
  collectionGrid.querySelectorAll('.poster-card--missing').forEach(el => {
    el.style.display = showMissingCards ? '' : 'none';
  });
  const btn = document.getElementById('btn-toggle-missing');
  if (btn) btn.classList.toggle('missing-hidden', !showMissingCards);
}

document.addEventListener('DOMContentLoaded', () => {
  setCollectionViewMode(collectionViewMode);
  document.getElementById('btn-toggle-view').addEventListener('click', () => {
    setCollectionViewMode(collectionViewMode === 'flat' ? 'grouped' : 'flat');
    loadCollection();
  });

  const btnReorder = document.getElementById('btn-reorder-sets');
  if (btnReorder) {
    btnReorder.addEventListener('click', async () => {
      try {
        await requireAuth();
        setReorderMode(!reorderMode);
      } catch (_) {}
    });
  }

  const btnMissing = document.getElementById('btn-toggle-missing');
  if (btnMissing) {
    btnMissing.addEventListener('click', () => {
      showMissingCards = !showMissingCards;
      localStorage.setItem('showMissingCards', showMissingCards);
      applyMissingFilter();
    });
  }
});

async function loadCollection() {
  showSkeletonCards();
  try {
    const entries = await apiFetch('/collection');
    _lastEntries = entries;
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

// Determine whether to show pricing for a given entry
function entryPricingOn(e) {
  const mode = window.appSettings?.pricing_mode;
  if (mode !== 'collection_only') return true;
  // In collection_only mode, show pricing when explicitly enabled
  return e.track_price === true || e.for_trade === true;
}

function renderPosterCard(e) {
  const isMissing  = e.quantity === 0;
  const pricingOn  = !isMissing && entryPricingOn(e);
  const price      = pricingOn ? bestPrice(e.prices, e.variant) : null;
  const priceStr   = price != null ? `€${parseFloat(price).toFixed(2)}` : null;
  const imageUrl   = `/api/images/${e.card.api_id}`;
  const entryJson  = JSON.stringify(e).replace(/"/g, '&quot;');
  const qty        = e.quantity > 1 ? `<span class="poster-qty-badge">×${e.quantity}</span>` : '';

  let pnlDot = '';
  if (pricingOn && e.purchase_price != null && price != null) {
    const diff = parseFloat(price) - parseFloat(e.purchase_price);
    pnlDot = diff >= 0
      ? `<span class="poster-pnl-dot pnl-pos" title="+€${diff.toFixed(2)}"></span>`
      : `<span class="poster-pnl-dot pnl-neg" title="€${diff.toFixed(2)}"></span>`;
  }

  const isScraped  = e.card.source === 'pricecharting_scrape';
  const isStale    = pricingOn && isScraped && isPriceStale(e.prices);
  const pcBadge    = (pricingOn && isScraped) ? `<span class="chip chip-cm" title="Price from PriceCharting (USD→EUR)">PC</span>` : '';
  const staleBadge = isStale ? `<span class="chip chip-stale" title="Price may be outdated">Stale</span>` : '';
  const tradeBadge = e.for_trade ? `<span class="chip chip-trade" title="In Trade Binder">TRADE</span>` : '';

  const priceRow = pricingOn
    ? `<span class="poster-price-row">${pnlDot}${priceStr ? `<span class="poster-price">${priceStr}</span>` : '<span class="poster-no-price">—</span>'}</span>`
    : '';

  const isCollOnly = window.appSettings?.pricing_mode === 'collection_only';

  // Track price button — shown in collection_only mode (unless for_trade, which already implies tracking)
  const trackBtn = isCollOnly && !e.for_trade ? `
    <button class="poster-action-btn poster-action-track${e.track_price ? ' active' : ''}"
      title="${e.track_price ? 'Stop tracking price' : 'Track price'}"
      onclick="toggleTrackPrice(event, ${e.id}, ${e.track_price})">
      <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.75" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" d="M11.48 3.499a.562.562 0 0 1 1.04 0l2.125 5.111a.563.563 0 0 0 .475.345l5.518.442c.499.04.701.663.321.988l-4.204 3.602a.563.563 0 0 0-.182.557l1.285 5.385a.562.562 0 0 1-.84.61l-4.725-2.885a.562.562 0 0 0-.586 0L6.982 20.54a.562.562 0 0 1-.84-.61l1.285-5.386a.562.562 0 0 0-.182-.557l-4.204-3.601a.562.562 0 0 1 .321-.988l5.518-.442a.563.563 0 0 0 .475-.345L11.48 3.5Z" /></svg>
    </button>` : '';

  // Trade button — always visible
  const tradeBtn = `
    <button class="poster-action-btn poster-action-trade${e.for_trade ? ' active' : ''}"
      title="${e.for_trade ? 'Remove from Trade Binder' : 'Add to Trade Binder'}"
      onclick="toggleForTrade(event, ${e.id}, ${e.for_trade})">
      <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.75" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" d="M7.5 21 3 16.5m0 0L7.5 12M3 16.5h13.5m0-13.5L21 7.5m0 0L16.5 12M21 7.5H7.5" /></svg>
    </button>`;

  const missingBadge = isMissing ? `<span class="poster-missing-badge">Missing</span>` : '';
  const cardClasses  = ['poster-card', isMissing ? 'poster-card--missing' : ''].filter(Boolean).join(' ');

  return `
    <div class="${cardClasses}" role="button" tabindex="0"
         aria-label="${e.card.name}"
         data-entry="${entryJson}"
         onkeydown="if(event.key==='Enter')openCardView(JSON.parse(this.dataset.entry))">
      <img src="${imageUrl}" alt="${e.card.name}" onerror="this.style.display='none';this.parentElement.insertAdjacentHTML('afterbegin',cardPlaceholder())">
      ${missingBadge}

      <div class="poster-badges">
        ${isMissing ? '' : conditionChip(e.condition)}
        ${qty}
        ${pcBadge}
        ${staleBadge}
        ${tradeBadge}
      </div>

      <div class="poster-actions" onclick="event.stopPropagation()">
        ${trackBtn}
        ${tradeBtn}
        <button class="poster-action-btn poster-action-edit" title="Edit"
          onclick="openEditModal(JSON.parse(this.closest('[data-entry]').dataset.entry))">
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
          ${priceRow}
        </div>
      </div>
    </div>`;
}

function renderCollection(entries) {
  const subtitle = document.getElementById('collection-subtitle');

  // Separate owned from missing (qty=0)
  const owned   = entries.filter(e => e.quantity > 0);
  const missing = entries.filter(e => e.quantity === 0);

  if (subtitle) {
    if (entries.length === 0) {
      subtitle.textContent = 'No cards yet';
    } else {
      const parts = [`${owned.length} entr${owned.length === 1 ? 'y' : 'ies'}`];
      if (missing.length) parts.push(`${missing.length} missing`);
      subtitle.textContent = parts.join(' · ');
    }
  }

  if (!entries.length) {
    collectionGrid.innerHTML = '';
    collectionGrid.classList.add('hidden');
    collectionEmpty.classList.remove('hidden');
    updateSidebarStats(0, null, 0);
    return;
  }

  collectionEmpty.classList.add('hidden');
  collectionGrid.classList.remove('hidden');

  // Show/hide the missing toggle button
  const btnMissing = document.getElementById('btn-toggle-missing');
  if (btnMissing) btnMissing.classList.toggle('hidden', missing.length === 0);

  if (collectionViewMode === 'grouped') {
    collectionGrid.classList.remove('card-grid');
    collectionGrid.classList.add('set-group-stack');
    collectionGrid.classList.toggle('reorder-mode', reorderMode);
    renderCollectionGrouped(entries);
  } else {
    collectionGrid.classList.remove('set-group-stack', 'reorder-mode');
    collectionGrid.classList.add('card-grid');
    renderCollectionFlat(entries);
  }
}

function renderCollectionFlat(entries) {
  const isCollOnly = window.appSettings?.pricing_mode === 'collection_only';
  let totalValue = 0;
  let totalCards = 0;
  let missingCount = 0;

  collectionGrid.innerHTML = entries.map(e => {
    if (e.quantity === 0) {
      missingCount++;
    } else {
      const pricingOn = entryPricingOn(e);
      const price = pricingOn ? bestPrice(e.prices, e.variant) : null;
      if (price != null) totalValue += parseFloat(price) * e.quantity;
      totalCards += e.quantity;
    }
    return renderPosterCard(e);
  }).join('');

  const showValue = !isCollOnly && totalValue > 0
    ? totalValue
    : (isCollOnly && totalValue > 0 ? totalValue : null);

  updateSidebarStats(totalCards, showValue, missingCount);
  applyMissingFilter();
}

function renderCollectionGrouped(entries) {
  const isCollOnly = window.appSettings?.pricing_mode === 'collection_only';
  let totalValue = 0;
  let totalCards = 0;
  let totalMissing = 0;

  // Group by set_id
  const groups = new Map();
  for (const e of entries) {
    const key = e.card.set_id || '__other__';
    if (!groups.has(key)) {
      groups.set(key, {
        setName:      e.card.set_name || (e.card.set_code ? e.card.set_code : 'Other'),
        setCardCount: e.card.set_card_count || 0,
        entries:      [],
      });
    }
    groups.get(key).entries.push(e);
  }

  // Sort groups: respect saved order, alphabetical for new groups
  const savedOrder = JSON.parse(localStorage.getItem('setGroupOrder') || 'null');
  let sorted;
  if (savedOrder && savedOrder.length > 0) {
    const orderMap = new Map(savedOrder.map((id, i) => [id, i]));
    sorted = [...groups.entries()].sort((a, b) => {
      const aInOrder = orderMap.has(a[0]);
      const bInOrder = orderMap.has(b[0]);
      if (aInOrder && bInOrder) return orderMap.get(a[0]) - orderMap.get(b[0]);
      if (aInOrder) return -1;
      if (bInOrder) return 1;
      return a[1].setName.localeCompare(b[1].setName);
    });
  } else {
    sorted = [...groups.entries()].sort((a, b) =>
      a[1].setName.localeCompare(b[1].setName)
    );
  }

  const htmlParts = sorted.map(([setId, group], idx) => {
    let groupValue = 0;

    const cardsHtml = group.entries.map(e => {
      if (e.quantity > 0) {
        const pricingOn = entryPricingOn(e);
        const price = pricingOn ? bestPrice(e.prices, e.variant) : null;
        if (price != null) {
          groupValue += parseFloat(price) * e.quantity;
          totalValue += parseFloat(price) * e.quantity;
        }
        totalCards += e.quantity;
      } else {
        totalMissing++;
      }
      return renderPosterCard(e);
    }).join('');

    const ownedCount   = group.entries.filter(e => e.quantity > 0).reduce((s, e) => s + e.quantity, 0);
    const missingCount = group.entries.filter(e => e.quantity === 0).length;
    const totalInSet   = group.setCardCount;

    let countLabel;
    if (missingCount > 0 && totalInSet > 0) {
      countLabel = `${ownedCount} owned · ${missingCount} missing / ${totalInSet} total`;
    } else if (missingCount > 0) {
      countLabel = `${ownedCount} owned · ${missingCount} missing`;
    } else if (totalInSet > 0) {
      countLabel = `${ownedCount} / ${totalInSet} cards`;
    } else {
      countLabel = `${ownedCount} card${ownedCount !== 1 ? 's' : ''}`;
    }

    const valueLabel = groupValue > 0
      ? `<span class="set-group-value">€${groupValue.toFixed(2)}</span>`
      : '';

    const layout = window.appSettings?.grouped_layout || 'horizontal';
    const bodyClass = layout === 'horizontal' ? 'set-group-body set-group-row' : 'set-group-body card-grid';
    const collapsed = localStorage.getItem(`setGroup_${setId}`) === 'collapsed';

    const isFirst = idx === 0;
    const isLast  = idx === sorted.length - 1;

    const dragHandle = reorderMode ? `
      <span class="set-group-drag-handle" title="Drag to reorder">
        <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" d="M3.75 9h16.5m-16.5 6.75h16.5" /></svg>
      </span>` : '';

    const moveBtns = reorderMode ? `
      <div class="set-group-reorder-btns">
        <button class="set-group-move-btn" title="Move up"${isFirst ? ' disabled' : ''}
          onclick="event.stopPropagation();moveSetGroup('${setId}', -1)">
          <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2.5" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" d="m4.5 15.75 7.5-7.5 7.5 7.5" /></svg>
        </button>
        <button class="set-group-move-btn" title="Move down"${isLast ? ' disabled' : ''}
          onclick="event.stopPropagation();moveSetGroup('${setId}', 1)">
          <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2.5" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" d="m19.5 8.25-7.5 7.5-7.5-7.5" /></svg>
        </button>
      </div>` : '';

    const draggable = reorderMode ? ' draggable="true"' : '';

    return `
      <div class="set-group${collapsed ? ' collapsed' : ''}" data-set-id="${setId}"${draggable}>
        <div class="set-group-header-row">
          ${dragHandle}
          <button class="set-group-header" aria-expanded="${!collapsed}">
            <span class="set-group-chevron">
              <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2.5" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" d="m19.5 8.25-7.5 7.5-7.5-7.5" /></svg>
            </span>
            <span class="set-group-name">${group.setName}</span>
            <span class="set-group-meta">${valueLabel}<span class="set-group-count">${countLabel}</span></span>
          </button>
          ${moveBtns}
        </div>
        <div class="${bodyClass}">${cardsHtml}</div>
      </div>`;
  });

  collectionGrid.innerHTML = htmlParts.join('');

  collectionGrid.querySelectorAll('.set-group-header').forEach(btn => {
    btn.addEventListener('click', e => {
      e.stopPropagation();
      const group = btn.closest('.set-group');
      const collapsed = group.classList.toggle('collapsed');
      btn.setAttribute('aria-expanded', !collapsed);
      const setId = group.dataset.setId;
      if (collapsed) {
        localStorage.setItem(`setGroup_${setId}`, 'collapsed');
      } else {
        localStorage.removeItem(`setGroup_${setId}`);
      }
    });
  });

  if (reorderMode) initSetGroupDragDrop();

  const showValue = totalValue > 0 ? totalValue : null;
  updateSidebarStats(totalCards, showValue, totalMissing);
  applyMissingFilter();
}

function cardPlaceholder() {
  return `<div class="poster-placeholder"><div class="poster-placeholder-icon">P</div></div>`;
}

// ── Track price toggle ───────────────────────────────────────────
async function toggleTrackPrice(event, id, currentValue) {
  event.stopPropagation();
  try {
    await requireAuth();
    await apiFetch(`/collection/${id}`, {
      method: 'PUT',
      body: JSON.stringify({ track_price: !currentValue }),
    });
    toast(!currentValue ? 'Price tracking enabled' : 'Price tracking disabled');
    loadCollection();
  } catch (e) {
    if (e.message !== 'Login cancelled') toast(`Error: ${e.message}`, 'error');
  }
}

// ── For trade toggle ─────────────────────────────────────────────
async function toggleForTrade(event, id, currentValue) {
  event.stopPropagation();
  try {
    await requireAuth();
    await apiFetch(`/collection/${id}`, {
      method: 'PUT',
      body: JSON.stringify({ for_trade: !currentValue }),
    });
    toast(!currentValue ? 'Added to Trade Binder' : 'Removed from Trade Binder');
    loadCollection();
  } catch (e) {
    if (e.message !== 'Login cancelled') toast(`Error: ${e.message}`, 'error');
  }
}

async function deleteEntry(id) {
  if (!confirm('Remove this card from your collection?')) return;
  try {
    await requireAuth();
    await apiFetch(`/collection/${id}`, { method: 'DELETE' });
    toast('Card removed');
    loadCollection();
  } catch (e) {
    if (e.message !== 'Login cancelled') toast(`Error: ${e.message}`, 'error');
  }
}

// ── Edit Modal ───────────────────────────────────────────────────
const editOverlay    = document.getElementById('edit-modal-overlay');
const editForm       = document.getElementById('edit-card-form');
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
  f.for_trade.checked     = entry.for_trade || false;

  const isCollOnly = window.appSettings?.pricing_mode === 'collection_only';
  const trackRow = document.getElementById('edit-track-price-row');
  if (trackRow) {
    trackRow.classList.toggle('hidden', !isCollOnly);
    if (isCollOnly) f.track_price.checked = entry.track_price || false;
  }

  editOverlay.classList.remove('hidden');
}

editModalClose.addEventListener('click', () => editOverlay.classList.add('hidden'));
editOverlay.addEventListener('click', e => {
  if (e.target === editOverlay) editOverlay.classList.add('hidden');
});

editForm.addEventListener('submit', async e => {
  e.preventDefault();
  const f  = editForm.elements;
  const id = f.entry_id.value;

  const body = {
    quantity:       parseInt(f.quantity.value, 10),
    condition:      f.condition.value,
    language:       f.language.value,
    variant:        f.variant.value || null,
    purchase_price: f.purchase_price.value ? parseFloat(f.purchase_price.value) : null,
    date_acquired:  f.date_acquired.value || null,
    notes:          f.notes.value || null,
    for_trade:      f.for_trade.checked,
  };

  const isCollOnly = window.appSettings?.pricing_mode === 'collection_only';
  if (isCollOnly) body.track_price = f.track_price.checked;

  try {
    await requireAuth();
    await apiFetch(`/collection/${id}`, { method: 'PUT', body: JSON.stringify(body) });
    toast('Entry updated');
    editOverlay.classList.add('hidden');
    loadCollection();
  } catch (e) {
    if (e.message !== 'Login cancelled') toast(`Error: ${e.message}`, 'error');
  }
});

document.getElementById('btn-add-card').addEventListener('click', async () => {
  try {
    await requireAuth();
    openAddModal();
  } catch (_) {}
});

// ── Card View Overlay ────────────────────────────────────────────
const cardViewOverlay = document.getElementById('card-view-overlay');
let _cardViewEntry = null;

function openCardView(entry) {
  document.querySelectorAll('.poster-card.tapped').forEach(c => c.classList.remove('tapped'));
  _cardViewEntry = entry;

  document.getElementById('card-view-img').src = `/api/images/${entry.card.api_id}`;
  document.getElementById('card-view-img').alt = entry.card.name;
  document.getElementById('card-view-name').textContent = entry.card.name;

  const setMeta = [entry.card.set_name || entry.card.set_code, entry.card.card_number]
    .filter(Boolean).join(' · ');
  document.getElementById('card-view-set').textContent = setMeta;

  // Chips
  const chips = [
    entry.quantity === 0 ? `<span class="chip chip-default" style="color:var(--text-muted)">Missing</span>` : conditionChip(entry.condition),
    entry.language && entry.language !== 'English'
      ? `<span class="chip chip-default">${entry.language}</span>` : '',
    entry.variant
      ? `<span class="chip chip-default">${entry.variant}</span>` : '',
    entry.quantity > 1
      ? `<span class="chip chip-default">×${entry.quantity}</span>` : '',
    entry.card.source === 'pricecharting_scrape'
      ? `<span class="chip chip-cm">PC</span>` : '',
    entry.for_trade
      ? `<span class="chip chip-trade">TRADE</span>` : '',
  ].filter(Boolean).join('');
  document.getElementById('card-view-chips').innerHTML = chips;

  // Price row — show if pricing is on for this entry
  const pricingOn = entry.quantity > 0 && entryPricingOn(entry);
  const price = pricingOn ? bestPrice(entry.prices, entry.variant) : null;
  const priceEl = document.getElementById('card-view-price-row');
  if (price != null) {
    priceEl.innerHTML = `<span class="card-view-price-label">Market price</span><span class="card-view-price-value">€${parseFloat(price).toFixed(2)}</span>`;
    priceEl.classList.remove('hidden');
  } else {
    priceEl.classList.add('hidden');
  }

  // Purchase info
  const purchaseEl = document.getElementById('card-view-purchase');
  if (entry.purchase_price != null && entry.quantity > 0) {
    const purchaseStr = `€${parseFloat(entry.purchase_price).toFixed(2)}`;
    let pnl = '';
    if (price != null) {
      const diff = parseFloat(price) - parseFloat(entry.purchase_price);
      const sign = diff >= 0 ? '+' : '';
      const cls  = diff >= 0 ? 'card-view-pnl-pos' : 'card-view-pnl-neg';
      pnl = `<span class="${cls}">${sign}€${diff.toFixed(2)}</span>`;
    }
    purchaseEl.innerHTML = `<span class="card-view-price-label">Purchased for</span><span class="card-view-price-value">${purchaseStr} ${pnl}</span>`;
    purchaseEl.classList.remove('hidden');
  } else {
    purchaseEl.classList.add('hidden');
  }

  // Toggle row — track price & for trade
  const toggleRow = document.getElementById('card-view-toggle-row');
  if (toggleRow) {
    const isCollOnly = window.appSettings?.pricing_mode === 'collection_only';
    const isMissing  = entry.quantity === 0;
    let toggleHtml = '';

    // For-trade toggle always available (except missing cards)
    if (!isMissing) {
      toggleHtml += `
        <button class="btn btn-secondary btn-sm" onclick="toggleForTradeFromCardView()">
          <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.75" stroke="currentColor" style="width:1rem;height:1rem"><path stroke-linecap="round" stroke-linejoin="round" d="M7.5 21 3 16.5m0 0L7.5 12M3 16.5h13.5m0-13.5L21 7.5m0 0L16.5 12M21 7.5H7.5" /></svg>
          ${entry.for_trade ? 'Remove from Trade' : 'Add to Trade'}
        </button>`;
    }

    // Track price toggle — only in collection_only mode and only if not for_trade
    if (isCollOnly && !entry.for_trade && !isMissing) {
      toggleHtml += `
        <button class="btn btn-secondary btn-sm" onclick="toggleTrackPriceFromCardView()">
          <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.75" stroke="currentColor" style="width:1rem;height:1rem"><path stroke-linecap="round" stroke-linejoin="round" d="M11.48 3.499a.562.562 0 0 1 1.04 0l2.125 5.111a.563.563 0 0 0 .475.345l5.518.442c.499.04.701.663.321.988l-4.204 3.602a.563.563 0 0 0-.182.557l1.285 5.385a.562.562 0 0 1-.84.61l-4.725-2.885a.562.562 0 0 0-.586 0L6.982 20.54a.562.562 0 0 1-.84-.61l1.285-5.386a.562.562 0 0 0-.182-.557l-4.204-3.601a.562.562 0 0 1 .321-.988l5.518-.442a.563.563 0 0 0 .475-.345L11.48 3.5Z" /></svg>
          ${entry.track_price ? 'Untrack Price' : 'Track Price'}
        </button>`;
    }

    toggleRow.innerHTML = toggleHtml;
  }

  cardViewOverlay.classList.remove('hidden');
}

async function toggleForTradeFromCardView() {
  const entry = _cardViewEntry;
  if (!entry) return;
  try {
    await requireAuth();
    await apiFetch(`/collection/${entry.id}`, {
      method: 'PUT',
      body: JSON.stringify({ for_trade: !entry.for_trade }),
    });
    toast(!entry.for_trade ? 'Added to Trade Binder' : 'Removed from Trade Binder');
    closeCardView();
    loadCollection();
  } catch (e) {
    if (e.message !== 'Login cancelled') toast(`Error: ${e.message}`, 'error');
  }
}

async function toggleTrackPriceFromCardView() {
  const entry = _cardViewEntry;
  if (!entry) return;
  try {
    await requireAuth();
    await apiFetch(`/collection/${entry.id}`, {
      method: 'PUT',
      body: JSON.stringify({ track_price: !entry.track_price }),
    });
    toast(!entry.track_price ? 'Price tracking enabled' : 'Price tracking disabled');
    closeCardView();
    loadCollection();
  } catch (e) {
    if (e.message !== 'Login cancelled') toast(`Error: ${e.message}`, 'error');
  }
}

function closeCardView() {
  cardViewOverlay.classList.add('hidden');
  _cardViewEntry = null;
}

document.getElementById('card-view-close').addEventListener('click', closeCardView);
cardViewOverlay.addEventListener('click', e => {
  if (e.target === cardViewOverlay) closeCardView();
});
document.addEventListener('keydown', e => {
  if (e.key === 'Escape' && !cardViewOverlay.classList.contains('hidden')) closeCardView();
});
document.getElementById('card-view-edit-btn').addEventListener('click', () => {
  const entry = _cardViewEntry;
  closeCardView();
  openEditModal(entry);
});

// ── Tap-to-reveal actions (touch devices) ────────────────────────
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
  openCardView(JSON.parse(card.dataset.entry));
});
