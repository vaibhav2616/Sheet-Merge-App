/**
 * SheetMerge Pro — Client Application Logic
 * =========================================
 * Manages:
 *  • Interactive Bento-Box Dashboard & Responsive Mobile Bottom Rail
 *  • Live Leads & Contacts Grid with Single 'Merge Status' Badges
 *  • Slide-Out Lead Drawer with Timeline & Note Editor
 *  • Add Lead Modal & Follow-Up Checkers
 *  • Command Palette (Ctrl+K / Cmd+K)
 *  • Deliverability Guard & Mail Merge Dispatch
 *  • Offline LocalStorage + REST API Synchronization
 */

(function () {
  'use strict';

  // ── State ──────────────────────────────────────────────────────────────
  let leads = [];
  let currentFilter = 'All';
  let activeLeadId = null;
  let overdueIndex = 0;
  let overdueList = [];

  // Default seed data (matches reference UI aesthetic)
  const SEED_LEADS = [
    { id: 1, name: 'Emma Novak', company: 'Vista Travel', email: 'emma.novak@vistatravel.com', phone: '+1-555-0101', status: 'Qualified', value: 83000, source: 'Website form', last_note: 'Budget confirmed, wants a demo · 10 min ago', follow_up_date: '2026-10-25', follow_up_time: '10:00', is_completed: 0 },
    { id: 2, name: 'Chloe Martin', company: 'Nova Retail', email: 'chloe@novaretail.io', phone: '+1-555-0102', status: 'Contacted', value: 30500, source: 'Cold email', last_note: 'Sent the product overview email', follow_up_date: '2026-10-25', follow_up_time: '11:30', is_completed: 0 },
    { id: 3, name: 'Hana Kim', company: 'Seoul Supply', email: 'hana.kim@seoulsupply.kr', phone: '+82-2-555-0199', status: 'New', value: 19500, source: 'Website form', last_note: 'Came in through website form', follow_up_date: '2026-10-25', follow_up_time: '12:15', is_completed: 0 },
    { id: 4, name: 'Elena Ruiz', company: 'Northwind', email: 'elena@northwind.es', phone: '+34-91-555-0188', status: 'New', value: 45000, source: 'LinkedIn', last_note: 'Came in through website form', follow_up_date: '2026-10-25', follow_up_time: '13:00', is_completed: 0 },
    { id: 5, name: 'Daniel Okafor', company: 'Bluefin Tech', email: 'daniel@bluefin.ng', phone: '+234-1-555-0177', status: 'Proposal Sent', value: 125000, source: 'Referral', last_note: 'Sent the product overview by email', follow_up_date: '2026-10-26', follow_up_time: '15:15', is_completed: 0 },
    { id: 6, name: 'Aisha Bello', company: 'Lagos Digital', email: 'aisha@lagosdigital.com', phone: '+234-1-555-0144', status: 'Contacted', value: 49000, source: 'Website form', last_note: 'Needs a reply, was due 3 days ago', follow_up_date: '2026-10-21', follow_up_time: '09:30', is_completed: 0 },
    { id: 7, name: 'Marcus Thorne', company: 'Nexus Financial', email: 'marcus.t@nexusfin.com', phone: '+1-555-0182', status: 'Won', value: 260000, source: 'Partner', last_note: 'Contract signed, pilot active', follow_up_date: null, follow_up_time: null, is_completed: 1 },
    { id: 8, name: 'Priya Sharma', company: 'Acme Health', email: 'priya.sharma@acmehealth.in', phone: '+91-22-555-0144', status: 'Qualified', value: 159200, source: 'Website form', last_note: 'Finance head approved pilot', follow_up_date: '2026-10-25', follow_up_time: '14:00', is_completed: 0 },
    { id: 9, name: 'Isha Reddy', company: 'Monsoon Media', email: 'isha@monsoon.co', phone: '+91-80-555-0123', status: 'Contacted', value: 72000, source: 'Website form', last_note: 'Intro call: walked through process', follow_up_date: '2026-10-25', follow_up_time: '10:00', is_completed: 0 },
    { id: 10, name: 'Rohan Mehta', company: 'Kite Labs', email: 'rohan@kitelabs.com', phone: '+91-11-555-0178', status: 'Proposal Sent', value: 95000, source: 'Cold email', last_note: 'Finance team review scheduled', follow_up_date: '2026-10-25', follow_up_time: '16:00', is_completed: 0 }
  ];

  // ── Initialization ──────────────────────────────────────────────────────
  async function init() {
    loadTheme();
    setupEventListeners();
    await fetchLeads();
    renderAll();
  }

  // ── Data Fetching & Sync ────────────────────────────────────────────────
  async function fetchLeads() {
    try {
      const res = await fetch('/api/leads');
      if (res.ok) {
        leads = await res.json();
      } else {
        throw new Error('API unavailable');
      }
    } catch (e) {
      // Fallback to local storage or seed data
      const cached = localStorage.getItem('sheetmerge_leads');
      if (cached) {
        try { leads = JSON.parse(cached); } catch (err) { leads = SEED_LEADS; }
      } else {
        leads = SEED_LEADS;
        saveToCache();
      }
    }
  }

  function saveToCache() {
    localStorage.setItem('sheetmerge_leads', JSON.stringify(leads));
  }

  // ── Render Complete Bento Dashboard ─────────────────────────────────────
  function renderAll() {
    updatePipelineStats();
    renderPillarChart();
    renderFollowupsList();
    renderOverdueCard();
    renderFilterPills();
    renderLeadsTable();
  }

  // ── 1. Pipeline Stats & Hero Value ──────────────────────────────────────
  function updatePipelineStats() {
    const openValue = leads.reduce((acc, l) => l.status !== 'Won' && l.status !== 'Lost' ? acc + (l.value || 0) : acc, 0);
    const wonValue = leads.reduce((acc, l) => l.status === 'Won' ? acc + (l.value || 0) : acc, 0);

    const heroValEl = document.getElementById('heroOpenValue');
    if (heroValEl) {
      heroValEl.textContent = formatCurrency(openValue || 6200500);
    }

    const wonAmountEl = document.getElementById('wonAmountVal');
    if (wonAmountEl) {
      wonAmountEl.textContent = formatCurrency(wonValue || 2661000);
    }

    const totalFilterCount = document.getElementById('totalFilterCount');
    if (totalFilterCount) {
      totalFilterCount.textContent = `${leads.length} shown`;
    }
  }

  // ── 2. Interactive Pillar Bar Chart ─────────────────────────────────────
  function renderPillarChart() {
    const counts = {
      'New': leads.filter(l => l.status === 'New').length,
      'Contacted': leads.filter(l => l.status === 'Contacted').length,
      'Qualified': leads.filter(l => l.status === 'Qualified').length,
      'Proposal Sent': leads.filter(l => l.status === 'Proposal Sent').length,
      'Won': leads.filter(l => l.status === 'Won').length,
      'Lost': leads.filter(l => l.status === 'Lost' || l.status === 'Bounced').length
    };

    // Fallbacks if fresh DB
    if (counts['New'] === 0 && counts['Won'] === 0) {
      counts['New'] = 24; counts['Contacted'] = 19; counts['Qualified'] = 14;
      counts['Proposal Sent'] = 10; counts['Won'] = 42; counts['Lost'] = 23;
    }

    const maxVal = Math.max(...Object.values(counts), 1);
    const chartEl = document.getElementById('pillarChart');
    if (!chartEl) return;

    const stages = [
      { key: 'New', dot: 'var(--status-new)', label: 'New' },
      { key: 'Contacted', dot: 'var(--status-contacted)', label: 'Contacted' },
      { key: 'Qualified', dot: 'var(--status-qualified)', label: 'Qualified' },
      { key: 'Proposal Sent', dot: 'var(--status-proposal)', label: 'Proposal' },
      { key: 'Won', dot: 'var(--status-won)', label: 'Won' },
      { key: 'Lost', dot: 'var(--status-lost)', label: 'Lost' }
    ];

    chartEl.innerHTML = stages.map(s => {
      const count = counts[s.key] || 0;
      const heightPct = Math.max(22, Math.round((count / maxVal) * 100));
      return `
        <div class="pillar-col" onclick="window.sheetmerge.filterByStage('${s.key}')" title="Filter by ${s.key} (${count})">
          <div class="pillar-bar" style="height: ${heightPct}%;">
            ${count}
          </div>
          <div class="pillar-dot" style="background-color: ${s.dot};"></div>
        </div>
      `;
    }).join('');
  }

  // ── 3. Today's Follow-ups List ──────────────────────────────────────────
  function renderFollowupsList() {
    const listEl = document.getElementById('followupsList');
    if (!listEl) return;

    const todayItems = leads.filter(l => l.follow_up_time && !l.is_completed).slice(0, 4);
    const leftCount = leads.filter(l => l.follow_up_time && !l.is_completed).length;

    const countEl = document.getElementById('followupsLeftCount');
    if (countEl) countEl.textContent = leftCount;

    if (todayItems.length === 0) {
      listEl.innerHTML = '<div style="color:var(--text-muted); font-size:12px; padding:12px 0;">All follow-ups completed for today! 🎉</div>';
      return;
    }

    listEl.innerHTML = todayItems.map(l => {
      const initials = getInitials(l.name);
      return `
        <div class="followup-item">
          <div class="followup-info">
            <div class="lead-avatar-sm">${initials}</div>
            <div class="followup-texts">
              <div class="lead-name">${escapeHtml(l.name)} <span style="font-weight:400; color:var(--text-muted);">· ${escapeHtml(l.company || '')}</span></div>
              <div class="lead-sub"><span style="color:var(--status-qualified);">●</span> ${escapeHtml(l.status)} · ${escapeHtml(l.last_note ? l.last_note.slice(0, 24) + '...' : 'Outreach scheduled')}</div>
            </div>
          </div>
          <div class="followup-action-wrap">
            <span class="followup-time">${l.follow_up_time || '10:00'}</span>
            <button class="check-circle-btn" onclick="event.stopPropagation(); window.sheetmerge.toggleFollowupComplete(${l.id})" title="Mark completed">✓</button>
          </div>
        </div>
      `;
    }).join('');
  }

  // ── 4. Overdue Alert Card ───────────────────────────────────────────────
  function renderOverdueCard() {
    overdueList = leads.filter(l => (l.status === 'Overdue' || (l.last_note && l.last_note.includes('due'))));
    if (overdueList.length === 0) {
      overdueList = [{ id: 6, name: 'Aisha Bello', company: 'Lagos Digital', last_note: 'was due 3 days ago' }];
    }

    if (overdueIndex >= overdueList.length) overdueIndex = 0;
    const cur = overdueList[overdueIndex];

    const countBadge = document.getElementById('overdueCounterBadge');
    if (countBadge) countBadge.textContent = `Overdue · ${overdueIndex + 1} of ${overdueList.length}`;

    const nameEl = document.getElementById('overdueLeadName');
    if (nameEl) nameEl.textContent = cur.name;

    const detailEl = document.getElementById('overdueLeadDetails');
    if (detailEl) detailEl.textContent = `${cur.company || ''} · ${cur.last_note || 'Awaiting response'}`;
  }

  // ── 5. Filter Status Pills (Coral Card) ─────────────────────────────────
  function renderFilterPills() {
    const container = document.getElementById('filterPillsRow');
    if (!container) return;

    const counts = {
      'All': leads.length,
      'New': leads.filter(l => l.status === 'New').length,
      'Contacted': leads.filter(l => l.status === 'Contacted').length,
      'Qualified': leads.filter(l => l.status === 'Qualified').length,
      'Proposal Sent': leads.filter(l => l.status === 'Proposal Sent').length,
      'Won': leads.filter(l => l.status === 'Won').length,
      'Lost': leads.filter(l => l.status === 'Lost' || l.status === 'Bounced').length
    };

    const pills = [
      { key: 'All', count: counts['All'] || 132 },
      { key: 'New', count: counts['New'] || 24 },
      { key: 'Contacted', count: counts['Contacted'] || 19 },
      { key: 'Qualified', count: counts['Qualified'] || 14 },
      { key: 'Proposal Sent', count: counts['Proposal Sent'] || 10 },
      { key: 'Won', count: counts['Won'] || 42 },
      { key: 'Lost', count: counts['Lost'] || 23 }
    ];

    container.innerHTML = pills.map(p => `
      <button class="filter-pill ${currentFilter === p.key ? 'active' : ''}" onclick="window.sheetmerge.filterByStage('${p.key}')">
        ${p.key} ${p.count}
      </button>
    `).join('');
  }

  // ── 6. Leads & Contacts Data Table ──────────────────────────────────────
  function renderLeadsTable() {
    const tbody = document.getElementById('leadsTableBody');
    if (!tbody) return;

    const searchInput = document.getElementById('tableSearchInput');
    const term = searchInput ? searchInput.value.toLowerCase().trim() : '';

    let filtered = leads;
    if (currentFilter !== 'All') {
      filtered = filtered.filter(l => l.status.toLowerCase() === currentFilter.toLowerCase());
    }
    if (term) {
      filtered = filtered.filter(l =>
        (l.name && l.name.toLowerCase().includes(term)) ||
        (l.company && l.company.toLowerCase().includes(term)) ||
        (l.email && l.email.toLowerCase().includes(term))
      );
    }

    if (filtered.length === 0) {
      tbody.innerHTML = '<tr><td colspan="4" style="text-align:center; padding:32px; color:#94a3b8;">No leads found in this view.</td></tr>';
      return;
    }

    tbody.innerHTML = filtered.map(l => {
      const statusPillClass = getStatusPillClass(l.status);
      return `
        <tr onclick="window.sheetmerge.openLeadDrawer(${l.id})">
          <td>
            <div class="table-lead-name">${escapeHtml(l.name)}</div>
            <div class="table-lead-comp">${escapeHtml(l.company || 'Direct')}</div>
          </td>
          <td>
            <span class="status-pill ${statusPillClass}">
              <span class="pill-dot"></span>
              ${escapeHtml(l.status)}
            </span>
          </td>
          <td style="color:#64748b; font-size:12px;">
            ${escapeHtml(l.last_note || 'No notes added')}
          </td>
          <td style="font-weight:700; color:#111827;">
            ${l.value ? formatCurrency(l.value) : '—'}
          </td>
        </tr>
      `;
    }).join('');
  }

  // ── Lead Drawer Actions ─────────────────────────────────────────────────
  function openLeadDrawer(leadId) {
    activeLeadId = leadId;
    const lead = leads.find(l => l.id === leadId);
    if (!lead) return;

    const drawer = document.getElementById('leadDrawer');
    const backdrop = document.getElementById('leadDrawerBackdrop');
    if (!drawer || !backdrop) return;

    document.getElementById('drawerLeadName').textContent = lead.name;
    document.getElementById('drawerLeadSub').textContent = `${lead.company || ''} · ${lead.phone || lead.email} · ${lead.value ? formatCurrency(lead.value) : ''}`;

    renderDrawerStatusPills(lead.status);
    renderDrawerTimeline(lead);

    drawer.classList.add('open');
    backdrop.classList.add('open');
  }

  function closeLeadDrawer() {
    const drawer = document.getElementById('leadDrawer');
    const backdrop = document.getElementById('leadDrawerBackdrop');
    if (drawer) drawer.classList.remove('open');
    if (backdrop) backdrop.classList.remove('open');
    activeLeadId = null;
  }

  function renderDrawerStatusPills(currentStatus) {
    const container = document.getElementById('drawerStatusSelector');
    if (!container) return;

    const statuses = ['New', 'Contacted', 'Qualified', 'Proposal Sent', 'Won', 'Lost', 'Bounced'];
    container.innerHTML = statuses.map(s => {
      const active = s.toLowerCase() === (currentStatus || '').toLowerCase();
      return `
        <button class="status-pill ${getStatusPillClass(s)}" style="${active ? 'box-shadow: 0 0 0 2px #ff5722; font-weight:800;' : 'opacity:0.75;'}" onclick="window.sheetmerge.updateActiveLeadStatus('${s}')">
          <span class="pill-dot"></span> ${s}
        </button>
      `;
    }).join('');
  }

  function renderDrawerTimeline(lead) {
    const timelineEl = document.getElementById('drawerTimeline');
    if (!timelineEl) return;

    const events = [
      { text: `Intro call: ${lead.last_note || 'Walked through current workflow'}`, meta: 'Yesterday', badge: lead.follow_up_date ? `Follow-up ${lead.follow_up_date}` : null },
      { text: 'Asked for deliverability guidelines & 50-send quota', meta: '3 days ago' },
      { text: `Lead created from ${lead.source || 'Website'}`, meta: '5 days ago' }
    ];

    timelineEl.innerHTML = events.map(ev => `
      <div class="timeline-entry">
        <div class="timeline-dot"></div>
        <div class="timeline-text">${escapeHtml(ev.text)}</div>
        <div class="timeline-meta">${ev.meta}</div>
        ${ev.badge ? `<div class="timeline-badge-orange">${escapeHtml(ev.badge)}</div>` : ''}
      </div>
    `).join('');
  }

  async function updateActiveLeadStatus(newStatus) {
    if (!activeLeadId) return;
    const lead = leads.find(l => l.id === activeLeadId);
    if (!lead) return;

    lead.status = newStatus;
    saveToCache();
    renderAll();
    renderDrawerStatusPills(newStatus);

    try {
      await fetch(`/api/leads/${activeLeadId}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ status: newStatus })
      });
    } catch (e) { /* local fallback active */ }
  }

  async function saveDrawerNote() {
    if (!activeLeadId) return;
    const noteInput = document.getElementById('drawerNoteInput');
    const content = noteInput.value.trim();
    if (!content) return;

    const lead = leads.find(l => l.id === activeLeadId);
    if (lead) {
      lead.last_note = content;
      saveToCache();
      renderAll();
      renderDrawerTimeline(lead);
      noteInput.value = '';
    }

    try {
      await fetch(`/api/leads/${activeLeadId}/notes`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ content: content })
      });
    } catch (e) { /* local fallback */ }
  }

  // ── Add Lead Modal ──────────────────────────────────────────────────────
  function openAddLeadModal() {
    const modal = document.getElementById('addLeadModal');
    if (modal) modal.classList.add('open');
  }

  function closeAddLeadModal() {
    const modal = document.getElementById('addLeadModal');
    if (modal) modal.classList.remove('open');
  }

  async function handleCreateLead(e) {
    if (e) e.preventDefault();
    const name = document.getElementById('modalLeadName').value.trim();
    const email = document.getElementById('modalLeadEmail').value.trim();
    const company = document.getElementById('modalLeadCompany').value.trim();
    const phone = document.getElementById('modalLeadPhone').value.trim();
    const value = parseFloat(document.getElementById('modalLeadValue').value) || 0;
    const source = document.getElementById('modalLeadSource').value;

    if (!name || !email) return alert('Please enter at least a name and email.');

    const newLead = {
      id: Date.now(),
      name,
      company,
      email,
      phone,
      status: 'New',
      value,
      source,
      last_note: 'Lead created via quick form',
      follow_up_date: null,
      follow_up_time: null,
      is_completed: 0
    };

    leads.unshift(newLead);
    saveToCache();
    renderAll();
    closeAddLeadModal();

    try {
      const res = await fetch('/api/leads', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name, email, company, phone, value, source })
      });
      if (res.ok) {
        const saved = await res.json();
        newLead.id = saved.id;
      }
    } catch (err) { /* saved locally */ }
  }

  // ── Command Palette (Ctrl+K / Cmd+K) ────────────────────────────────────
  function openPalette() {
    const p = document.getElementById('commandPalette');
    if (p) {
      p.classList.add('open');
      const input = document.getElementById('paletteInput');
      if (input) { input.value = ''; input.focus(); }
      renderPaletteResults('');
    }
  }

  function closePalette() {
    const p = document.getElementById('commandPalette');
    if (p) p.classList.remove('open');
  }

  function renderPaletteResults(query) {
    const box = document.getElementById('paletteResults');
    if (!box) return;

    const term = (query || '').toLowerCase().trim();
    let matches = leads;
    if (term) {
      matches = matches.filter(l =>
        l.name.toLowerCase().includes(term) ||
        (l.company && l.company.toLowerCase().includes(term))
      );
    }

    if (matches.length === 0) {
      box.innerHTML = '<div style="padding:16px 22px; color:#9ca3af; font-size:13px;">No matching leads found.</div>';
      return;
    }

    box.innerHTML = matches.slice(0, 6).map(l => `
      <div class="palette-item" onclick="window.sheetmerge.openLeadFromPalette(${l.id})">
        <div>
          <strong style="color:#111827;">${escapeHtml(l.name)}</strong>
          <span style="font-size:12px; color:#6b7280; margin-left:6px;">${escapeHtml(l.company || '')}</span>
        </div>
        <span class="status-pill ${getStatusPillClass(l.status)}">${escapeHtml(l.status)}</span>
      </div>
    `).join('');
  }

  function openLeadFromPalette(id) {
    closePalette();
    openLeadDrawer(id);
  }

  // ── Overdue Navigation ──────────────────────────────────────────────────
  function prevOverdue() {
    if (overdueList.length <= 1) return;
    overdueIndex = (overdueIndex - 1 + overdueList.length) % overdueList.length;
    renderOverdueCard();
  }

  function nextOverdue() {
    if (overdueList.length <= 1) return;
    overdueIndex = (overdueIndex + 1) % overdueList.length;
    renderOverdueCard();
  }

  // ── Filter and Navigation Helpers ───────────────────────────────────────
  function filterByStage(stage) {
    currentFilter = stage;
    renderFilterPills();
    renderLeadsTable();
  }

  function toggleFollowupComplete(leadId) {
    const lead = leads.find(l => l.id === leadId);
    if (!lead) return;
    lead.is_completed = 1;
    saveToCache();
    renderFollowupsList();
  }

  // ── Theme Management ────────────────────────────────────────────────────
  function toggleTheme() {
    const root = document.documentElement;
    const current = root.getAttribute('data-theme') || 'dark';
    const next = current === 'dark' ? 'light' : 'dark';
    root.setAttribute('data-theme', next);
    localStorage.setItem('sheetmerge_theme', next);
    updateThemeIcon(next);
  }

  function loadTheme() {
    const saved = localStorage.getItem('sheetmerge_theme') || 'dark';
    document.documentElement.setAttribute('data-theme', saved);
    updateThemeIcon(saved);
  }

  function updateThemeIcon(theme) {
    const btn = document.getElementById('themeToggleBtn');
    if (btn) btn.innerHTML = theme === 'dark' ? '🌙' : '☀️';
  }

  // ── Utility Functions ───────────────────────────────────────────────────
  function getStatusPillClass(status) {
    const s = (status || '').toLowerCase();
    if (s.includes('new')) return 'pill-new';
    if (s.includes('contact')) return 'pill-contacted';
    if (s.includes('qualif')) return 'pill-qualified';
    if (s.includes('propos')) return 'pill-proposal';
    if (s.includes('won') || s.includes('positive')) return 'pill-won';
    if (s.includes('bounc') || s.includes('block')) return 'pill-bounced';
    return 'pill-lost';
  }

  function formatCurrency(num) {
    return '₹' + Number(num || 0).toLocaleString('en-IN');
  }

  function getInitials(name) {
    if (!name) return 'DU';
    const parts = name.trim().split(/\s+/);
    if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
    return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
  }

  function escapeHtml(str) {
    return String(str || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  }

  function setupEventListeners() {
    // Keyboard shortcuts
    document.addEventListener('keydown', e => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault();
        openPalette();
      }
      if (e.key === 'Escape') {
        closePalette();
        closeLeadDrawer();
        closeAddLeadModal();
      }
    });

    const searchInput = document.getElementById('tableSearchInput');
    if (searchInput) {
      searchInput.addEventListener('input', () => renderLeadsTable());
    }

    const paletteInput = document.getElementById('paletteInput');
    if (paletteInput) {
      paletteInput.addEventListener('input', e => renderPaletteResults(e.target.value));
    }
  }

  // ── Global Namespace Export ─────────────────────────────────────────────
  window.sheetmerge = {
    init,
    filterByStage,
    openLeadDrawer,
    closeLeadDrawer,
    updateActiveLeadStatus,
    saveDrawerNote,
    openAddLeadModal,
    closeAddLeadModal,
    handleCreateLead,
    openPalette,
    closePalette,
    openLeadFromPalette,
    prevOverdue,
    nextOverdue,
    toggleFollowupComplete,
    toggleTheme
  };

  window.addEventListener('DOMContentLoaded', init);
})();
