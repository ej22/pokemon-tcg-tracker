/* ── Core app: routing, toast, auth, shared helpers ───────────── */

const API = '/api';

// ── App settings (loaded at startup) ────────────────────────────
window.appSettings = {
  pricing_mode:        'full',
  auto_fetch_full_set: 'disabled',
  grouped_layout:      localStorage.getItem('groupedLayout') || 'horizontal',
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
  collection:     document.getElementById('view-collection'),
  portfolio:      document.getElementById('view-portfolio'),
  sets:           document.getElementById('view-sets'),
  'trade-binder': document.getElementById('view-trade-binder'),
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
  if (view === 'collection')    loadCollection();
  if (view === 'portfolio')     loadPortfolio();
  if (view === 'sets')          loadSets();
  if (view === 'trade-binder')  loadTradeBinder();
}

document.querySelectorAll('.nav-link').forEach(a => {
  a.addEventListener('click', () => routeFromHash());
});
window.addEventListener('hashchange', routeFromHash);
window.addEventListener('DOMContentLoaded', async () => {
  await loadAuthState();
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
function updateSidebarStats(totalCards, valueEur, missingCount = 0) {
  const countEl   = document.getElementById('sidebar-total-cards');
  const valueEl   = document.getElementById('sidebar-value');
  const missingEl = document.getElementById('sidebar-missing-count');
  const missingRow = document.getElementById('sidebar-missing-row');

  if (countEl) countEl.textContent = totalCards != null ? totalCards : '—';
  if (valueEl) valueEl.textContent = valueEur != null ? `€${parseFloat(valueEur).toFixed(2)}` : '—';

  if (missingEl && missingRow) {
    missingRow.classList.toggle('hidden', missingCount === 0);
    missingEl.textContent = missingCount;
  }
}

// ── Dismiss tapped cards on outside tap ─────────────────────────
document.addEventListener('click', e => {
  if (!e.target.closest('.poster-card')) {
    document.querySelectorAll('.poster-card.tapped').forEach(c => c.classList.remove('tapped'));
  }
});

// ── Fetch helpers ────────────────────────────────────────────────
async function apiFetch(path, opts = {}, _retried = false) {
  const token = localStorage.getItem('authToken');
  const headers = { 'Content-Type': 'application/json', ...opts.headers };
  if (token) headers['Authorization'] = `Bearer ${token}`;

  const res = await fetch(API + path, { ...opts, headers });

  // On 401 when auth is enabled: show login modal and retry once
  if (res.status === 401 && !_retried && window.authState?.authEnabled) {
    localStorage.removeItem('authToken');
    window.authState.authenticated = false;
    updateAuthUI();
    await requireAuth();
    return apiFetch(path, opts, true);
  }

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

// ── Authentication ───────────────────────────────────────────────
window.authState = { authenticated: false, authEnabled: false, username: null };

// Pending requireAuth() promises resolved after successful login
let _loginResolvers = [];

async function loadAuthState() {
  try {
    const token = localStorage.getItem('authToken');
    const headers = token ? { Authorization: `Bearer ${token}` } : {};
    const data = await fetch(API + '/auth/status', { headers }).then(r => r.json());
    window.authState = {
      authEnabled:   data.auth_enabled,
      authenticated: data.authenticated,
      username:      data.username || null,
    };
    updateAuthUI();
  } catch (_) {
    // Non-fatal: assume auth disabled
  }
}

function updateAuthUI() {
  const section    = document.getElementById('sidebar-auth-section');
  const loggedIn   = document.getElementById('auth-logged-in');
  const loggedOut  = document.getElementById('auth-logged-out');
  const nameEl     = document.getElementById('auth-username-display');

  if (!section) return;

  if (!window.authState.authEnabled) {
    section.classList.add('hidden');
    return;
  }

  section.classList.remove('hidden');
  if (window.authState.authenticated) {
    if (nameEl) nameEl.textContent = window.authState.username || 'User';
    loggedIn?.classList.remove('hidden');
    loggedOut?.classList.add('hidden');
  } else {
    loggedIn?.classList.add('hidden');
    loggedOut?.classList.remove('hidden');
  }
}

async function requireAuth() {
  if (!window.authState.authEnabled || window.authState.authenticated) return;
  return new Promise((resolve, reject) => {
    _loginResolvers.push({ resolve, reject });
    showLoginModal();
  });
}

function showLoginModal() {
  document.getElementById('login-modal-overlay').classList.remove('hidden');
  document.getElementById('login-error').classList.add('hidden');
  setTimeout(() => document.getElementById('login-username').focus(), 50);
}

function hideLoginModal() {
  document.getElementById('login-modal-overlay').classList.add('hidden');
  document.getElementById('login-form').reset();
  document.getElementById('login-error').classList.add('hidden');
}

function logout() {
  localStorage.removeItem('authToken');
  window.authState.authenticated = false;
  window.authState.username = null;
  updateAuthUI();
  toast('Logged out');
}

// Login form submission
document.getElementById('login-form').addEventListener('submit', async e => {
  e.preventDefault();
  const username = document.getElementById('login-username').value.trim();
  const password = document.getElementById('login-password').value;
  const errorEl  = document.getElementById('login-error');

  try {
    const res = await fetch(API + '/auth/login', {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify({ username, password }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Login failed' }));
      throw new Error(err.detail || 'Login failed');
    }
    const data = await res.json();
    localStorage.setItem('authToken', data.token);
    window.authState.authenticated = true;
    window.authState.username = username;
    updateAuthUI();
    hideLoginModal();
    toast(`Logged in as ${username}`);

    // Resolve all pending requireAuth() promises
    const resolvers = _loginResolvers.splice(0);
    resolvers.forEach(r => r.resolve());
  } catch (err) {
    errorEl.textContent = err.message;
    errorEl.classList.remove('hidden');
  }
});

document.getElementById('login-modal-close').addEventListener('click', () => {
  hideLoginModal();
  // Reject pending requireAuth() promises so callers don't hang
  const resolvers = _loginResolvers.splice(0);
  resolvers.forEach(r => r.reject(new Error('Login cancelled')));
});

// ── Settings Modal ───────────────────────────────────────────────
const settingsOverlay = document.getElementById('settings-modal-overlay');

function openSettingsModal() {
  const mode = window.appSettings.pricing_mode || 'full';
  updateSettingsModeUI(mode);
  const autoFetch = window.appSettings.auto_fetch_full_set || 'disabled';
  updateAutoFetchUI(autoFetch);
  applySettingsToUI();
  settingsOverlay.classList.remove('hidden');
}

function updateAutoFetchUI(value) {
  document.getElementById('autofetch-btn-disabled').classList.toggle('active', value === 'disabled');
  document.getElementById('autofetch-btn-enabled').classList.toggle('active', value === 'enabled');
  document.getElementById('settings-autofetch-warning').classList.toggle('hidden', value !== 'enabled');
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

document.getElementById('btn-settings').addEventListener('click', async () => {
  await requireAuth().catch(() => {});
  if (window.authState.authEnabled && !window.authState.authenticated) return;
  openSettingsModal();
});
document.getElementById('btn-settings-topbar').addEventListener('click', async () => {
  await requireAuth().catch(() => {});
  if (window.authState.authEnabled && !window.authState.authenticated) return;
  openSettingsModal();
});
document.getElementById('btn-settings-mobile').addEventListener('click', async () => {
  await requireAuth().catch(() => {});
  if (window.authState.authEnabled && !window.authState.authenticated) return;
  openSettingsModal();
});

document.querySelectorAll('.mode-btn[data-mode]').forEach(btn => {
  btn.addEventListener('click', async () => {
    const newMode = btn.dataset.mode;
    const currentMode = window.appSettings.pricing_mode || 'full';
    if (newMode === currentMode) return;

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
    if (typeof collectionViewMode !== 'undefined' && collectionViewMode === 'grouped') {
      loadCollection();
    }
  });
});

document.querySelectorAll('.mode-btn[data-autofetch]').forEach(btn => {
  btn.addEventListener('click', async () => {
    const newValue = btn.dataset.autofetch;
    const currentValue = window.appSettings.auto_fetch_full_set || 'disabled';
    if (newValue === currentValue) return;

    updateAutoFetchUI(newValue);

    try {
      await apiFetch('/settings/auto_fetch_full_set', {
        method: 'PUT',
        body: JSON.stringify({ value: newValue }),
      });
      window.appSettings.auto_fetch_full_set = newValue;
      toast(newValue === 'enabled' ? 'Auto-load full sets enabled' : 'Auto-load full sets disabled');
    } catch (e) {
      updateAutoFetchUI(currentValue);
      toast(`Failed to save setting: ${e.message}`, 'error');
    }
  });
});
