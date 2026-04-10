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
const toastEl = document.getElementById('toast');
let toastTimer;
function toast(msg, type = 'success') {
  toastEl.textContent = msg;
  toastEl.className = `toast ${type}`;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => toastEl.classList.add('hidden'), 3500);
}

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
  const cls = diff >= 0 ? 'pnl-positive' : 'pnl-negative';
  const sign = diff >= 0 ? '+' : '';
  return `<span class="${cls}">${sign}€${diff.toFixed(2)}</span>`;
}
