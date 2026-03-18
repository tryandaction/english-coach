// pages/mock-exam.js — Mock exam launcher with section progression

const MOCK_STATE_KEY = 'mock_exam_state';
const PRACTICE_KEY = 'practice_mode';

const _mockStore = {
  get: () => { try { return JSON.parse(sessionStorage.getItem(MOCK_STATE_KEY)); } catch { return null; } },
  set: (v) => { try { sessionStorage.setItem(MOCK_STATE_KEY, JSON.stringify(v)); } catch {} },
  clear: () => { try { sessionStorage.removeItem(MOCK_STATE_KEY); } catch {} },
};

let _timerId = null;

export async function render(el) {
  const saved = _mockStore.get();
  if (saved?.session_id) {
    await refreshSession(el, saved.session_id);
    return;
  }
  renderLauncher(el);
}

function renderLauncher(el) {
  el.innerHTML = `
    <h1>⏱ Mock Exam</h1>
    <p style="color:var(--text-dim)">启动一套连续 section 流的模考会话。当前版本会记录每个 section 的状态、继续进度和完成态。</p>

    <div class="card" style="padding:20px;margin-bottom:18px">
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:16px;align-items:start">
        <div>
          <div style="font-size:12px;font-weight:700;letter-spacing:.04em;color:var(--text-dim);margin-bottom:10px">EXAM</div>
          <div id="mock-exam-tabs" style="display:flex;gap:8px;flex-wrap:wrap">
            <button class="btn btn-primary mock-exam-tab" data-exam="toefl">TOEFL</button>
            <button class="btn btn-outline mock-exam-tab" data-exam="ielts">IELTS</button>
          </div>
        </div>
        <div>
          <div style="font-size:12px;font-weight:700;letter-spacing:.04em;color:var(--text-dim);margin-bottom:10px">SECTIONS</div>
          <div style="display:grid;grid-template-columns:repeat(2,minmax(120px,1fr));gap:10px">
            ${['reading', 'listening', 'speaking', 'writing'].map((section, index) => `
              <label class="card" style="padding:12px;display:flex;gap:10px;align-items:center;cursor:pointer">
                <input type="checkbox" class="mock-section" value="${section}" ${index < 2 ? 'checked' : ''}>
                <span style="text-transform:capitalize">${section}</span>
              </label>
            `).join('')}
          </div>
        </div>
      </div>

      <div style="margin-top:18px;display:flex;gap:10px;flex-wrap:wrap">
        <button class="btn btn-primary" id="btn-start-mock">Start Mock Exam</button>
        <button class="btn btn-outline" id="btn-go-practice">Go To Practice Mode</button>
      </div>
    </div>

    <div class="card" style="padding:18px">
      <h3 style="margin-top:0">This Round Includes</h3>
      <div style="display:flex;flex-wrap:wrap;gap:10px">
        <span class="tag">Section status</span>
        <span class="tag">Continue exam</span>
        <span class="tag">Completed view</span>
        <span class="tag">Current section handoff</span>
      </div>
      <p style="margin:14px 0 0 0;color:var(--text-dim)">本轮重点是打通更像模考的 section 流，而不是最终发布态的完整统分系统。</p>
    </div>
  `;

  let activeExam = 'toefl';
  el.querySelectorAll('.mock-exam-tab').forEach(btn => {
    btn.addEventListener('click', () => {
      activeExam = btn.dataset.exam;
      el.querySelectorAll('.mock-exam-tab').forEach(node => {
        node.className = `btn ${node === btn ? 'btn-primary' : 'btn-outline'} mock-exam-tab`;
      });
    });
  });

  el.querySelector('#btn-go-practice')?.addEventListener('click', () => navigate('practice'));
  el.querySelector('#btn-start-mock')?.addEventListener('click', async () => {
    const sections = Array.from(el.querySelectorAll('.mock-section:checked')).map(node => node.value);
    if (!sections.length) return;

    const btn = el.querySelector('#btn-start-mock');
    btn.disabled = true;
    btn.textContent = 'Starting...';

    try {
      const session = await api.post('/api/mock-exam/start', { exam: activeExam, sections });
      _mockStore.set(session);
      renderSessionView(el, session);
    } catch (e) {
      btn.disabled = false;
      btn.textContent = 'Start Mock Exam';
      const msg = document.createElement('div');
      msg.className = 'alert alert-error';
      msg.style.marginTop = '12px';
      msg.textContent = e.message;
      el.appendChild(msg);
    }
  });
}

