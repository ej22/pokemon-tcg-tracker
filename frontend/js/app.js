/* ── Core app: routing, toast, shared helpers ─────────────────── */

const API = '/api';

// ── App settings (loaded at startup) ────────────────────────────
window.appSettings = {
  pricing_mode:   'full',
  grouped_layout: localStorage.getItem('groupedLayout') || 'horizontal',
};

async function loadSettings() {
  try {
    const data = await apiFetch('/settings');
    window.appSettings = {
      grouped_layout: localStorage.getItem('groupedLayout') || 'horizontal',
      ...data,
    };
    applySettingsToUI();
  } catch (e) {
    // Non-fatal: default settings apply
  }
}

function applySettingsToUI() {
  const pricingOn = window.appSettings.pricing_mode !== 'collection_only';
  const valueRow = document.getElementById('sidebar-value-row');
  if (valueRow) valueRow.classList.toggle('hidden', !pricingOn);

  const layout = window.appSettings.grouped_layout || 'horizontal';
  document.getElementById('layout-btn-horizontal')?.classList.toggle('active', layout === 'horizontal');
  document.getElementById('layout-btn-grid')?.classList.toggle('active', layout === 'grid');
}

// ── Routing ─────────────────────────────────────────────────────
const views = {
  collection: document.getElementById('view-collection'),
  portfolio:  document.getElementById('view-portfolio'),
  sets:       document.getElementById('view-sets'),
};

function showView(name) {
  Object.entries(views).forEach(([k, el]) => {
    el.classList.toggle('active', k === name);
    el.classList.toggle('hidden', k !== name);
  });
  document.querySelectorAll('.nav-link').forEach(a => {
    a.classList.toggle('active', a.dataset.view === name);
  });
}

function routeFromHash() {
  const hash = window.location.hash.replace('#', '') || 'collection';
  const view = views[hash] ? hash : 'collection';
  showView(view);
  if (view === 'collection') loadCollection();
  if (view === 'portfolio')  loadPortfolio();
  if (view === 'sets')       loadSets();
}

document.querySelectorAll('.nav-link').forEach(a => {
  a.addEventListener('click', () => routeFromHash());
});
window.addEventListener('hashchange', routeFromHash);
window.addEventListener('DOMContentLoaded', async () => {
  await loadSettings();
  routeFromHash();
});

// ── Toast ────────────────────────────────────────────────────────
const toastContainer = document.getElementById('toast-container');

function toast(msg, type = 'success') {
  const el = document.createElement('div');
  el.className = `toast ${type}`;
  el.textContent = msg;
  toastContainer.appendChild(el);

  const dismiss = () => {
    el.style.animation = 'toast-out 200ms var(--ease) forwards';
    el.addEventListener('animationend', () => el.remove(), { once: true });
  };
  const timer = setTimeout(dismiss, 3500);
  el.addEventListener('click', () => { clearTimeout(timer); dismiss(); });
}

// ── Sidebar stats ────────────────────────────────────────────────
function updateSidebarStats(totalCards, valueEur) {
  const countEl = document.getElementById('sidebar-total-cards');
  const valueEl = document.getElementById('sidebar-value');
  if (countEl) countEl.textContent = totalCards != null ? totalCards : '—';
  if (valueEl) valueEl.textContent = valueEur != null ? `€${parseFloat(valueEur).toFixed(2)}` : '—';
}

// ── Dismiss tapped cards on outside tap ─────────────────────────
document.addEventListener('click', e => {
  if (!e.target.closest('.poster-card')) {
    document.querySelectorAll('.poster-card.tapped').forEach(c => c.classList.remove('tapped'));
  }
});

// ── Fetch helpers ────────────────────────────────────────────────
async function apiFetch(path, opts = {}) {
  const res = await fetch(API + path, {
    headers: { 'Content-Type': 'application/json', ...opts.headers },
    ...opts,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }
  if (res.status === 204) return null;
  return res.json();
}

// ── Format helpers ───────────────────────────────────────────────
function fmtEur(val) {
  if (val == null) return '<span class="text-muted">—</span>';
  return `€${parseFloat(val).toFixed(2)}`;
}

function fmtDate(iso) {
  if (!iso) return '<span class="text-muted">—</span>';
  return iso.slice(0, 10);
}

function pnlHtml(purchasePrice, currentPrice, qty) {
  if (purchasePrice == null || currentPrice == null) return '<span class="text-muted">—</span>';
  const diff = (parseFloat(currentPrice) - parseFloat(purchasePrice)) * (qty || 1);
  const cls = diff >= 0 ? 'cell-pnl-pos' : 'cell-pnl-neg';
  const sign = diff >= 0 ? '+' : '';
  return `<span class="${cls}">${sign}€${diff.toFixed(2)}</span>`;
}

// ── Settings Modal ───────────────────────────────────────────────
const settingsOverlay = document.getElementById('settings-modal-overlay');

function openSettingsModal() {
  const mode = window.appSettings.pricing_mode || 'full';
  updateSettingsModeUI(mode);
  applySettingsToUI();
  settingsOverlay.classList.remove('hidden');
}

function updateSettingsModeUI(mode) {
  document.getElementById('mode-btn-full').classList.toggle('active', mode === 'full');
  document.getElementById('mode-btn-collection').classList.toggle('active', mode === 'collection_only');
  document.getElementById('settings-mode-full').classList.toggle('hidden', mode !== 'full');
  document.getElementById('settings-mode-collection').classList.toggle('hidden', mode !== 'collection_only');
  document.getElementById('settings-pricing-warning').classList.add('hidden');
}

document.getElementById('settings-modal-close').addEventListener('click', () => {
  settingsOverlay.classList.add('hidden');
});
settingsOverlay.addEventListener('click', e => {
  if (e.target === settingsOverlay) settingsOverlay.classList.add('hidden');
});

document.getElementById('btn-settings').addEventListener('click', openSettingsModal);
document.getElementById('btn-settings-topbar').addEventListener('click', openSettingsModal);

document.querySelectorAll('.mode-btn[data-mode]').forEach(btn => {
  btn.addEventListener('click', async () => {
    const newMode = btn.dataset.mode;
    const currentMode = window.appSettings.pricing_mode || 'full';
    if (newMode === currentMode) return;

    // Preview the selection visually
    updateSettingsModeUI(newMode);
    document.getElementById('settings-pricing-warning').classList.toggle('hidden', newMode !== 'full');

    try {
      await apiFetch('/settings/pricing_mode', {
        method: 'PUT',
        body: JSON.stringify({ value: newMode }),
      });
      window.appSettings.pricing_mode = newMode;
      applySettingsToUI();
      toast(newMode === 'full' ? 'Full pricing mode enabled' : 'Collection-only mode enabled');
      routeFromHash();
    } catch (e) {
      updateSettingsModeUI(currentMode);
      toast(`Failed to save setting: ${e.message}`, 'error');
    }
  });
});

document.querySelectorAll('.mode-btn[data-layout]').forEach(btn => {
  btn.addEventListener('click', () => {
    const newLayout = btn.dataset.layout;
    if (newLayout === (window.appSettings.grouped_layout || 'horizontal')) return;
    window.appSettings.grouped_layout = newLayout;
    localStorage.setItem('groupedLayout', newLayout);
    applySettingsToUI();
    // Re-render collection if currently in grouped view
    if (typeof collectionViewMode !== 'undefined' && collectionViewMode === 'grouped') {
      loadCollection();
    }
  });
});
