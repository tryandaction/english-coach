// pages/mock-exam.js — Mock exam launcher with coach recommendation

const MOCK_STATE_KEY = 'mock_exam_state';
const PRACTICE_KEY = 'practice_mode';

const _mockStore = {
  get: () => { try { return JSON.parse(sessionStorage.getItem(MOCK_STATE_KEY)); } catch { return null; } },
  set: (v) => { try { sessionStorage.setItem(MOCK_STATE_KEY, JSON.stringify(v)); } catch {} },
  clear: () => { try { sessionStorage.removeItem(MOCK_STATE_KEY); } catch {} },
};

let _timerId = null;

function clearMockTimer() {
  if (_timerId) {
    clearInterval(_timerId);
    _timerId = null;
  }
}

export async function render(el) {
  clearMockTimer();
  const saved = _mockStore.get();
  if (saved?.session_id) {
    await refreshSession(el, saved.session_id);
    return;
  }
  const coach = await api.get('/api/coach/status').catch(() => ({}));
  renderLauncher(el, coach);
}

function renderLauncher(el, coach) {
  const coachTask = ((coach.plan || {}).tasks || []).find(task => task.route_page === 'mock-exam');
  const contextTask = getCoachTaskContext();
  const activeTask = coachTask || contextTask;
  const preferredExam = activeTask?.exam || 'toefl';
  const preferredSection = activeTask?.recommended_section || null;
  el.innerHTML = `
    <h1>⏱ Mock Exam</h1>
    <p style="color:var(--text-dim)">启动一套连续 section 流的模考会话。只选 1 个 section 时会直接打开；多 section 时会保留顺序和继续进度。</p>

    ${renderCoachHint(coachTask || contextTask, coach)}

    <div class="card" style="padding:20px;margin-bottom:18px">
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:16px;align-items:start">
        <div>
          <div style="font-size:12px;font-weight:700;letter-spacing:.04em;color:var(--text-dim);margin-bottom:10px">EXAM</div>
          <div id="mock-exam-tabs" style="display:flex;gap:8px;flex-wrap:wrap">
            <button class="btn ${preferredExam === 'toefl' ? 'btn-primary' : 'btn-outline'} mock-exam-tab" data-exam="toefl">TOEFL</button>
            <button class="btn ${preferredExam === 'ielts' ? 'btn-primary' : 'btn-outline'} mock-exam-tab" data-exam="ielts">IELTS</button>
          </div>
        </div>
        <div>
          <div style="font-size:12px;font-weight:700;letter-spacing:.04em;color:var(--text-dim);margin-bottom:10px">SECTIONS</div>
          <div style="display:grid;grid-template-columns:repeat(2,minmax(120px,1fr));gap:10px">
            ${['reading', 'listening', 'speaking', 'writing'].map((section, index) => `
              <label class="card" style="padding:12px;display:flex;gap:10px;align-items:center;cursor:pointer">
                <input type="checkbox" class="mock-section" value="${section}" ${(preferredSection ? preferredSection === section : index < 2) ? 'checked' : ''}>
                <span style="text-transform:capitalize">${section}</span>
              </label>
            `).join('')}
          </div>
        </div>
        <div>
          <div style="font-size:12px;font-weight:700;letter-spacing:.04em;color:var(--text-dim);margin-bottom:10px">START WITH</div>
          <select id="mock-start-section"
            style="width:100%;padding:10px 12px;background:var(--bg);color:var(--text);border:1px solid var(--border);border-radius:10px">
          </select>
        </div>
      </div>

      <div style="margin-top:18px;display:flex;gap:10px;flex-wrap:wrap">
        <button class="btn btn-primary" id="btn-start-mock">${preferredSection ? 'Start Recommended Section' : 'Start Mock Exam'}</button>
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

  let activeExam = preferredExam;
  const refreshStartSectionSelect = () => {
    const selected = Array.from(el.querySelectorAll('.mock-section:checked')).map(node => node.value);
    const select = el.querySelector('#mock-start-section');
    if (!select) return;
    select.innerHTML = selected.map(section => `
      <option value="${section}" ${preferredSection === section ? 'selected' : ''}>${section.toUpperCase()}</option>
    `).join('');
    if (!select.value && selected.length) select.value = selected[0];
  };

  el.querySelectorAll('.mock-exam-tab').forEach(btn => {
    btn.addEventListener('click', () => {
      activeExam = btn.dataset.exam;
      el.querySelectorAll('.mock-exam-tab').forEach(node => {
        node.className = `btn ${node === btn ? 'btn-primary' : 'btn-outline'} mock-exam-tab`;
      });
    });
  });
  el.querySelectorAll('.mock-section').forEach(node => {
    node.addEventListener('change', refreshStartSectionSelect);
  });
  refreshStartSectionSelect();

  el.querySelector('#btn-go-practice')?.addEventListener('click', () => navigate('practice'));
  el.querySelector('#btn-start-mock')?.addEventListener('click', async () => {
    const sections = Array.from(el.querySelectorAll('.mock-section:checked')).map(node => node.value);
    if (!sections.length) return;
    const startWith = el.querySelector('#mock-start-section')?.value || sections[0];
    const orderedSections = [startWith, ...sections.filter(section => section !== startWith)];
    const btn = el.querySelector('#btn-start-mock');
    btn.disabled = true;
    btn.textContent = 'Starting...';
    try {
      const session = await api.post('/api/mock-exam/start', { exam: activeExam, sections: orderedSections });
      _mockStore.set(session);
      if (orderedSections.length === 1) {
        openSection(session, orderedSections[0], 0);
        return;
      }
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

function renderCoachHint(task, coach) {
  if (task) {
    return `
      <div class="card" style="padding:16px;margin-bottom:18px;border-color:var(--accent)">
        <div style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:8px">
          <span class="tag">${task.category === 'sprint' ? '冲刺内容' : 'Coach 推荐'}</span>
          <span class="tag">${task.state === 'done' ? '已完成' : '待执行'}</span>
        </div>
        <div style="font-size:14px;font-weight:600;margin-bottom:6px">${escHtml(task.title || '今天建议做 1 个 mock section')}</div>
        <div style="font-size:13px;color:var(--text-dim);line-height:1.6">${escHtml(task.reason || task.description || '')}</div>
      </div>
    `;
  }
  return `
    <div class="card" style="padding:16px;margin-bottom:18px;background:var(--bg2)">
      <div style="font-size:13px;color:var(--text-dim);line-height:1.7">
        ${coach.stage === 'sprint'
          ? '你当前处于冲刺阶段，但今天的计划没有优先推荐 mock，建议先回去完成更高优先级的修复任务。'
          : '今天没有把 Mock Exam 作为主任务推荐。更适合先做轻量任务，等进入冲刺阶段再提高 mock 权重。'}
      </div>
    </div>
  `;
}

function renderSessionView(el, session) {
  clearMockTimer();
  _mockStore.set(session);
  if (session.exam_complete) {
    renderCompletedView(el, session);
    return;
  }

  el.innerHTML = `
    <div data-mock-session-root="1">
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
            <div style="margin-top:12px">${renderSectionAction(section, index)}</div>
          </div>
        `).join('')}
      </div>
    </div>
    </div>
  `;

  el.querySelector('#btn-refresh-mock')?.addEventListener('click', () => refreshSession(el, session.session_id));
  el.querySelector('#btn-reset-mock')?.addEventListener('click', () => {
    _mockStore.clear();
    if (_timerId) clearInterval(_timerId);
    render(el);
  });
  el.querySelectorAll('[data-open-section]').forEach(btn => {
    btn.addEventListener('click', () => openSection(session, btn.dataset.openSection, Number(btn.dataset.index)));
  });
  _timerId = setInterval(() => {
    if (!el.isConnected || !el.querySelector('[data-mock-session-root="1"]')) {
      clearMockTimer();
      return;
    }
    refreshSession(el, session.session_id);
  }, 5000);
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
      <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:12px;margin:0 0 20px 0;text-align:left">
        <div class="card" style="padding:14px;background:var(--bg2)">
          <div style="font-size:12px;font-weight:700;letter-spacing:.04em;color:var(--text-dim);margin-bottom:8px">这次做了什么</div>
          <div style="font-size:13px;color:var(--text-dim);line-height:1.7">${escHtml(report.result_card || '本轮模考已完成。')}</div>
        </div>
        <div class="card" style="padding:14px;background:var(--bg2)">
          <div style="font-size:12px;font-weight:700;letter-spacing:.04em;color:var(--text-dim);margin-bottom:8px">哪一点进步了</div>
          <div style="font-size:13px;color:var(--text-dim);line-height:1.7">${escHtml(report.improved_point || '整套 section 已经能完整跑通。')}</div>
        </div>
        <div class="card" style="padding:14px;background:var(--bg2)">
          <div style="font-size:12px;font-weight:700;letter-spacing:.04em;color:var(--text-dim);margin-bottom:8px">明天为什么回来</div>
          <div style="font-size:13px;color:var(--text-dim);line-height:1.7">${escHtml(report.tomorrow_reason || mockNextStep(report))}</div>
        </div>
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
      ${(report.recommendations || []).length ? `
        <div class="card" style="padding:16px;text-align:left;background:var(--bg2)">
          <strong style="display:block;margin-bottom:8px">Recommendations</strong>
          ${(report.recommendations || []).map(item => `<div style="font-size:13px;color:var(--text-dim);margin-bottom:6px">• ${escHtml(item)}</div>`).join('')}
        </div>` : ''}
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
    sessionStorage.removeItem('coach_task_context');
    render(el);
  });
}

