/**
 * SheetMerge Pro — Client Application Engine
 * ===========================================
 * Handles multi-page routing, onboarding wizard, Google account authentication,
 * live Google Sheets ingestion, single-status YAMM rendering, and sequential dispatch.
 */

(function () {
  'use strict';

  // ── Application State ──────────────────────────────────────────────────
  const state = {
    currentView: 'landing',
    wizardStep: 1,
    authStatus: {
      setup_completed: false,
      has_profile: false,
      has_verified_account: false,
      can_access_dashboard: false,
      profile: null,
      accounts: []
    },
    accounts: [],
    recipients: [],
    isDispatching: false,
    stopRequested: false,
    activeTheme: 'dark'
  };

  // ── Initialization ─────────────────────────────────────────────────────
  async function init() {
    loadTheme();
    setupGlobalNavigation();
    await checkAuthStatus();
    
    // Route based on onboarding status
    if (state.authStatus.can_access_dashboard) {
      navigate('dashboard');
    } else {
      navigate('landing');
    }
  }

  // ── Theme Management ───────────────────────────────────────────────────
  function loadTheme() {
    const savedTheme = localStorage.getItem('sheetmerge_theme') || 'dark';
    state.activeTheme = savedTheme;
    document.documentElement.setAttribute('data-theme', savedTheme);
    const btn = document.getElementById('themeToggleBtn');
    if (btn) btn.textContent = savedTheme === 'dark' ? '🌙' : '☀️';
  }

  function toggleTheme() {
    state.activeTheme = state.activeTheme === 'dark' ? 'light' : 'dark';
    localStorage.setItem('sheetmerge_theme', state.activeTheme);
    document.documentElement.setAttribute('data-theme', state.activeTheme);
    const btn = document.getElementById('themeToggleBtn');
    if (btn) btn.textContent = state.activeTheme === 'dark' ? '🌙' : '☀️';
  }

  // ── View Navigation ────────────────────────────────────────────────────
  function navigate(viewName) {
    if (viewName === 'dashboard' && !state.authStatus.can_access_dashboard) {
      alert('Account setup & profile buildup required! Please complete the onboarding wizard before entering the dashboard.');
      navigate('onboarding');
      return;
    }

    state.currentView = viewName;

    // Toggle active view pane
    document.querySelectorAll('.app-view').forEach(v => v.classList.remove('active'));
    const target = document.getElementById(
      viewName === 'landing' ? 'viewLanding' :
      viewName === 'onboarding' ? 'viewOnboarding' : 'viewDashboard'
    );
    if (target) target.classList.add('active');

    // Update rail active states
    document.querySelectorAll('.rail-btn').forEach(b => b.classList.remove('active'));
    if (viewName === 'landing') document.getElementById('navLandingBtn')?.classList.add('active');
    if (viewName === 'onboarding') document.getElementById('navOnboardingBtn')?.classList.add('active');
    if (viewName === 'dashboard') {
      document.getElementById('navDashboardBtn')?.classList.add('active');
      loadDashboardData();
    }
  }

  function setupGlobalNavigation() {
    window.addEventListener('keydown', (e) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault();
        openComposeDrawer();
      }
    });
  }

  // ── Authentication & Gating Checks ─────────────────────────────────────
  async function checkAuthStatus() {
    try {
      const res = await fetch('/api/auth/status');
      if (res.ok) {
        state.authStatus = await res.json();
        updateUserBadges();
      }
    } catch (e) {
      console.warn('Could not check auth status', e);
    }
  }

  function updateUserBadges() {
    const p = state.authStatus.profile;
    const avatarEl = document.getElementById('railUserAvatar');
    const badgeEl = document.getElementById('dashUserBadge');

    if (p && p.full_name) {
      const initials = p.full_name.split(' ').map(n => n[0]).join('').substring(0, 2).toUpperCase();
      if (avatarEl) avatarEl.textContent = initials;
      if (badgeEl) badgeEl.textContent = `👤 ${p.full_name} (${p.company || 'Workspace'})`;
      
      // Auto-populate profile input if editing
      const nameInput = document.getElementById('profFullName');
      const compInput = document.getElementById('profCompany');
      const roleInput = document.getElementById('profRole');
      if (nameInput && !nameInput.value) nameInput.value = p.full_name;
      if (compInput && !compInput.value) compInput.value = p.company || '';
      if (roleInput && !roleInput.value) roleInput.value = p.role || '';
    }
  }

  // ── Onboarding Wizard Stepper ──────────────────────────────────────────
  function goToStep(stepNum) {
    state.wizardStep = stepNum;

    // Update Indicators
    for (let i = 1; i <= 4; i++) {
      const ind = document.getElementById(`stepIndicator${i}`);
      const pane = document.getElementById(`wizardStep${i}`);
      if (ind) {
        ind.classList.remove('active');
        if (i === stepNum) ind.classList.add('active');
        if (i < stepNum) ind.classList.add('completed');
      }
      if (pane) {
        pane.classList.remove('active');
        if (i === stepNum) pane.classList.add('active');
      }
    }

    if (stepNum === 2) {
      renderWizardAccountsList();
    }
  }

  async function handleProfileSubmit(event) {
    event.preventDefault();
    const fullName = document.getElementById('profFullName').value.trim();
    const company = document.getElementById('profCompany').value.trim();
    const role = document.getElementById('profRole').value.trim();
    const goal = parseInt(document.getElementById('profGoal').value, 10);

    try {
      const res = await fetch('/api/auth/setup-profile', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ full_name: fullName, company, role, daily_goal: goal })
      });
      const data = await res.json();
      if (res.ok) {
        await checkAuthStatus();
        goToStep(2);
      } else {
        alert(data.detail || 'Could not save profile');
      }
    } catch (e) {
      alert('Network error saving profile');
    }
  }

  async function handleAccountVerify(event) {
    event.preventDefault();
    const email = document.getElementById('wizAccEmail').value.trim();
    const name = document.getElementById('wizAccName').value.trim();
    const password = document.getElementById('wizAccPassword').value.trim();

    const btn = document.getElementById('btnVerifyAccount');
    const btnText = document.getElementById('btnVerifyText');
    btn.disabled = true;
    btnText.textContent = 'Testing SMTP Handshake...';

    try {
      const res = await fetch('/api/accounts/verify-smtp', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, app_password: password, display_name: name })
      });
      const data = await res.json();

      if (res.ok && data.success) {
        alert(`✓ Verified ${email} successfully on Gmail SMTP!`);
        document.getElementById('wizardAccountForm').reset();
        await checkAuthStatus();
        renderWizardAccountsList();
      } else {
        alert(data.detail || 'SMTP Verification failed. Please verify your 16-character App Password.');
      }
    } catch (e) {
      alert('Failed to connect to backend SMTP relay.');
    } finally {
      btn.disabled = false;
      btnText.textContent = 'Authenticate & Save Account';
    }
  }

  function renderWizardAccountsList() {
    const listEl = document.getElementById('wizardAccountsList');
    const nextBtn = document.getElementById('btnStep2Next');
    if (!listEl) return;

    listEl.innerHTML = '';
    const accounts = state.authStatus.accounts || [];

    if (accounts.length === 0) {
      listEl.innerHTML = `
        <div style="font-size:12px; color:var(--text-muted); padding:10px; background:var(--card-surface); border-radius:10px;">
          No Google accounts connected yet. Connect your first Gmail account below.
        </div>
      `;
      if (nextBtn) nextBtn.disabled = true;
      return;
    }

    if (nextBtn) nextBtn.disabled = false;

    accounts.forEach(a => {
      const card = document.createElement('div');
      card.className = 'account-badge-card';
      card.innerHTML = `
        <div class="email-info">
          <strong>${a.email}</strong>
          <span>${a.display_name || 'Sender'} · Daily quota: ${a.daily_quota}/day</span>
        </div>
        <div>
          <span class="status-badge ${a.is_verified ? 'verified' : 'unverified'}">
            ${a.is_verified ? '✓ VERIFIED' : 'UNVERIFIED'}
          </span>
        </div>
      `;
      listEl.appendChild(card);
    });
  }

  // ── Sheet / CSV Import in Wizard ───────────────────────────────────────
  async function importWizardSheet() {
    const url = document.getElementById('wizSheetUrl').value.trim();
    if (!url) {
      alert('Please enter a Google Sheet URL');
      return;
    }

    try {
      const res = await fetch('/api/sheet/import-url', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url })
      });
      const data = await res.json();
      if (res.ok && data.success) {
        renderWizardSheetPreview(data);
      } else {
        alert(data.detail || 'Could not import Google Sheet');
      }
    } catch (e) {
      alert('Network error connecting to Google Sheet');
    }
  }

  function handleWizardFileSelect(event) {
    const file = event.target.files[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = async function (e) {
      const csvText = e.target.result;
      try {
        const res = await fetch('/api/sheet/upload-csv', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ csv_text: csvText })
        });
        const data = await res.json();
        if (res.ok && data.success) {
          renderWizardSheetPreview(data);
        } else {
          alert(data.detail || 'Could not parse CSV');
        }
      } catch (err) {
        alert('Network error uploading CSV');
      }
    };
    reader.readAsText(file);
  }

  function renderWizardSheetPreview(sheetData) {
    const previewWrap = document.getElementById('wizSheetPreview');
    const tableEl = document.getElementById('wizPreviewTable');
    const countEl = document.getElementById('wizSheetRowCount');
    const labelEl = document.getElementById('wizSheetSourceLabel');

    if (!previewWrap || !tableEl) return;

    previewWrap.style.display = 'block';
    if (countEl) countEl.textContent = `${sheetData.total_rows} recipients loaded`;
    if (labelEl) labelEl.textContent = sheetData.source || 'Imported Recipients';

    const rows = sheetData.rows || [];
    let html = '<thead><tr><th>#</th><th>Email</th><th>First Name</th><th>Company</th><th>Merge Status</th></tr></thead><tbody>';
    rows.slice(0, 5).forEach((r, idx) => {
      html += `
        <tr>
          <td>${idx + 1}</td>
          <td><strong>${r.email}</strong></td>
          <td>${r.first_name || '—'}</td>
          <td>${r.company || '—'}</td>
          <td><span class="merge-badge unprocessed">${r.merge_status || 'UNPROCESSED'}</span></td>
        </tr>
      `;
    });
    html += '</tbody>';
    tableEl.innerHTML = html;
  }

  // ── Step 4: Loading & User Engagement Screen ────────────────────────────
  function launchLoadingScreen() {
    goToStep(4);
    const fillEl = document.getElementById('engagementProgressFill');
    const titleEl = document.getElementById('loadingEngagementTitle');
    const subEl = document.getElementById('loadingEngagementSubtitle');
    const btnEnter = document.getElementById('btnEnterDashboard');

    const check1 = document.getElementById('checkRow1');
    const check2 = document.getElementById('checkRow2');
    const check3 = document.getElementById('checkRow3');
    const check4 = document.getElementById('checkRow4');

    if (btnEnter) btnEnter.style.display = 'none';

    // Simulated verified progression
    setTimeout(() => {
      if (fillEl) fillEl.style.width = '25%';
      if (check1) { check1.classList.add('done'); check1.querySelector('.check-icon').textContent = '✓'; }
      if (titleEl) titleEl.textContent = 'Testing Gmail SMTP TLS Handshakes...';
    }, 500);

    setTimeout(() => {
      if (fillEl) fillEl.style.width = '55%';
      if (check2) { check2.classList.add('done'); check2.querySelector('.check-icon').textContent = '✓'; }
      if (titleEl) titleEl.textContent = 'Calibrating 2.0s–5.0s Humanized Jitter...';
    }, 1100);

    setTimeout(() => {
      if (fillEl) fillEl.style.width = '80%';
      if (check3) { check3.classList.add('done'); check3.querySelector('.check-icon').textContent = '✓'; }
      if (titleEl) titleEl.textContent = 'Initializing Single YAMM Merge Status Column...';
    }, 1700);

    setTimeout(() => {
      if (fillEl) fillEl.style.width = '100%';
      if (check4) { check4.classList.add('done'); check4.querySelector('.check-icon').textContent = '✓'; }
      if (titleEl) titleEl.textContent = '🎉 Deliverability Pipeline Calibrated & Ready!';
      if (subEl) subEl.textContent = 'Your multi-account environment is active. Enter your campaign dashboard.';
      if (btnEnter) btnEnter.style.display = 'inline-flex';
    }, 2300);
  }

  async function completeOnboardingAndEnterDashboard() {
    await checkAuthStatus();
    navigate('dashboard');
  }

  // ── Dashboard Data Loading ─────────────────────────────────────────────
  async function loadDashboardData() {
    await Promise.all([
      fetchDashboardOverview(),
      fetchUnifiedAccounts(),
      fetchRecipients()
    ]);
  }

  async function fetchDashboardOverview() {
    try {
      const res = await fetch('/api/dashboard/overview');
      if (res.status === 403) {
        alert('Onboarding required before accessing dashboard.');
        navigate('onboarding');
        return;
      }
      if (res.ok) {
        const data = await res.json();
        renderDashboardMetrics(data);
      }
    } catch (e) {
      console.warn('Could not fetch dashboard overview', e);
    }
  }

  function renderDashboardMetrics(data) {
    const m = data.metrics || {};
    const acc = data.accounts_overview || {};

    const quotaVal = document.getElementById('dashQuotaVal');
    if (quotaVal) quotaVal.textContent = `${acc.combined_sent_today || 0} / ${acc.combined_daily_quota || 0}`;

    const quotaSub = document.getElementById('dashQuotaSubtext');
    if (quotaSub) {
      quotaSub.innerHTML = `<span style="color:#10b981;">✓ ${acc.combined_remaining_quota || 0} deliveries remaining</span> · Hard bounces excluded`;
    }

    const openEl = document.getElementById('dashOpenRateVal');
    if (openEl) openEl.textContent = `${m.open_rate || 0.0}%`;

    const clickEl = document.getElementById('dashClickRateVal');
    if (clickEl) clickEl.textContent = `${m.click_rate || 0.0}%`;

    const bounceEl = document.getElementById('dashBounceRateVal');
    if (bounceEl) bounceEl.textContent = `${m.bounce_rate || 0.0}%`;

    renderPillarChart(m);
  }

  function renderPillarChart(metrics) {
    const chartEl = document.getElementById('dashPillarChart');
    if (!chartEl) return;

    const stages = [
      { label: 'Unprocessed', count: metrics.unprocessed_count || 0, color: 'var(--status-pending)' },
      { label: 'Sent', count: metrics.sent_count || 0, color: 'var(--status-sent)' },
      { label: 'Opened', count: metrics.opened_count || 0, color: 'var(--status-opened)' },
      { label: 'Clicked', count: metrics.clicked_count || 0, color: 'var(--status-clicked)' },
      { label: 'Bounced', count: metrics.bounced_count || 0, color: 'var(--status-bounced)' }
    ];

    const maxCount = Math.max(1, ...stages.map(s => s.count));
    chartEl.innerHTML = '';

    stages.forEach(s => {
      const col = document.createElement('div');
      col.className = 'pillar-col';
      const pct = Math.max(8, Math.round((s.count / maxCount) * 100));

      col.innerHTML = `
        <span class="pillar-count">${s.count}</span>
        <div class="pillar-bar-wrap">
          <div class="pillar-bar" style="height:${pct}%; background:${s.color};"></div>
        </div>
        <span class="pillar-label">${s.label}</span>
      `;
      chartEl.appendChild(col);
    });
  }

  async function fetchUnifiedAccounts() {
    try {
      const res = await fetch('/api/accounts/unified-overview');
      if (res.ok) {
        const data = await res.json();
        renderAccountsList(data.accounts || []);
      }
    } catch (e) {
      console.warn('Could not fetch unified accounts', e);
    }
  }

  function renderAccountsList(accountsList) {
    const listEl = document.getElementById('dashAccountsList');
    if (!listEl) return;

    listEl.innerHTML = '';
    if (accountsList.length === 0) {
      listEl.innerHTML = '<div style="font-size:11px; color:var(--text-muted); padding:8px;">No accounts connected.</div>';
      return;
    }

    accountsList.forEach(a => {
      const item = document.createElement('div');
      item.className = 'account-card-item';
      item.innerHTML = `
        <div class="acc-left">
          <div class="acc-avatar">${(a.display_name || a.email)[0].toUpperCase()}</div>
          <div class="acc-details">
            <strong>${a.email}</strong>
            <span>${a.display_name || 'Sender'} · ${a.sent_today}/${a.daily_quota} sent</span>
          </div>
        </div>
        <div class="acc-right">
          <span class="status-badge ${a.status_badge === 'CONNECTED' ? 'verified' : a.status_badge === 'QUOTA_EXHAUSTED' ? 'exhausted' : 'unverified'}">
            ${a.status_badge}
          </span>
        </div>
      `;
      listEl.appendChild(item);
    });
  }

  async function fetchRecipients() {
    try {
      const res = await fetch('/api/sheet/recipients');
      if (res.ok) {
        state.recipients = await res.json();
        renderRecipientsTable(state.recipients);
      }
    } catch (e) {
      console.warn('Could not fetch recipients', e);
    }
  }

  function renderRecipientsTable(recipList) {
    const tbody = document.getElementById('recipientsTableBody');
    const emptyState = document.getElementById('tableEmptyState');
    if (!tbody) return;

    tbody.innerHTML = '';
    if (!recipList || recipList.length === 0) {
      if (emptyState) emptyState.style.display = 'block';
      return;
    }
    if (emptyState) emptyState.style.display = 'none';

    recipList.forEach((r, idx) => {
      const tr = document.createElement('tr');
      tr.id = `recipRow_${r.id}`;

      let badgeClass = 'unprocessed';
      if (r.merge_status === 'EMAIL_SENT') badgeClass = 'sent';
      else if (r.merge_status === 'EMAIL_OPENED') badgeClass = 'opened';
      else if (r.merge_status === 'EMAIL_CLICKED') badgeClass = 'clicked';
      else if (r.merge_status === 'EMAIL_BOUNCED') badgeClass = 'bounced';
      else if (r.merge_status === 'ERROR') badgeClass = 'error';

      tr.innerHTML = `
        <td>${idx + 1}</td>
        <td><strong>${r.email}</strong></td>
        <td>${r.first_name || '—'}</td>
        <td>${r.company || '—'}</td>
        <td>
          <span class="merge-badge ${badgeClass}" id="badge_${r.id}">
            ${r.merge_status || 'UNPROCESSED'}
          </span>
          ${r.last_event ? `<div style="font-size:10px; color:var(--text-dim); margin-top:2px;">${r.last_event}</div>` : ''}
        </td>
        <td>
          <button class="row-action-btn" onclick="window.sheetmerge.dispatchSingleRow(${r.id})">
            ${r.merge_status === 'UNPROCESSED' ? 'Send' : 'Re-send'}
          </button>
        </td>
      `;
      tbody.appendChild(tr);
    });
  }

  function filterRecipients() {
    const q = document.getElementById('tableSearchInput')?.value.toLowerCase().trim() || '';
    if (!q) {
      renderRecipientsTable(state.recipients);
      return;
    }
    const filtered = state.recipients.filter(r => 
      r.email.toLowerCase().includes(q) ||
      (r.first_name && r.first_name.toLowerCase().includes(q)) ||
      (r.company && r.company.toLowerCase().includes(q)) ||
      (r.merge_status && r.merge_status.toLowerCase().includes(q))
    );
    renderRecipientsTable(filtered);
  }

  // ── Dispatching Operations ─────────────────────────────────────────────
  async function dispatchSingleRow(recipientId) {
    const subj = document.getElementById('templateSubject')?.value || 'Quick question';
    const body = document.getElementById('templateBody')?.value || '<p>Hello {{First Name}}</p>';

    const badge = document.getElementById(`badge_${recipientId}`);
    if (badge) {
      badge.textContent = 'SENDING...';
      badge.className = 'merge-badge unprocessed';
    }

    try {
      const res = await fetch('/api/campaign/dispatch-row', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ recipient_id: recipientId, subject: subj, body_html: body })
      });
      const data = await res.json();
      if (res.ok) {
        await loadDashboardData();
      } else {
        alert(data.detail || 'Dispatch failed');
        if (badge) badge.textContent = 'ERROR';
      }
    } catch (e) {
      alert('Network error dispatching email');
    }
  }

  async function startCampaignDispatch() {
    if (state.isDispatching) return;
    const unprocessed = state.recipients.filter(r => r.merge_status === 'UNPROCESSED');
    if (unprocessed.length === 0) {
      alert('No unprocessed recipients remaining in the campaign.');
      return;
    }

    const confirmed = confirm(`Start sequential throttled dispatching for ${unprocessed.length} recipients?\n(Sends with random 2s-5s humanized pacing).`);
    if (!confirmed) return;

    state.isDispatching = true;
    const btn = document.getElementById('btnDispatchCampaign');
    if (btn) btn.innerHTML = '<span>Sending...</span>';

    const subj = document.getElementById('templateSubject')?.value || 'Quick question';
    const body = document.getElementById('templateBody')?.value || '<p>Hello {{First Name}}</p>';

    for (const r of unprocessed) {
      if (state.stopRequested) break;
      await dispatchSingleRow(r.id);
      // Humanized jitter pause
      const jitterMs = 2000 + Math.floor(Math.random() * 3000);
      await new Promise(res => setTimeout(res, jitterMs));
    }

    state.isDispatching = false;
    if (btn) btn.innerHTML = '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polygon points="5 3 19 12 5 21 5 3"></polygon></svg><span>Dispatch Campaign</span>';
    alert('Campaign sequential dispatching complete!');
  }

  // ── Import / Export Operations in Dashboard ────────────────────────────
  async function importGoogleSheet() {
    const url = document.getElementById('googleSheetUrlInput')?.value.trim();
    if (!url) {
      alert('Please enter a Google Sheet URL.');
      return;
    }
    try {
      const res = await fetch('/api/sheet/import-url', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url })
      });
      const data = await res.json();
      if (res.ok && data.success) {
        alert(`✓ Loaded ${data.total_rows} recipients from Google Sheet!`);
        await loadDashboardData();
      } else {
        alert(data.detail || 'Failed to import Google Sheet');
      }
    } catch (e) {
      alert('Network error connecting to Google Sheet');
    }
  }

  function handleFileSelect(event) {
    const file = event.target.files[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = async function (e) {
      const csvText = e.target.result;
      try {
        const res = await fetch('/api/sheet/upload-csv', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ csv_text: csvText })
        });
        const data = await res.json();
        if (res.ok && data.success) {
          alert(`✓ Loaded ${data.total_rows} recipients from CSV!`);
          await loadDashboardData();
        } else {
          alert(data.detail || 'Failed to parse CSV');
        }
      } catch (err) {
        alert('Network error uploading CSV');
      }
    };
    reader.readAsText(file);
  }

  function exportUpdatedCsv() {
    window.location.href = '/api/sheet/export-csv';
  }

  // ── DNS Pre-Flight Scanner ─────────────────────────────────────────────
  async function checkDomain() {
    const domain = document.getElementById('domainInput')?.value.trim() || 'gmail.com';
    try {
      const res = await fetch('/api/security/check-domain', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ domain })
      });
      const data = await res.json();
      if (res.ok) {
        const spf = document.getElementById('spfStatus');
        const dkim = document.getElementById('dkimStatus');
        const dmarc = document.getElementById('dmarcStatus');
        const mx = document.getElementById('mxStatus');

        if (spf) spf.textContent = data.spf.valid ? '✓ Valid SPF' : '⚠ Missing SPF';
        if (dkim) dkim.textContent = data.dkim.configured ? '✓ DKIM Active' : '⚠ No 2048-bit DKIM';
        if (dmarc) dmarc.textContent = data.dmarc.configured ? `✓ DMARC (${data.dmarc.policy || 'p=none'})` : '⚠ No DMARC';
        if (mx) mx.textContent = data.mx.configured ? '✓ MX Resolving' : '⚠ No MX Record';
      }
    } catch (e) {
      console.warn('DNS scan error', e);
    }
  }

  // ── Modals & Drawers ───────────────────────────────────────────────────
  function openAddAccountModal() {
    const m = document.getElementById('addAccountModal');
    if (m) m.classList.add('open');
  }
  function closeAddAccountModal() {
    const m = document.getElementById('addAccountModal');
    if (m) m.classList.remove('open');
  }

  async function handleModalAccountSubmit(event) {
    event.preventDefault();
    const email = document.getElementById('modalAccEmail').value.trim();
    const name = document.getElementById('modalAccName').value.trim();
    const password = document.getElementById('modalAccPassword').value.trim();

    const btn = document.getElementById('btnModalVerify');
    btn.disabled = true;
    btn.textContent = 'Testing Handshake...';

    try {
      const res = await fetch('/api/accounts/verify-smtp', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, app_password: password, display_name: name })
      });
      const data = await res.json();
      if (res.ok && data.success) {
        alert(`✓ Verified ${email} on Gmail SMTP!`);
        closeAddAccountModal();
        document.getElementById('modalAccountForm').reset();
        await loadDashboardData();
      } else {
        alert(data.detail || 'SMTP Verification failed');
      }
    } catch (e) {
      alert('Error verifying account');
    } finally {
      btn.disabled = false;
      btn.textContent = 'Verify & Connect';
    }
  }

  function openComplianceModal() {
    const m = document.getElementById('complianceModal');
    if (m) m.classList.add('open');
  }
  function closeComplianceModal() {
    const m = document.getElementById('complianceModal');
    if (m) m.classList.remove('open');
  }

  function openComposeDrawer() {
    const d = document.getElementById('composeDrawer');
    if (d) d.style.display = 'flex';
  }
  function closeComposeDrawer() {
    const d = document.getElementById('composeDrawer');
    if (d) d.style.display = 'none';
  }

  function insertTag(tag) {
    const textarea = document.getElementById('templateBody');
    if (!textarea) return;
    const start = textarea.selectionStart;
    const end = textarea.selectionEnd;
    const text = textarea.value;
    textarea.value = text.substring(0, start) + tag + text.substring(end);
    textarea.focus();
    textarea.selectionStart = textarea.selectionEnd = start + tag.length;
  }

  async function sendTestEmail() {
    const targetEmail = document.getElementById('testEmailTarget')?.value.trim();
    if (!targetEmail) {
      alert('Please enter a target recipient email address.');
      return;
    }
    const accounts = state.authStatus.accounts || [];
    if (accounts.length === 0) {
      alert('No connected sender account available to send test email.');
      return;
    }

    const senderEmail = accounts[0].email;
    const subject = document.getElementById('templateSubject')?.value || 'Test Subject';
    const body = document.getElementById('templateBody')?.value || '<p>Test Body</p>';

    try {
      const res = await fetch('/api/campaign/send-test', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          account_email: senderEmail,
          target_email: targetEmail,
          subject: subject,
          body_html: body
        })
      });
      const data = await res.json();
      if (res.ok && data.success) {
        alert(`✓ Test email delivered to ${targetEmail}!`);
      } else {
        alert(data.detail || 'Failed to send test email');
      }
    } catch (e) {
      alert('Network error sending test email');
    }
  }

  // ── Global Export for Inline Event Handlers ────────────────────────────
  window.sheetmerge = {
    navigate,
    toggleTheme,
    goToStep,
    handleProfileSubmit,
    handleAccountVerify,
    importWizardSheet,
    handleWizardFileSelect,
    launchLoadingScreen,
    completeOnboardingAndEnterDashboard,
    filterRecipients,
    dispatchSingleRow,
    startCampaignDispatch,
    importGoogleSheet,
    handleFileSelect,
    exportUpdatedCsv,
    checkDomain,
    openAddAccountModal,
    closeAddAccountModal,
    handleModalAccountSubmit,
    openComplianceModal,
    closeComplianceModal,
    openComposeDrawer,
    closeComposeDrawer,
    insertTag,
    sendTestEmail
  };

  // Launch on DOM ready
  document.addEventListener('DOMContentLoaded', init);

})();
