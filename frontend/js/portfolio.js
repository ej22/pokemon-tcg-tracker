/* ── Portfolio view ───────────────────────────────────────────── */

const portfolioLoading = document.getElementById('portfolio-loading');
const portfolioContent = document.getElementById('portfolio-content');
const setValueTbody    = document.getElementById('set-value-tbody');
const chartNoData      = document.getElementById('chart-no-data');

let portfolioChart = null;

async function loadPortfolio() {
  portfolioLoading.classList.remove('hidden');
  portfolioContent.classList.add('hidden');

  try {
    const summary = await apiFetch('/portfolio/summary');
    renderPortfolioSummary(summary);
    await renderPortfolioChart();
    portfolioContent.classList.remove('hidden');
  } catch (e) {
    toast(`Failed to load portfolio: ${e.message}`, 'error');
  } finally {
    portfolioLoading.classList.add('hidden');
  }
}

function renderPortfolioSummary(s) {
  document.getElementById('summary-total-cards').textContent  = s.total_cards;
  document.getElementById('summary-unique-cards').textContent = s.total_unique_cards;
  document.getElementById('summary-value-eur').textContent    =
    s.total_value_eur != null ? `€${parseFloat(s.total_value_eur).toFixed(2)}` : '—';
  document.getElementById('summary-priced').textContent =
    `${s.cards_with_prices} / ${s.cards_with_prices + s.cards_without_prices}`;

  setValueTbody.innerHTML = (s.value_by_set || []).map(row => `
    <tr>
      <td>${row.set_name}</td>
      <td>${row.card_count}</td>
      <td class="price-value">€${row.total_eur.toFixed(2)}</td>
    </tr>
  `).join('') || '<tr><td colspan="3" class="text-muted" style="text-align:center">No data</td></tr>';
}

async function renderPortfolioChart() {
  // Aggregate total portfolio value per day from price history across all collection cards
  const canvas = document.getElementById('portfolio-chart');

  try {
    const collection = await apiFetch('/collection');
    if (!collection.length) {
      chartNoData.classList.remove('hidden');
      canvas.classList.add('hidden');
      return;
    }

    // Fetch price history for all cards and sum by date
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
          data: days.map(d => dailyTotals[d].toFixed(2)),
          borderColor: '#F27E00',
          backgroundColor: 'rgba(242,126,0,0.1)',
          borderWidth: 2,
          pointRadius: 3,
          tension: 0.3,
          fill: true,
        }],
      },
      options: {
        responsive: true,
        maintainAspectRatio: true,
        plugins: {
          legend: { labels: { color: '#e8eaf0' } },
          tooltip: {
            callbacks: {
              label: ctx => `€${parseFloat(ctx.parsed.y).toFixed(2)}`,
            },
          },
        },
        scales: {
          x: { ticks: { color: '#7a7f9a' }, grid: { color: '#2e3250' } },
          y: {
            ticks: { color: '#7a7f9a', callback: v => `€${v}` },
            grid: { color: '#2e3250' },
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
document.getElementById('btn-refresh-prices').addEventListener('click', async () => {
  const btn = document.getElementById('btn-refresh-prices');
  btn.disabled = true;
  btn.textContent = 'Refreshing…';
  try {
    const result = await apiFetch('/prices/refresh', { method: 'POST' });
    toast(`Refreshed ${result.refreshed} cards (${result.skipped} skipped)`);
    await loadPortfolio();
  } catch (e) {
    toast(`Refresh failed: ${e.message}`, 'error');
  } finally {
    btn.disabled = false;
    btn.innerHTML = '&#8635; Refresh Prices';
  }
});