function renderSessionView(el, session) {
  if (_timerId) clearInterval(_timerId);
  _mockStore.set(session);

  if (session.exam_complete) {
    renderCompletedView(el, session);
    return;
  }

  el.innerHTML = `
    <div style="display:flex;align-items:flex-start;justify-content:space-between;gap:16px;flex-wrap:wrap;margin-bottom:18px">
      <div>
        <h1 style="margin:0 0 6px 0">⏱ ${escHtml((session.exam || 'toefl').toUpperCase())} Mock Exam</h1>
        <p style="margin:0;color:var(--text-dim)">按顺序完成 section。当前会话会保存状态，你可以返回继续。</p>
      </div>
      <div style="display:flex;gap:10px;flex-wrap:wrap">
        <button class="btn btn-outline" id="btn-refresh-mock">Refresh</button>
        <button class="btn btn-outline" id="btn-reset-mock">Reset</button>
      </div>
    </div>

    <div class="stats-row" style="margin-bottom:18px">
      <div class="stat-badge"><div class="val">${session.total_sections || 0}</div><div class="lbl">Sections</div></div>
      <div class="stat-badge"><div class="val">${session.completed_sections || 0}</div><div class="lbl">Done</div></div>
      <div class="stat-badge"><div class="val">${session.total_time || 0}</div><div class="lbl">Minutes</div></div>
      <div class="stat-badge"><div class="val">${escHtml(String(session.current_section_name || '-').toUpperCase())}</div><div class="lbl">Current</div></div>
      <div class="stat-badge"><div class="val">${formatElapsed(session.elapsed_time || 0)}</div><div class="lbl">Elapsed</div></div>
    </div>

    <div class="card" style="padding:18px;margin-bottom:18px">
      <h3 style="margin-top:0">Instructions</h3>
      <pre style="white-space:pre-wrap;font-family:inherit;color:var(--text-dim);margin:0">${escHtml(session.instructions || '')}</pre>
    </div>

    <div class="card" style="padding:18px">
      <h3 style="margin-top:0">Section Flow</h3>
      <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:12px">
        ${(session.sections || []).map((section, index) => `
          <div class="card" style="padding:14px;background:var(--bg2)">
            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px">
              <strong style="text-transform:capitalize">${escHtml(section.name)}</strong>
              <span class="tag">${section.status.toUpperCase()}</span>
            </div>
            <div style="font-size:13px;color:var(--text-dim)">Time Limit: ${section.time_limit} min</div>
            <div style="font-size:13px;color:var(--text-dim)">Items: ${section.item_count || 0}</div>
            ${section.summary ? renderSectionSummary(section.summary) : ''}
            <div style="margin-top:12px">
              ${renderSectionAction(section, index)}
            </div>
          </div>
        `).join('')}
      </div>
    </div>
  `;

  el.querySelector('#btn-refresh-mock')?.addEventListener('click', () => refreshSession(el, session.session_id));
  el.querySelector('#btn-reset-mock')?.addEventListener('click', () => {
    _mockStore.clear();
    if (_timerId) clearInterval(_timerId);
    renderLauncher(el);
  });

  el.querySelectorAll('[data-open-section]').forEach(btn => {
    btn.addEventListener('click', () => {
      openSection(session, btn.dataset.openSection, Number(btn.dataset.index));
    });
  });

  _timerId = setInterval(() => refreshSession(el, session.session_id), 5000);
}

