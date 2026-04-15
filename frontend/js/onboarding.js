/* ── Onboarding Wizard ─────────────────────────────────────────── */

let _apiKeyValid = false;
let _selectedPricingMode = 'full';
let _selectedGroupedLayout = 'horizontal';
let _selectedAutoFetch = 'disabled';
let _selectedSetImages = 'visible';

function initOnboarding() {
  const overlay = document.getElementById('onboarding-overlay');
  if (!overlay) return;
  overlay.classList.remove('hidden');
  _showOnboardingStep(0);
  _initOnboardingControls();
}

function _showOnboardingStep(index) {
  document.querySelectorAll('.onboarding-step').forEach(el => {
    el.classList.toggle('active', parseInt(el.dataset.step) === index);
  });
  document.querySelectorAll('.step-dot').forEach(el => {
    el.classList.toggle('active', parseInt(el.dataset.step) === index);
  });
}

function _initOnboardingControls() {
  // Step 0: Get Started
  document.getElementById('onboarding-step0-next').addEventListener('click', () => {
    _showOnboardingStep(1);
  });

  // Step 1: API Key
  document.getElementById('onboarding-validate-btn').addEventListener('click', _validateApiKey);
  document.getElementById('onboarding-step1-back').addEventListener('click', () => {
    _showOnboardingStep(0);
  });
  document.getElementById('onboarding-step1-next').addEventListener('click', () => {
    _showOnboardingStep(2);
  });

  // Step 2: Preferences — pricing mode
  document.querySelectorAll('.onboarding-mode-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      _selectedPricingMode = btn.dataset.mode;
      document.querySelectorAll('.onboarding-mode-btn').forEach(b => {
        b.classList.toggle('active', b.dataset.mode === _selectedPricingMode);
      });
      _updatePricingModeDesc(_selectedPricingMode);
    });
  });

  // Step 2: Preferences — grouped layout
  document.querySelectorAll('.onboarding-layout-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      _selectedGroupedLayout = btn.dataset.layout;
      document.querySelectorAll('.onboarding-layout-btn').forEach(b => {
        b.classList.toggle('active', b.dataset.layout === _selectedGroupedLayout);
      });
    });
  });

  // Step 2: Preferences — auto-fetch full sets
  document.querySelectorAll('.onboarding-autofetch-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      _selectedAutoFetch = btn.dataset.autofetch;
      document.querySelectorAll('.onboarding-autofetch-btn').forEach(b => {
        b.classList.toggle('active', b.dataset.autofetch === _selectedAutoFetch);
      });
      _updateApiWarning();
    });
  });

  // Step 2: Preferences — set card images
  document.querySelectorAll('.onboarding-setimages-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      _selectedSetImages = btn.dataset.setimages;
      document.querySelectorAll('.onboarding-setimages-btn').forEach(b => {
        b.classList.toggle('active', b.dataset.setimages === _selectedSetImages);
      });
      _updateApiWarning();
    });
  });

  document.getElementById('onboarding-step2-back').addEventListener('click', () => {
    _showOnboardingStep(1);
  });
  document.getElementById('onboarding-step2-next').addEventListener('click', () => {
    _updateOnboardingSummary();
    _showOnboardingStep(3);
  });

  // Step 3: Finish
  document.getElementById('onboarding-finish-btn').addEventListener('click', _completeOnboarding);
}

function _updateApiWarning() {
  const warningEl = document.getElementById('onboarding-api-warning');
  if (!warningEl) return;
  warningEl.classList.toggle('hidden', !(_selectedAutoFetch === 'enabled' && _selectedSetImages === 'visible'));
}

function _updatePricingModeDesc(mode) {
  const fullDesc = document.getElementById('onboarding-mode-desc-full');
  const collDesc = document.getElementById('onboarding-mode-desc-coll');
  if (fullDesc) fullDesc.classList.toggle('hidden', mode !== 'full');
  if (collDesc) collDesc.classList.toggle('hidden', mode !== 'collection_only');
}

function _updateOnboardingSummary() {
  const set = (id, text) => { const el = document.getElementById(id); if (el) el.textContent = text; };
  set('onboarding-summary-mode',      _selectedPricingMode === 'full' ? 'Full pricing' : 'Collection only');
  set('onboarding-summary-layout',    _selectedGroupedLayout === 'horizontal' ? 'Horizontal scroll' : 'Grid');
  set('onboarding-summary-autofetch', _selectedAutoFetch === 'enabled' ? 'On' : 'Off');
  set('onboarding-summary-setimages', _selectedSetImages === 'visible' ? 'Visible' : 'Hidden');
}

async function _validateApiKey() {
  const btn = document.getElementById('onboarding-validate-btn');
  const statusEl = document.getElementById('onboarding-validate-status');
  const nextBtn = document.getElementById('onboarding-step1-next');

  btn.disabled = true;
  statusEl.innerHTML = '<div class="validate-spinner"></div><span>Validating…</span>';
  nextBtn.classList.add('hidden');
  _apiKeyValid = false;

  try {
    const data = await apiFetch('/settings/validate-api-key', { method: 'POST' });
    if (data.status === 'valid') {
      _apiKeyValid = true;
      statusEl.innerHTML = '<span class="validate-success">✓ API key is valid — connection successful</span>';
      nextBtn.classList.remove('hidden');
      btn.textContent = 'Validate Connection';
    } else {
      statusEl.innerHTML = `<span class="validate-error">✗ ${data.detail || 'API key is invalid'}</span>`;
      btn.disabled = false;
      btn.textContent = 'Retry';
    }
  } catch (e) {
    statusEl.innerHTML = `<span class="validate-error">✗ ${e.message}</span>`;
    btn.disabled = false;
    btn.textContent = 'Retry';
  }
}

async function _completeOnboarding() {
  const btn = document.getElementById('onboarding-finish-btn');
  btn.disabled = true;
  btn.textContent = 'Setting up…';

  try {
    await apiFetch('/settings/complete-onboarding', {
      method: 'POST',
      body: JSON.stringify({
        pricing_mode:        _selectedPricingMode,
        grouped_layout:      _selectedGroupedLayout,
        auto_fetch_full_set: _selectedAutoFetch,
        set_images:          _selectedSetImages,
      }),
    });

    localStorage.setItem('groupedLayout', _selectedGroupedLayout);

    window.appSettings.onboarding_complete  = 'true';
    window.appSettings.pricing_mode         = _selectedPricingMode;
    window.appSettings.grouped_layout       = _selectedGroupedLayout;
    window.appSettings.auto_fetch_full_set  = _selectedAutoFetch;
    window.appSettings.set_images           = _selectedSetImages;

    document.getElementById('onboarding-overlay').classList.add('hidden');

    applySettingsToUI();
    routeFromHash();
  } catch (e) {
    btn.disabled = false;
    btn.textContent = 'Start Collecting';
    // Show an inline error on the step
    const statusEl = document.getElementById('onboarding-finish-error');
    if (statusEl) {
      statusEl.textContent = `Failed to save settings: ${e.message}`;
      statusEl.classList.remove('hidden');
    }
  }
}
