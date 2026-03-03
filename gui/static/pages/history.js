// pages/history.js — Session history with star + delete

const TABS = [
  { key: '',        label: 'All' },
  { key: 'grammar', label: '✏️ Grammar' },
  { key: 'vocab',   label: '🃏 Vocab' },
  { key: 'reading', label: '📖 Reading' },
  { key: 'writing', label: '📝 Writing' },
  { key: 'chat',    label: '💬 Chat' },
];

let _activeTab = '';

export async function render(el) {
  el.innerHTML = `
    <h1>📋 History</h1>
    <div id="tab-bar" style="display:flex;gap:6px;flex-wrap:wrap;margin-bottom:20px">
      ${TABS.map(t => `
        <button class="btn ${t.key === _activeTab ? 'btn-primary' : 'btn-outline'} tab-btn"
          data-mode="${t.key}" style="font-size:13px;padding:5px 12px">${t.label}</button>
      `).join('')}
    </div>
    <div id="history-list"></div>
  `;

  el.querySelectorAll('.tab-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      _activeTab = btn.dataset.mode;
      render(el);
    });
  });

  await loadList(el);
}

async function loadList(el) {
  const list = el.querySelector('#history-list');
  list.innerHTML = '<div style="text-align:center;padding:40px"><div class="spinner"></div></div>';

  try {
    const url = _activeTab ? `/api/history/list?mode=${_activeTab}` : '/api/history/list';
    const data = await api.get(url);
    if (!data.sessions.length) {
      list.innerHTML = `<div class="alert alert-info">No records yet${_activeTab ? ' in this category' : ''}.</div>`;
      return;
    }
    list.innerHTML = data.sessions.map(s => sessionRow(s)).join('');

    // Wire up star buttons
    list.querySelectorAll('.star-btn').forEach(btn => {
      btn.addEventListener('click', async (e) => {
        e.stopPropagation();
        const sid = btn.dataset.sid;
        const r = await api.post(`/api/history/star/${sid}`, {});
        btn.textContent = r.starred ? '★' : '☆';
        btn.style.color = r.starred ? 'var(--yellow)' : 'var(--text-dim)';
        btn.dataset.starred = r.starred ? '1' : '0';
      });
    });

    // Wire up expand rows
    list.querySelectorAll('.history-row').forEach(row => {
      row.addEventListener('click', () => toggleDetail(row, list));
    });
  } catch (e) {
    if (e.message.includes('profile') || e.message.includes('Profile') || e.message.includes('No profile')) {
      list.innerHTML = `
        <div class="card" style="text-align:center;padding:40px">
          <div style="font-size:40px;margin-bottom:12px">⚙️</div>
          <h3 style="margin-bottom:8px">Setup Required</h3>
          <p style="color:var(--text-dim);margin-bottom:20px">Please complete the setup wizard before viewing History.</p>
          <button class="btn btn-primary" onclick="navigate('setup')">Go to Setup →</button>
        </div>`;
    } else {
      renderError(list, e.message, () => loadList(el));
    }
  }
}
async function toggleDetail(row, list) {
  const sid = row.dataset.sid;
  const existing = list.querySelector(`.detail-row[data-sid="${sid}"]`);
  if (existing) { existing.remove(); return; }

  const detail = document.createElement('div');
  detail.className = 'detail-row card';
  detail.dataset.sid = sid;
  detail.style.cssText = 'margin:-8px 0 12px;border-radius:0 0 10px 10px;padding:16px;border-top:none';
  detail.innerHTML = '<div style="text-align:center;padding:12px"><div class="spinner"></div></div>';
  row.after(detail);

  try {
    const d = await api.get(`/api/history/detail/${sid}`);
    let inner = `<div style="font-size:13px;color:var(--text-dim);margin-bottom:12px">
      ${fmtDate(d.started_at)} · ${d.duration_sec ? Math.round(d.duration_sec/60)+' min' : '—'} · ${d.items_done || 0} items · ${d.accuracy_pct}%
    </div>`;

    if (d.content && d.mode === 'chat') {
      inner += `<div style="max-height:320px;overflow-y:auto;display:flex;flex-direction:column;gap:8px;margin-bottom:12px">
        ${d.content.filter(m => m.role !== 'system').map(m => `
          <div class="msg msg-${m.role === 'assistant' ? 'ai' : 'user'}" style="max-width:85%">
            ${escHtml(m.content)}
          </div>`).join('')}
      </div>`;
    }

    inner += `<button class="btn btn-outline" data-del="${sid}" style="font-size:12px;color:var(--red);border-color:var(--red)">🗑 Delete</button>`;
    detail.innerHTML = inner;

    detail.querySelector(`[data-del]`).addEventListener('click', async () => {
      await fetch(`/api/history/${sid}`, { method: 'DELETE' });
      row.remove();
      detail.remove();
    });
  } catch (e) {
    detail.innerHTML = `<div class="alert alert-error">${e.message}</div>`;
  }
}

function sessionRow(s) {
  const date = fmtDate(s.started_at);
  const stats = s.mode === 'chat'
    ? `${s.items_done || 0} turns`
    : `${s.items_done || 0} items · ${s.accuracy_pct}%`;
  return `
    <div class="history-row card" data-sid="${s.session_id}"
      style="display:flex;align-items:center;gap:12px;padding:12px 16px;margin-bottom:8px;cursor:pointer">
      <span style="font-size:20px">${s.icon}</span>
      <div style="flex:1;min-width:0">
        <div style="font-weight:600;font-size:14px">${modeLabel(s.mode)}</div>
        <div style="font-size:12px;color:var(--text-dim)">${date} · ${stats}</div>
      </div>
      <button class="star-btn" data-sid="${s.session_id}" data-starred="${s.starred ? '1' : '0'}"
        style="background:none;border:none;font-size:18px;cursor:pointer;color:${s.starred ? 'var(--yellow)' : 'var(--text-dim)'}"
        title="${s.starred ? 'Unstar' : 'Star'}">${s.starred ? '★' : '☆'}</button>
      <span style="font-size:12px;color:var(--text-dim)">›</span>
    </div>`;
}

function modeLabel(mode) {
  return { vocab:'Vocabulary', grammar:'Grammar', reading:'Reading', writing:'Writing', chat:'Chat' }[mode] || mode;
}

function fmtDate(iso) {
  if (!iso) return '—';
  const d = new Date(iso);
  return `${d.getMonth()+1}/${d.getDate()} ${String(d.getHours()).padStart(2,'0')}:${String(d.getMinutes()).padStart(2,'0')}`;
}

function escHtml(s) {
  return String(s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}