function renderCompletedView(el, session) {
  const report = session.report || {};
  el.innerHTML = `
    <div class="card" style="padding:24px;text-align:center">
      <div style="font-size:52px;margin-bottom:10px">✅</div>
      <h2 style="margin:0 0 8px 0">${escHtml((session.exam || 'toefl').toUpperCase())} Mock Complete</h2>
      <p style="color:var(--text-dim)">本轮模考 section 流已完成。当前报告用于帮助你定位下一步训练重点，不应当作正式标准化成绩单。</p>
      <div style="display:flex;gap:12px;justify-content:center;flex-wrap:wrap;margin:18px 0">
        <span class="tag">Score ${escHtml(report.overall_score || 'N/A')}</span>
        <span class="tag">Accuracy ${escHtml(String(report.overall_accuracy ?? 'N/A'))}%</span>
        <span class="tag">Time ${formatElapsed(report.total_time || session.elapsed_time || 0)}</span>
      </div>
      <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:12px;margin:20px 0;text-align:left">
        ${(report.section_scores || []).map(item => `
          <div class="card" style="padding:14px;background:var(--bg2)">
            <div style="display:flex;justify-content:space-between;gap:8px;align-items:center;margin-bottom:8px">
              <strong style="text-transform:capitalize">${escHtml(item.section)}</strong>
              <span class="tag">${item.accuracy}%</span>
            </div>
            <div style="font-size:13px;color:var(--text-dim)">Correct: ${item.correct} / ${item.total}</div>
            <div style="font-size:13px;color:var(--text-dim)">Time: ${formatElapsed(item.time_taken || 0)}</div>
          </div>
        `).join('') || '<div class="alert alert-info">当前还没有可展示的 section 评分明细。</div>'}
      </div>
      ${(report.recommendations || []).length
        ? `<div class="card" style="padding:16px;text-align:left;background:var(--bg2)">
            <strong style="display:block;margin-bottom:8px">Recommendations</strong>
            ${(report.recommendations || []).map(item => `<div style="font-size:13px;color:var(--text-dim);margin-bottom:6px">• ${escHtml(item)}</div>`).join('')}
          </div>`
        : ''}
      <div class="card" style="padding:16px;text-align:left;background:var(--bg2);margin-top:14px">
        <strong style="display:block;margin-bottom:8px">Next Step</strong>
        <div style="font-size:13px;color:var(--text-dim);line-height:1.7">${escHtml(mockNextStep(report))}</div>
      </div>
      <div style="display:flex;gap:10px;justify-content:center;flex-wrap:wrap;margin-top:20px">
        <button class="btn btn-primary" id="btn-start-new-mock">Start New Mock</button>
        <button class="btn btn-outline" onclick="navigate('practice')">← Practice</button>
      </div>
    </div>
  `;

  el.querySelector('#btn-start-new-mock')?.addEventListener('click', () => {
    _mockStore.clear();
    renderLauncher(el);
  });
}

function renderSectionSummary(summary) {
  const correct = summary.correct ?? null;
  const total = summary.total ?? null;
  if (correct === null || total === null) return '';
  return `<div style="font-size:12px;color:var(--text-dim);margin-top:8px">Result: ${correct} / ${total}</div>`;
}

function renderSectionAction(section, index) {
  if (section.status === 'done') {
    return '<button class="btn btn-outline" style="width:100%;justify-content:center" disabled>Completed</button>';
  }
  if (!section.available || section.status === 'locked') {
    return '<button class="btn btn-outline" style="width:100%;justify-content:center" disabled>Locked</button>';
  }
  return `<button class="btn btn-primary" data-open-section="${section.name}" data-index="${index}" style="width:100%;justify-content:center">Continue Section</button>`;
}

async function refreshSession(el, sessionId) {
  try {
    const session = await api.get(`/api/mock-exam/session/${sessionId}`);
    renderSessionView(el, session);
  } catch {
    _mockStore.clear();
    renderLauncher(el);
  }
}

function openSection(session, section, index) {
  sessionStorage.setItem(PRACTICE_KEY, JSON.stringify({
    source: 'mock_exam',
    section,
    exam: session.exam,
    started_at: Date.now(),
    mock_session_id: session.session_id,
    mock_section_index: index,
  }));
  navigate(section);
}

function formatElapsed(seconds) {
  if (seconds < 60) return `${seconds}s`;
  const mins = Math.floor(seconds / 60);
  const secs = seconds % 60;
  return `${mins}m ${secs}s`;
}

function mockNextStep(report) {
  const weak = (report.weak_areas || [])[0];
  if (weak) {
    return `先回到 Practice 里针对 ${weak} 做专项训练，再开始下一轮 mock，会比直接重复整套模考更高效。`;
  }
  return '当前模考没有暴露出明显单点短板，下一轮建议优先优化时间分配，再观察 section 间波动。';
}

function escHtml(s) {
  return String(s || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}
