/* ── Trade Binder view ────────────────────────────────────────── */

const tradeBinderGrid    = document.getElementById('trade-binder-grid');
const tradeBinderEmpty   = document.getElementById('trade-binder-empty');
const tradeBinderSummary = document.getElementById('trade-binder-summary');
const tradeBinderSubtitle = document.getElementById('trade-binder-subtitle');

async function loadTradeBinder() {
  tradeBinderGrid.innerHTML = Array.from({ length: 6 }, () =>
    `<div class="poster-skeleton skeleton"></div>`
  ).join('');
  tradeBinderEmpty.classList.add('hidden');
  tradeBinderSummary.classList.add('hidden');

  try {
    const entries = await apiFetch('/collection?for_trade=true');
    renderTradeBinder(entries);
  } catch (e) {
    toast(`Failed to load Trade Binder: ${e.message}`, 'error');
    tradeBinderGrid.innerHTML = '';
  }
}

function renderTradeBinder(entries) {
  if (tradeBinderSubtitle) {
    tradeBinderSubtitle.textContent = entries.length
      ? `${entries.length} card${entries.length === 1 ? '' : 's'} available for trade`
      : 'Cards available for trade';
  }

  if (!entries.length) {
    tradeBinderGrid.innerHTML = '';
    tradeBinderEmpty.classList.remove('hidden');
    tradeBinderSummary.classList.add('hidden');
    return;
  }

  tradeBinderEmpty.classList.add('hidden');

  // Calculate total value — trade cards always have pricing enabled
  let totalValue = 0;
  entries.forEach(e => {
    const price = bestPrice(e.prices, e.variant);
    if (price != null) totalValue += parseFloat(price) * (e.quantity || 1);
  });

  const summaryText = document.getElementById('trade-binder-summary-text');
  if (summaryText) {
    const valueStr = totalValue > 0 ? ` — Est. value: <span class="trade-summary-value">€${totalValue.toFixed(2)}</span>` : '';
    summaryText.innerHTML = `${entries.length} card${entries.length === 1 ? '' : 's'} for trade${valueStr}`;
  }
  tradeBinderSummary.classList.remove('hidden');

  // Render poster cards — trade entries always have pricing on
  const prevMode = window.appSettings?.pricing_mode;

  tradeBinderGrid.innerHTML = entries.map(e => {
    // Temporarily override so entryPricingOn returns true for these
    const pricingOn = true;
    return renderTradePosterCard(e);
  }).join('');

}

function renderTradePosterCard(e) {
  const price     = bestPrice(e.prices, e.variant);
  const priceStr  = price != null ? `€${parseFloat(price).toFixed(2)}` : null;
  const imageUrl  = `/api/images/${e.card.api_id}`;
  const entryJson = JSON.stringify(e).replace(/"/g, '&quot;');
  const qty       = e.quantity > 1 ? `<span class="poster-qty-badge">×${e.quantity}</span>` : '';

  let pnlDot = '';
  if (e.purchase_price != null && price != null) {
    const diff = parseFloat(price) - parseFloat(e.purchase_price);
    pnlDot = diff >= 0
      ? `<span class="poster-pnl-dot pnl-pos" title="+€${diff.toFixed(2)}"></span>`
      : `<span class="poster-pnl-dot pnl-neg" title="€${diff.toFixed(2)}"></span>`;
  }

  const isScraped  = e.card.source === 'pricecharting_scrape';
  const isStale    = isScraped && isPriceStale(e.prices);
  const pcBadge    = isScraped ? `<span class="chip chip-cm" title="Price from PriceCharting (USD→EUR)">PC</span>` : '';
  const staleBadge = isStale ? `<span class="chip chip-stale" title="Price may be outdated">Stale</span>` : '';

  const priceRow = `<span class="poster-price-row">${pnlDot}${priceStr ? `<span class="poster-price">${priceStr}</span>` : '<span class="poster-no-price">—</span>'}</span>`;

  return `
    <div class="poster-card" role="button" tabindex="0"
         aria-label="${e.card.name}"
         data-entry="${entryJson}"
         onkeydown="if(event.key==='Enter')openCardView(JSON.parse(this.dataset.entry))">
      <img src="${imageUrl}" alt="${e.card.name}" onerror="this.style.display='none';this.parentElement.insertAdjacentHTML('afterbegin',cardPlaceholder())">

      <div class="poster-badges">
        ${conditionChip(e.condition)}
        ${qty}
        ${pcBadge}
        ${staleBadge}
        <span class="chip chip-trade">TRADE</span>
      </div>

      <div class="poster-actions" onclick="event.stopPropagation()">
        <button class="poster-action-btn poster-action-trade active"
          title="Remove from Trade Binder"
          onclick="toggleForTrade(event, ${e.id}, true)">
          <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.75" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" d="M7.5 21 3 16.5m0 0L7.5 12M3 16.5h13.5m0-13.5L21 7.5m0 0L16.5 12M21 7.5H7.5" /></svg>
        </button>
        <button class="poster-action-btn poster-action-edit" title="Edit"
          onclick="openEditModal(JSON.parse(this.closest('[data-entry]').dataset.entry))">
          <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.75" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" d="m16.862 4.487 1.687-1.688a1.875 1.875 0 1 1 2.652 2.652L10.582 16.07a4.5 4.5 0 0 1-1.897 1.13L6 18l.8-2.685a4.5 4.5 0 0 1 1.13-1.897l8.932-8.931Zm0 0L19.5 7.125" /></svg>
        </button>
        <button class="poster-action-btn poster-action-delete" title="Remove"
          onclick="deleteEntry(event, ${e.id})">
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

// Tap-to-reveal Add button on trade binder cards (touch devices)
if (tradeBinderGrid) {
  tradeBinderGrid.addEventListener('click', e => {
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
}
