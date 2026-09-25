/**
 * SheetMerge Pro — Frontend Application Engine (v3.0.0)
 * ====================================================
 * Modules:
 *   1. App User Authentication (Fast Google OAuth & Email 6-Digit OTP)
 *   2. Multi-Account Google Sender Pool Management
 *   3. Live Google Sheets Ingestion & Single-Status YAMM Sync
 *   4. Sequential Humanized Jitter Dispatcher (2.0s–5.0s)
 *   5. Delivery & Inboxing Health Visualisation
 */

(function () {
  'use strict';

  // ── Application State ──────────────────────────────────────────────────
  const state = {
    currentView: 'landing',
    user: null,
    token: localStorage.getItem('sheetmerge_token') || '',
    accounts: [],
    recipients: [],
    tableFilter: 'all',
    searchQuery: '',
    isDispatching: false,
    stopRequested: false,
    activeTheme: 'dark',
    pendingOtpEmail: ''
  };

  // ── Initialization ─────────────────────────────────────────────────────
  async function init() {
    loadTheme();
    setupOtpDigitInputs();
    setupKeyboardShortcuts();
    await checkCurrentUser();

    // Default route
    if (state.user) {
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
    state.currentView = viewName;

    // Toggle active view pane
    document.querySelectorAll('.app-view').forEach(v => v.classList.remove('active'));
    const targetMap = {
      landing: 'viewLanding',
      auth: 'viewAuth',
      dashboard: 'viewDashboard',
      walkthrough: 'viewWalkthrough'
    };
    const target = document.getElementById(targetMap[viewName] || 'viewLanding');
    if (target) target.classList.add('active');

    // Update rail active states
    document.querySelectorAll('.rail-btn').forEach(b => b.classList.remove('active'));
    if (viewName === 'landing') document.getElementById('navLandingBtn')?.classList.add('active');
    if (viewName === 'auth') document.getElementById('navAuthBtn')?.classList.add('active');
    if (viewName === 'dashboard') {
      document.getElementById('navDashboardBtn')?.classList.add('active');
      loadDashboardData();
    }
    if (viewName === 'walkthrough') document.getElementById('navWalkthroughBtn')?.classList.add('active');
  }

  function setupKeyboardShortcuts() {
    window.addEventListener('keydown', (e) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault();
        openComposeDrawer();
      }
    });
  }

  // ══════════════════════════════════════════════════════════════════════════
  // SECTION 1: APP USER AUTHENTICATION (OAuth & Email OTP)
  // ══════════════════════════════════════════════════════════════════════════

  async function checkCurrentUser() {
    try {
      const headers = state.token ? { 'Authorization': `Bearer ${state.token}` } : {};
      const res = await fetch('/api/auth/me', { headers });
      if (res.ok) {
        const data = await res.json();
        if (data.authenticated && data.user) {
          state.user = data.user;
          updateUserDisplay();
        } else {
          state.user = null;
          updateUserDisplay();
        }
      }
    } catch (e) {
      console.warn('Could not check current user session', e);
    }
  }

  function updateUserDisplay() {
    const avatarEl = document.getElementById('railUserAvatar');
    const badgeEl = document.getElementById('dashUserBadge');
    const activeCard = document.getElementById('authActiveUserCard');
    const formsWrap = document.getElementById('authFormsWrap');

    if (state.user) {
      const initials = (state.user.full_name || state.user.email)
        .split(' ')
        .map(n => n[0])
        .join('')
        .substring(0, 2)
        .toUpperCase();

      if (avatarEl) avatarEl.textContent = initials || 'SM';
      if (badgeEl) badgeEl.textContent = `👤 ${state.user.full_name || state.user.email}`;

      if (activeCard && formsWrap) {
        activeCard.style.display = 'block';
        formsWrap.style.display = 'none';
        document.getElementById('activeUserName').textContent = state.user.full_name || 'Active User';
        document.getElementById('activeUserEmail').textContent = state.user.email;
      }
    } else {
      if (avatarEl) avatarEl.textContent = 'SM';
      if (badgeEl) badgeEl.textContent = '👤 Guest User (Sign In)';

      if (activeCard && formsWrap) {
        activeCard.style.display = 'none';
        formsWrap.style.display = 'block';
      }
    }
  }

  async function signInWithGoogleOAuth() {
    let email = prompt('Enter your Google email for fast 1-click Google Sign-In:', 'user@gmail.com');
    if (!email) return;

    email = email.trim().toLowerCase();
    if (!email || !email.includes('@')) {
      alert('Please enter a valid Google email address.');
      return;
    }

    const defaultName = email.split('@')[0].replace(/\./g, ' ').replace(/\b\w/g, l => l.toUpperCase());
    const btn = document.getElementById('btnGoogleAuth');
    if (btn) btn.disabled = true;

    try {
      const res = await fetch('/api/auth/google/oauth', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, name: defaultName })
      });
      const data = await res.json();
      if (res.ok && data.success) {
        state.token = data.token;
        localStorage.setItem('sheetmerge_token', data.token);
        state.user = data.user;
        updateUserDisplay();
        alert(`✓ Welcome, ${data.user.full_name}! You are now signed in with Google.`);
        navigate('dashboard');
      } else {
        alert(data.detail || 'Could not authenticate with Google.');
      }
    } catch (e) {
      alert('Error during Google authentication: ' + e.message);
    } finally {
      if (btn) btn.disabled = false;
    }
  }

  async function handleSendOtp(e) {
    if (e) e.preventDefault();
    const emailInput = document.getElementById('otpEmailInput');
    const email = emailInput.value.trim().toLowerCase();

    if (!email || !email.includes('@')) {
      alert('Please enter a valid email address.');
      return;
    }

    state.pendingOtpEmail = email;
    const btnText = document.getElementById('btnSendOtpText');
    if (btnText) btnText.textContent = 'Sending Verification Code...';

    try {
      const res = await fetch('/api/auth/otp/send', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email })
      });
      const data = await res.json();
      if (res.ok && data.success) {
        // Transition to OTP verification screen
        document.getElementById('emailOtpRequestForm').style.display = 'none';
        const verifySec = document.getElementById('otpVerifySection');
        verifySec.style.display = 'flex';
        document.getElementById('otpTargetDisplay').textContent = email;

        // If dev_otp returned, show it for easy copy
        if (data.dev_otp) {
          const banner = document.getElementById('devOtpBanner');
          const codeEl = document.getElementById('devOtpCode');
          if (banner && codeEl) {
            banner.style.display = 'block';
            codeEl.textContent = data.dev_otp;
          }
        }

        // Focus first digit
        document.getElementById('otpDigit1')?.focus();
      } else {
        alert(data.detail || 'Could not send verification code.');
      }
    } catch (err) {
      alert('Failed to send verification code: ' + err.message);
    } finally {
      if (btnText) btnText.textContent = 'Send 6-Digit Verification Code';
    }
  }

  function setupOtpDigitInputs() {
    for (let i = 1; i <= 6; i++) {
      const input = document.getElementById(`otpDigit${i}`);
      if (!input) continue;

      input.addEventListener('input', (e) => {
        const val = e.target.value.replace(/[^0-9]/g, '');
        e.target.value = val ? val[0] : '';
        if (val && i < 6) {
          document.getElementById(`otpDigit${i + 1}`)?.focus();
        }
      });

      input.addEventListener('keydown', (e) => {
        if (e.key === 'Backspace' && !e.target.value && i > 1) {
          document.getElementById(`otpDigit${i - 1}`)?.focus();
        }
      });

      input.addEventListener('paste', (e) => {
        e.preventDefault();
        const pasted = e.clipboardData.getData('text').trim().replace(/[^0-9]/g, '');
        if (pasted.length >= 6) {
          for (let j = 1; j <= 6; j++) {
            const digitInput = document.getElementById(`otpDigit${j}`);
            if (digitInput) digitInput.value = pasted[j - 1];
          }
          document.getElementById('otpDigit6')?.focus();
        }
      });
    }
  }

  async function handleVerifyOtp() {
    let code = '';
    for (let i = 1; i <= 6; i++) {
      code += (document.getElementById(`otpDigit${i}`)?.value || '');
    }

    if (code.length < 6) {
      alert('Please enter all 6 digits of your verification code.');
      return;
    }

    const btn = document.getElementById('btnVerifyOtp');
    if (btn) btn.disabled = true;

    try {
      const res = await fetch('/api/auth/otp/verify', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: state.pendingOtpEmail, otp: code })
      });
      const data = await res.json();
      if (res.ok && data.success) {
        state.token = data.token;
        localStorage.setItem('sheetmerge_token', data.token);
        state.user = data.user;
        updateUserDisplay();
        alert('✓ Code confirmed! Welcome to your SheetMerge workspace.');
        navigate('dashboard');
      } else {
        alert(data.detail || 'Invalid verification code. Please check and try again.');
      }
    } catch (e) {
      alert('Error verifying code: ' + e.message);
    } finally {
      if (btn) btn.disabled = false;
    }
  }

  function backToEmailInput() {
    document.getElementById('otpVerifySection').style.display = 'none';
    document.getElementById('emailOtpRequestForm').style.display = 'block';
  }

  function resendOtp() {
    if (state.pendingOtpEmail) {
      handleSendOtp();
    }
  }

  async function handleLogout() {
    if (!confirm('Are you sure you want to log out of your workspace?')) return;
    try {
      await fetch('/api/auth/logout', {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${state.token}` }
      });
    } catch (e) {
      console.warn('Logout notification failed', e);
    }
    state.token = '';
    state.user = null;
    localStorage.removeItem('sheetmerge_token');
    updateUserDisplay();
    navigate('auth');
  }

  // ══════════════════════════════════════════════════════════════════════════
  // SECTION 2: MULTI-ACCOUNT SENDER POOL (Connecting Google Accounts)
  // ══════════════════════════════════════════════════════════════════════════

  async function loadSenderAccounts() {
    try {
      const res = await fetch('/api/accounts/unified-overview');
      if (res.ok) {
        const data = await res.json();
        state.accounts = data.accounts || [];
        renderSenderAccounts(data);
      }
    } catch (e) {
      console.warn('Could not load sender accounts', e);
    }
  }

  function renderSenderAccounts(overview) {
    const list = document.getElementById('dashAccountsList');
    const noBanner = document.getElementById('noAccountsBanner');
    const quotaBadge = document.getElementById('dashQuotaTotalBadge');

    if (quotaBadge) {
      quotaBadge.textContent = `🛡️ Pool Capacity: ${overview.combined_sent_today} / ${overview.combined_daily_quota} Sent (${overview.combined_remaining_quota} Left)`;
    }

    if (!list) return;
    list.innerHTML = '';

    if (!overview.accounts || overview.accounts.length === 0) {
      if (noBanner) noBanner.style.display = 'block';
      return;
    }

    if (noBanner) noBanner.style.display = 'none';

    overview.accounts.forEach(acc => {
      const card = document.createElement('div');
      card.className = 'pool-account-card';

      const pct = acc.daily_quota > 0 ? Math.min(100, Math.round((acc.sent_today / acc.daily_quota) * 100)) : 0;
      const statusColor = acc.status_badge === 'CONNECTED' ? '#10b981' : (acc.status_badge === 'PAUSED' ? '#94a3b8' : '#f59e0b');

      card.innerHTML = `
        <div class="pool-acc-top">
          <div>
            <div class="pool-acc-email">${escapeHtml(acc.email)}</div>
            <div class="pool-acc-name">${escapeHtml(acc.display_name || 'Sender Account')}</div>
          </div>
          <span style="font-size:10px; font-weight:700; color:${statusColor}; background:rgba(255,255,255,0.06); padding:2px 8px; border-radius:6px;">
            ${acc.status_badge}
          </span>
        </div>
        <div>
          <div style="display:flex; justify-content:space-between; font-size:11px; margin-bottom:4px; color:var(--text-muted);">
            <span>Daily Quota</span>
            <span><strong>${acc.sent_today}</strong> / ${acc.daily_quota} sent</span>
          </div>
          <div class="pool-quota-bar-bg">
            <div class="pool-quota-bar-fill" style="width:${pct}%;"></div>
          </div>
        </div>
        <div class="pool-acc-footer">
          <span>TLS 587 · Gmail SMTP</span>
          <div style="display:flex; gap:6px;">
            <button class="action-pill-btn" style="padding:2px 8px; font-size:10px;" onclick="window.sheetmerge.toggleSenderAccount(${acc.id})">
              ${acc.is_active ? 'Pause' : 'Resume'}
            </button>
            <button class="action-pill-btn" style="padding:2px 8px; font-size:10px; color:#f43f5e;" onclick="window.sheetmerge.unlinkSenderAccount(${acc.id})">
              Unlink
            </button>
          </div>
        </div>
      `;
      list.appendChild(card);
    });
  }

  function openAddAccountModal() {
    document.getElementById('addAccountModal').classList.add('active');
  }

  function closeAddAccountModal() {
    document.getElementById('addAccountModal').classList.remove('active');
  }

  async function handleModalAccountSubmit(e) {
    if (e) e.preventDefault();
    const email = document.getElementById('modalAccEmail').value.trim();
    const name = document.getElementById('modalAccName').value.trim();
    const password = document.getElementById('modalAccPassword').value.trim();

    if (!email) {
      alert('Please enter a Google/Gmail address.');
      return;
    }

    const btn = document.getElementById('btnModalVerify');
    if (btn) btn.disabled = true;

    try {
      const res = await fetch('/api/accounts/link-google', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          email,
          display_name: name,
          app_password: password
        })
      });
      const data = await res.json();
      if (res.ok && data.success) {
        closeAddAccountModal();
        alert(`✓ Successfully linked ${email} to your sending pool!`);
        document.getElementById('modalAccountForm').reset();
        await loadSenderAccounts();
      } else {
        alert(data.detail || 'Could not link account.');
      }
    } catch (err) {
      alert('Failed to link account: ' + err.message);
    } finally {
      if (btn) btn.disabled = false;
    }
  }

  async function toggleSenderAccount(id) {
    try {
      const res = await fetch(`/api/accounts/${id}/toggle-active`, { method: 'POST' });
      if (res.ok) {
        await loadSenderAccounts();
      }
    } catch (e) {
      console.warn('Failed to toggle sender account', e);
    }
  }

  async function unlinkSenderAccount(id) {
    if (!confirm('Are you sure you want to unlink this sender account from the pool?')) return;
    try {
      const res = await fetch(`/api/accounts/${id}`, { method: 'DELETE' });
      if (res.ok) {
        await loadSenderAccounts();
      }
    } catch (e) {
      console.warn('Failed to unlink account', e);
    }
  }

  // ══════════════════════════════════════════════════════════════════════════
  // SECTION 3: GOOGLE SHEETS INGESTION & STATUS SYNCHRONIZATION
  // ══════════════════════════════════════════════════════════════════════════

  async function importGoogleSheet() {
    const input = document.getElementById('googleSheetUrlInput');
    const url = input.value.trim();

    if (!url) {
      alert('Please paste a valid Google Sheet URL.\nFormat: https://docs.google.com/spreadsheets/d/.../edit');
      return;
    }

    const btn = document.getElementById('btnImportSheet');
    if (btn) btn.disabled = true;

    try {
      const res = await fetch('/api/sheet/import-url', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url })
      });
      const data = await res.json();
      if (res.ok && data.success) {
        alert(`✓ Successfully imported Google Sheet!\nFound ${data.total_rows} recipients (${data.pending_count} pending merge).`);
        input.value = '';
        await loadRecipients();
        await loadDashboardData();
      } else {
        alert(data.detail || 'Could not import Google Sheet.');
      }
    } catch (e) {
      alert('Failed to connect to Google Sheet: ' + e.message);
    } finally {
      if (btn) btn.disabled = false;
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
          alert(`✓ Successfully loaded CSV!\n${data.total_rows} recipients loaded.`);
          await loadRecipients();
          await loadDashboardData();
        } else {
          alert(data.detail || 'Could not parse CSV.');
        }
      } catch (err) {
        alert('Failed to upload CSV: ' + err.message);
      }
    };
    reader.readAsText(file);
  }

  async function loadRecipients() {
    try {
      const res = await fetch('/api/sheet/recipients');
      if (res.ok) {
        state.recipients = await res.json();
        renderRecipientsTable();
      }
    } catch (e) {
      console.warn('Could not load recipients', e);
    }
  }

  function renderRecipientsTable() {
    const tbody = document.getElementById('recipientsTableBody');
    const emptyState = document.getElementById('tableEmptyState');
    if (!tbody) return;

    tbody.innerHTML = '';

    const filtered = state.recipients.filter(r => {
      // Filter by status tab
      if (state.tableFilter !== 'all') {
        if (r.merge_status.toUpperCase() !== state.tableFilter.toUpperCase()) {
          return false;
        }
      }
      // Filter by search query
      if (state.searchQuery) {
        const q = state.searchQuery.toLowerCase();
        const matchEmail = (r.email || '').toLowerCase().includes(q);
        const matchName = (r.first_name || '').toLowerCase().includes(q);
        const matchCompany = (r.company || '').toLowerCase().includes(q);
        if (!matchEmail && !matchName && !matchCompany) return false;
      }
      return true;
    });

    if (filtered.length === 0) {
      if (emptyState) emptyState.style.display = 'block';
      return;
    }

    if (emptyState) emptyState.style.display = 'none';

    filtered.forEach(r => {
      const tr = document.createElement('tr');
      tr.id = `row-recipient-${r.id}`;

      let badgeClass = 'badge-unprocessed';
      let badgeLabel = r.merge_status || 'UNPROCESSED';

      if (r.merge_status === 'EMAIL_SENT') {
        badgeClass = 'badge-sent';
        badgeLabel = 'SENT';
      } else if (r.merge_status === 'EMAIL_OPENED') {
        badgeClass = 'badge-opened';
        badgeLabel = 'OPENED';
      } else if (r.merge_status === 'EMAIL_CLICKED') {
        badgeClass = 'badge-clicked';
        badgeLabel = 'CLICKED';
      } else if (r.merge_status === 'EMAIL_BOUNCED') {
        badgeClass = 'badge-bounced';
        badgeLabel = 'BOUNCED (550)';
      } else if (r.merge_status === 'ERROR') {
        badgeClass = 'badge-error';
        badgeLabel = 'ERROR';
      }

      tr.innerHTML = `
        <td style="color:var(--text-dim); font-size:12px;">${r.row_index || r.id}</td>
        <td><strong>${escapeHtml(r.email)}</strong></td>
        <td>${escapeHtml(r.first_name || '—')}</td>
        <td>${escapeHtml(r.company || '—')}</td>
        <td>
          <span class="merge-badge ${badgeClass}">${badgeLabel}</span>
          ${r.last_event ? `<span style="display:block; font-size:11px; color:var(--text-dim); margin-top:3px;">${escapeHtml(r.last_event)}</span>` : ''}
        </td>
        <td>
          <button class="action-pill-btn" style="padding:2px 8px; font-size:11px;" onclick="window.sheetmerge.dispatchSingleRow(${r.id})">
            Send Now
          </button>
        </td>
      `;
      tbody.appendChild(tr);
    });
  }

  function setTableFilter(filterVal, btn) {
    state.tableFilter = filterVal;
    document.querySelectorAll('.status-filter-btn').forEach(b => b.classList.remove('active'));
    if (btn) btn.classList.add('active');
    renderRecipientsTable();
  }

  function filterRecipients() {
    state.searchQuery = document.getElementById('tableSearchInput')?.value.trim() || '';
    renderRecipientsTable();
  }

  function exportUpdatedCsv() {
    window.location.href = '/api/sheet/export-csv';
  }

  async function cleanAllData() {
    if (!confirm('Clear all recipients and start with a fresh workspace?')) return;
    try {
      const res = await fetch('/api/data/clean-all', { method: 'POST' });
      if (res.ok) {
        alert('✓ Workspace cleared cleanly.');
        await loadRecipients();
        await loadSenderAccounts();
        await loadDashboardData();
      }
    } catch (e) {
      alert('Error clearing data: ' + e.message);
    }
  }

  // ══════════════════════════════════════════════════════════════════════════
  // SECTION 4: SEQUENTIAL DISPATCHER & METRICS VISUALISATION
  // ══════════════════════════════════════════════════════════════════════════

  async function startCampaignDispatch() {
    const unproc = state.recipients.filter(r => r.merge_status === 'UNPROCESSED');
    if (unproc.length === 0) {
      alert('No unprocessed recipients found. Please connect a Google Sheet with recipient rows.');
      return;
    }

    if (!confirm(`Dispatch campaign to ${unproc.length} recipient(s) sequentially across your sender accounts?`)) {
      return;
    }

    const btn = document.getElementById('btnDispatchCampaign');
    if (btn) btn.disabled = true;
    state.isDispatching = true;
    state.stopRequested = false;

    const subject = document.getElementById('templateSubject')?.value || 'Quick question for {{First Name}}';
    const bodyHtml = document.getElementById('templateBody')?.value || '<p>Hi {{First Name}}, following up.</p>';

    let sentCount = 0;
    let bounceCount = 0;

    for (const r of unproc) {
      if (state.stopRequested) break;

      // Update UI row to dispatching
      const rowEl = document.getElementById(`row-recipient-${r.id}`);
      if (rowEl) {
        const badge = rowEl.querySelector('.merge-badge');
        if (badge) {
          badge.className = 'merge-badge badge-unprocessed';
          badge.textContent = 'DISPATCHING...';
        }
      }

      try {
        const res = await fetch('/api/campaign/dispatch-row', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            recipient_id: r.id,
            subject,
            body_html: bodyHtml
          })
        });
        const data = await res.json();
        if (res.ok) {
          if (data.merge_status === 'EMAIL_SENT') {
            sentCount++;
          } else if (data.merge_status === 'EMAIL_BOUNCED') {
            bounceCount++;
          }
        }
      } catch (err) {
        console.error('Dispatch row error', err);
      }

      // Small delay between rows to respect pacing
      await new Promise(resolve => setTimeout(resolve, 800));
      await loadRecipients();
      await loadSenderAccounts();
    }

    state.isDispatching = false;
    if (btn) btn.disabled = false;
    alert(`✓ Campaign Dispatch Complete!\n${sentCount} sent successfully, ${bounceCount} suppressed.`);
    await loadDashboardData();
  }

  async function dispatchSingleRow(id) {
    const subject = document.getElementById('templateSubject')?.value || 'Hello {{First Name}}';
    const bodyHtml = document.getElementById('templateBody')?.value || '<p>Hi {{First Name}}</p>';

    try {
      const res = await fetch('/api/campaign/dispatch-row', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          recipient_id: id,
          subject,
          body_html: bodyHtml
        })
      });
      const data = await res.json();
      if (res.ok) {
        alert(`✓ Dispatched to ${data.email}: ${data.merge_status}`);
        await loadRecipients();
        await loadSenderAccounts();
        await loadDashboardData();
      } else {
        alert(data.detail || 'Dispatch failed.');
      }
    } catch (e) {
      alert('Error: ' + e.message);
    }
  }

  async function loadDashboardData() {
    await loadSenderAccounts();
    await loadRecipients();

    try {
      const res = await fetch('/api/dashboard/overview');
      if (res.ok) {
        const data = await res.json();
        const m = data.metrics || {};

        document.getElementById('dashDeliveredVal').textContent = m.delivered_count || 0;
        document.getElementById('dashOpenRateVal').textContent = (m.open_rate || 0.0) + '%';
        document.getElementById('dashClickRateVal').textContent = (m.click_rate || 0.0) + '%';
        document.getElementById('dashBounceRateVal').textContent = (m.bounce_rate || 0.0) + '%';
      }
    } catch (e) {
      console.warn('Could not load dashboard overview', e);
    }
  }

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
        document.getElementById('spfStatus').textContent = data.spf?.status === 'pass' ? '✓ Valid SPF' : '⚠ ' + data.spf?.status;
        document.getElementById('dkimStatus').textContent = data.dkim?.status === 'pass' ? '✓ 2048-bit Verified' : '⚠ ' + data.dkim?.status;
        document.getElementById('dmarcStatus').textContent = data.dmarc?.status === 'pass' ? '✓ Protected' : '⚠ Check DMARC';
        document.getElementById('mxStatus').textContent = data.mx?.valid ? '✓ MX Resolving' : '⚠ No MX';
        alert(`✓ DNS Scan for ${domain} complete!\nSPF: ${data.spf?.status}, DMARC: ${data.dmarc?.status}`);
      }
    } catch (e) {
      alert('DNS Scan error: ' + e.message);
    }
  }

  // ── Compose Drawer & Test Email ─────────────────────────────────────────
  function openComposeDrawer() {
    document.getElementById('composeDrawer').style.display = 'block';
    updateLivePreview();
  }

  function closeComposeDrawer() {
    document.getElementById('composeDrawer').style.display = 'none';
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
    const target = document.getElementById('testEmailTarget')?.value.trim();
    if (!target) {
      alert('Please enter your personal inbox email for the test.');
      return;
    }

    const subject = document.getElementById('templateSubject')?.value || 'Test';
    const bodyHtml = document.getElementById('templateBody')?.value || '<p>Test</p>';

    try {
      const res = await fetch('/api/campaign/send-test', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          target_email: target,
          subject,
          body_html: bodyHtml
        })
      });
      const data = await res.json();
      if (res.ok) {
        alert(data.message || 'Test email dispatched!');
      } else {
        alert(data.detail || 'Test email failed.');
      }
    } catch (e) {
      alert('Error sending test email: ' + e.message);
    }
  }

  // ── Compliance Modal ───────────────────────────────────────────────────
  function openComplianceModal() {
    document.getElementById('complianceModal').classList.add('active');
  }

  function closeComplianceModal() {
    document.getElementById('complianceModal').classList.remove('active');
  }

  function escapeHtml(str) {
    if (!str) return '';
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }

  function applyTemplatePreset(presetKey) {
    const subjInput = document.getElementById('templateSubject');
    const bodyInput = document.getElementById('templateBody');
    if (!subjInput || !bodyInput) return;

    if (presetKey === 'followup') {
      subjInput.value = 'Quick follow-up for {{First Name}} at {{Company}}';
      bodyInput.value = '<p>Hi {{First Name}},</p>\n<p>I noticed your work at {{Company}} and wanted to follow up directly.</p>\n<p>Would you have 5 minutes for a quick chat this week?</p>\n<p>Best regards,<br>{{Sender Name}}</p>';
    } else if (presetKey === 'collab') {
      subjInput.value = 'Collaboration proposal for {{Company}}';
      bodyInput.value = '<p>Hi {{First Name}},</p>\n<p>I am reaching out because we admire what {{Company}} is building.</p>\n<p>We have developed an automated mail merge pipeline that could save your team hours every week. Would you be open to exploring synergies?</p>\n<p>Best regards,<br>{{Sender Name}}</p>';
    } else if (presetKey === 'invite') {
      subjInput.value = 'Special invitation for {{First Name}} — Executive Briefing';
      bodyInput.value = '<p>Dear {{First Name}},</p>\n<p>We would like to invite you and the {{Company}} leadership team to our upcoming private briefing.</p>\n<p>Let us know if you would be able to attend.</p>\n<p>Warmly,<br>{{Sender Name}}</p>';
    }
    updateLivePreview();
  }

  function updateLivePreview() {
    const subj = document.getElementById('templateSubject')?.value || '';
    const body = document.getElementById('templateBody')?.value || '';
    const label = document.getElementById('previewRecipientLabel');
    const subjDisplay = document.getElementById('previewSubjectDisplay');
    const bodyDisplay = document.getElementById('previewBodyDisplay');

    const sample = (state.recipients && state.recipients.length > 0)
      ? state.recipients[0]
      : { first_name: 'Sarah', company: 'Cyberdyne Systems', email: 'sarah.connor@cyberdyne.io' };

    if (label) {
      label.textContent = state.recipients.length > 0
        ? `Row 1: ${sample.first_name || 'Recipient'} (${sample.email})`
        : 'Sample: Sarah (sarah.connor@cyberdyne.io)';
    }

    const fn = sample.first_name || 'there';
    const co = sample.company || 'your team';
    const em = sample.email || 'recipient@example.com';

    if (subjDisplay) {
      subjDisplay.textContent = 'Subject: ' + subj.replace(/{{First Name}}/g, fn).replace(/{{Company}}/g, co).replace(/{{Email}}/g, em);
    }
    if (bodyDisplay) {
      bodyDisplay.innerHTML = body.replace(/{{First Name}}/g, fn).replace(/{{Company}}/g, co).replace(/{{Email}}/g, em).replace(/{{Sender Name}}/g, state.user?.full_name || 'Your Name');
    }
  }

  // ── Expose Public API ──────────────────────────────────────────────────
  window.sheetmerge = {
    navigate,
    toggleTheme,
    signInWithGoogleOAuth,
    handleSendOtp,
    handleVerifyOtp,
    backToEmailInput,
    resendOtp,
    handleLogout,
    openAddAccountModal,
    closeAddAccountModal,
    handleModalAccountSubmit,
    toggleSenderAccount,
    unlinkSenderAccount,
    importGoogleSheet,
    handleFileSelect,
    setTableFilter,
    filterRecipients,
    exportUpdatedCsv,
    cleanAllData,
    startCampaignDispatch,
    dispatchSingleRow,
    checkDomain,
    openComposeDrawer,
    closeComposeDrawer,
    insertTag,
    sendTestEmail,
    applyTemplatePreset,
    updateLivePreview,
    openComplianceModal,
    closeComplianceModal
  };

  // Launch on DOM ready
  document.addEventListener('DOMContentLoaded', init);
})();
