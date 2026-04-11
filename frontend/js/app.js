/* ── Core app: routing, toast, shared helpers ─────────────────── */

const API = '/api';

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
window.addEventListener('DOMContentLoaded', routeFromHash);

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
