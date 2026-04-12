/* ── Portfolio view ───────────────────────────────────────────── */

const portfolioLoading = document.getElementById('portfolio-loading');
const portfolioContent = document.getElementById('portfolio-content');
const setValueTbody    = document.getElementById('set-value-tbody');
const chartNoData      = document.getElementById('chart-no-data');

let portfolioChart = null;

async function loadPortfolio() {
  const disabled = document.getElementById('portfolio-disabled');
  const btnRefreshPrices = document.getElementById('btn-refresh-prices');

  // Show disabled state when pricing is off
  if (window.appSettings?.pricing_mode === 'collection_only') {
    portfolioLoading.classList.add('hidden');
    portfolioContent.classList.add('hidden');
    disabled.classList.remove('hidden');
    if (btnRefreshPrices) btnRefreshPrices.classList.add('hidden');
    return;
  }

  disabled.classList.add('hidden');
  if (btnRefreshPrices) btnRefreshPrices.classList.remove('hidden');
  portfolioLoading.classList.remove('hidden');
  portfolioContent.classList.add('hidden');

  try {
    const summary = await apiFetch('/portfolio/summary');
    renderPortfolioSummary(summary);
    await renderPortfolioChart();
    portfolioContent.classList.remove('hidden');

    updateSidebarStats(
      summary.total_cards,
      summary.total_value_eur,
    );
  } catch (e) {
    toast(`Failed to load portfolio: ${e.message}`, 'error');
  } finally {
    portfolioLoading.classList.add('hidden');
  }
}

function renderPortfolioSummary(s) {
  document.getElementById('summary-total-cards').textContent  = s.total_cards ?? '—';
  document.getElementById('summary-unique-cards').textContent = s.total_unique_cards ?? '—';
  document.getElementById('summary-value-eur').textContent    =
    s.total_value_eur != null ? `€${parseFloat(s.total_value_eur).toFixed(2)}` : '—';
  document.getElementById('summary-priced').textContent =
    `${s.cards_with_prices} / ${(s.cards_with_prices ?? 0) + (s.cards_without_prices ?? 0)}`;

  setValueTbody.innerHTML = (s.value_by_set || []).map(row => `
    <tr>
      <td>${row.set_name}</td>
      <td><span class="cell-mono">${row.card_count}</span></td>
      <td><span class="cell-price">€${parseFloat(row.total_eur).toFixed(2)}</span></td>
    </tr>
  `).join('') || '<tr><td colspan="3" class="text-muted" style="text-align:center;padding:1.5rem">No data</td></tr>';
}

async function renderPortfolioChart() {
  const canvas = document.getElementById('portfolio-chart');

  try {
    const collection = await apiFetch('/collection');
    if (!collection.length) {
      chartNoData.classList.remove('hidden');
      canvas.classList.add('hidden');
      return;
    }

    const dailyTotals = {};
    for (const entry of collection) {
      try {
        const history = await apiFetch(`/prices/${entry.card_api_id}/history`);
        for (const h of history) {
          if (h.source !== 'cardmarket') continue;
          const day = h.fetched_at.slice(0, 10);
          const price = parseFloat(h.trend_price ?? h.avg_price ?? h.mid_price ?? 0);
          dailyTotals[day] = (dailyTotals[day] || 0) + price * entry.quantity;
        }
      } catch (_) { /* skip cards with no history */ }
    }

    const days = Object.keys(dailyTotals).sort();
    if (days.length < 2) {
      chartNoData.classList.remove('hidden');
      canvas.classList.add('hidden');
      return;
    }

    chartNoData.classList.add('hidden');
    canvas.classList.remove('hidden');

    if (portfolioChart) portfolioChart.destroy();

    portfolioChart = new Chart(canvas, {
      type: 'line',
      data: {
        labels: days,
        datasets: [{
          label: 'Portfolio Value (EUR)',
          data: days.map(d => parseFloat(dailyTotals[d].toFixed(2))),
          borderColor: '#F27E00',
          backgroundColor: 'rgba(242,126,0,0.08)',
          borderWidth: 2,
          pointRadius: 3,
          pointBackgroundColor: '#F27E00',
          tension: 0.35,
          fill: true,
        }],
      },
      options: {
        responsive: true,
        maintainAspectRatio: true,
        plugins: {
          legend: { labels: { color: '#9ca3b0', font: { size: 12 } } },
          tooltip: {
            backgroundColor: '#18181B',
            borderColor: '#2a2a2f',
            borderWidth: 1,
            titleColor: '#e4e4e7',
            bodyColor: '#a1a1aa',
            callbacks: {
              label: ctx => `€${parseFloat(ctx.parsed.y).toFixed(2)}`,
            },
          },
        },
        scales: {
          x: {
            ticks: { color: '#71717a', font: { size: 11 } },
            grid: { color: '#27272a' },
            border: { color: '#27272a' },
          },
          y: {
            ticks: { color: '#71717a', font: { size: 11 }, callback: v => `€${v}` },
            grid: { color: '#27272a' },
            border: { color: '#27272a' },
          },
        },
      },
    });
  } catch (e) {
    chartNoData.classList.remove('hidden');
    canvas.classList.add('hidden');
  }
}

// ── Manual price refresh button ──────────────────────────────────
const btnRefresh = document.getElementById('btn-refresh-prices');
btnRefresh.addEventListener('click', async () => {
  btnRefresh.disabled = true;
  btnRefresh.querySelector('span') && (btnRefresh.querySelector('span').textContent = 'Refreshing…');

  const originalHTML = btnRefresh.innerHTML;
  btnRefresh.innerHTML = `
    <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.75" stroke="currentColor" style="animation:spin 1s linear infinite"><path stroke-linecap="round" stroke-linejoin="round" d="M16.023 9.348h4.992v-.001M2.985 19.644v-4.992m0 0h4.992m-4.993 0 3.181 3.183a8.25 8.25 0 0 0 13.803-3.7M4.031 9.865a8.25 8.25 0 0 1 13.803-3.7l3.181 3.182m0-4.991v4.99" /></svg>
    Refreshing…
  `;

  try {
    const result = await apiFetch('/prices/refresh', { method: 'POST' });
    toast(`Refreshed ${result.refreshed} cards (${result.skipped} skipped)`);
    await loadPortfolio();
  } catch (e) {
    toast(`Refresh failed: ${e.message}`, 'error');
  } finally {
    btnRefresh.disabled = false;
    btnRefresh.innerHTML = originalHTML;
  }
});