function renderSectionSummary(summary) {
  const correct = summary.correct ?? null;
  const total = summary.total ?? null;
  const rows = [];
  if (correct !== null && total !== null) rows.push(`<div style="font-size:12px;color:var(--text-dim);margin-top:8px">Result: ${correct} / ${total}</div>`);
  if (summary.result_card) rows.push(`<div style="font-size:12px;color:var(--text-dim);line-height:1.6;margin-top:6px">${escHtml(summary.result_card)}</div>`);
  if (summary.improved_point) rows.push(`<div style="font-size:12px;color:var(--text-dim);line-height:1.6;margin-top:6px">进步点：${escHtml(summary.improved_point)}</div>`);
  if (summary.tomorrow_reason) rows.push(`<div style="font-size:12px;color:var(--text-dim);line-height:1.6;margin-top:6px">明天：${escHtml(summary.tomorrow_reason)}</div>`);
  return rows.join('');
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
    render(el);
  }
}

function openSection(session, section, index) {
  clearMockTimer();
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

function getCoachTaskContext() {
  try { return JSON.parse(sessionStorage.getItem('coach_task_context')); } catch { return null; }
}

function formatElapsed(seconds) {
  if (seconds < 60) return `${seconds}s`;
  const mins = Math.floor(seconds / 60);
  const secs = seconds % 60;
  return `${mins}m ${secs}s`;
}

function mockNextStep(report) {
  if (report.tomorrow_reason) return report.tomorrow_reason;
  const weak = (report.weak_areas || [])[0];
  if (weak) {
    return `先回到 Practice 里针对 ${weak} 做专项训练，再开始下一轮 mock，会比直接重复整套模考更高效。`;
  }
  return '当前模考没有暴露出明显单点短板，下一轮建议优先优化时间分配，再观察 section 间波动。';
}

function escHtml(value) {
  return String(value || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}
