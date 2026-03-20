// pages/practice.js — Practice catalog with coach context

let _profile = {};
let _catalog = null;
let _coach = {};
let _activeExam = 'toefl';

export async function render(el) {
  _profile = {};
  _catalog = null;
  _coach = {};

  try {
    [_profile, _catalog, _coach] = await Promise.all([
      api.get('/api/progress').catch(() => ({})),
      api.get('/api/practice/catalog').catch(() => null),
      api.get('/api/coach/status').catch(() => ({})),
    ]);
    if (window._currentAbortSignal?.aborted || !el.isConnected) return;
  } catch (e) {
    if (e.name === 'AbortError' || !el.isConnected) return;
  }

  _activeExam = (_profile.target_exam || _catalog?.active_exam || 'toefl').toLowerCase();
  if (!['toefl', 'ielts'].includes(_activeExam)) _activeExam = 'toefl';

  renderPracticeShell(el);
  bindPracticeEvents(el);
}

function renderPracticeShell(el) {
  const examData = _catalog?.exams?.[_activeExam] || { sections: {} };
  const coachTask = getCoachTaskContext();
  const planTasks = ((_coach.plan || {}).tasks || []).filter(task => ['reading', 'listening', 'writing', 'speaking'].includes(task.route_page));

  el.innerHTML = `
    <div style="display:flex;align-items:flex-start;justify-content:space-between;gap:16px;flex-wrap:wrap;margin-bottom:18px">
      <div>
        <h1 style="margin:0 0 6px 0">🎯 Practice Mode</h1>
        <p style="margin:0;color:var(--text-dim)">按考试和题型进入专项训练。当前页面会明确告诉你哪些能直接练、哪些需要 AI、哪些还没打通。</p>
      </div>
      <button class="btn btn-outline" id="btn-go-mock">⏱ Mock Exam</button>
    </div>

    ${coachTask ? renderCoachBanner(coachTask) : ''}
    ${planTasks.length ? renderCoachPlanStrip(planTasks) : ''}

    <div class="card" style="margin-bottom:18px;padding:16px">
      <div style="display:flex;justify-content:space-between;gap:16px;align-items:flex-start;flex-wrap:wrap">
        <div>
          <div style="font-size:12px;font-weight:700;letter-spacing:.04em;color:var(--text-dim);margin-bottom:10px">EXAM</div>
          <div id="practice-exam-tabs" style="display:flex;gap:8px;flex-wrap:wrap">
            ${['toefl', 'ielts'].map(exam => `
              <button class="btn ${exam === _activeExam ? 'btn-primary' : 'btn-outline'} practice-exam-tab"
                data-exam="${exam}" style="font-size:13px;padding:6px 14px">${exam.toUpperCase()}</button>
            `).join('')}
          </div>
          <div style="font-size:12px;color:var(--text-dim);margin-top:10px">
            当前目标考试：${((_profile.target_exam || 'general').toUpperCase())} · 当前 CEFR：${_profile.cefr_level || 'B2'}
          </div>
        </div>
        <div style="display:flex;gap:8px;flex-wrap:wrap">
          ${legendItem('direct', '可直接练')}
          ${legendItem('needs_ai', '需 AI')}
          ${legendItem('construction', '建设中')}
        </div>
      </div>
      ${examData.reading_ready === false
        ? `<div class="alert alert-info" style="margin-top:12px">当前考试的阅读素材不足，系统会优先尝试 AI 生成；若无 AI，将保留建设中状态。</div>`
        : ''}
    </div>

    <style>
      .type-card-badge {
        display:inline-block;
        font-size:10px;
        font-weight:700;
        padding:3px 7px;
        border-radius:999px;
        background:var(--bg3);
        border:1px solid var(--border);
      }
      .badge-direct { color:var(--green); border-color:var(--green); }
      .badge-needs_ai { color:var(--yellow); border-color:var(--yellow); }
      .badge-construction { color:var(--text-dim); }
    </style>

    <div class="practice-selector">
      ${sectionCard('Reading', '支持按题型进入专项训练，并在无 AI 时尽量开放离线可练部分。', examData.sections?.reading || [])}
      ${sectionCard('Listening', '会优先按题型命中内置素材；命不中时，再回退到同类对话或讲座。', examData.sections?.listening || [])}
      ${sectionCard('Writing', '写作题面可直接练；若 AI 已配置，可进一步获得反馈闭环。', examData.sections?.writing || [])}
      ${sectionCard('Speaking', '口语任务可直接练；若 AI 已配置，可进一步获得评分反馈。', examData.sections?.speaking || [])}
    </div>
  `;
}

function renderCoachBanner(task) {
  return `
    <div class="card" style="margin-bottom:18px;border-color:var(--accent)">
      <div style="display:flex;justify-content:space-between;gap:12px;align-items:flex-start;flex-wrap:wrap">
        <div>
          <div style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:8px">
            <span class="tag">${categoryLabel(task.category)}</span>
            <span class="tag">${task.state === 'done' ? '已完成' : '待执行'}</span>
          </div>
          <h3 style="margin:0 0 6px 0">${escHtml(task.title || '当前 coach 任务')}</h3>
          <div style="font-size:13px;color:var(--text-dim);line-height:1.6">${escHtml(task.reason || task.description || '')}</div>
        </div>
        <button class="btn btn-outline" id="btn-clear-coach-task">清除上下文</button>
      </div>
    </div>
  `;
}

function renderCoachPlanStrip(tasks) {
  return `
    <div class="card" style="margin-bottom:18px;background:var(--bg2)">
      <div style="display:flex;justify-content:space-between;gap:12px;align-items:center;margin-bottom:10px">
        <strong>今日 coach 推荐</strong>
        <span style="font-size:12px;color:var(--text-dim)">点击后会把任务上下文带入专项页</span>
      </div>
      <div style="display:flex;gap:10px;flex-wrap:wrap">
        ${tasks.map(task => `
          <button class="btn btn-outline coach-task-btn" data-task="${escAttr(JSON.stringify(task))}" style="justify-content:flex-start">
            ${escHtml(task.title)} · ${categoryLabel(task.category)}
          </button>
        `).join('')}
      </div>
    </div>
  `;
}

function sectionCard(title, desc, items) {
  return `
    <div class="card" style="margin-bottom:18px">
      <h2 style="margin:0 0 6px 0">${title}</h2>
      <p style="margin:0 0 14px 0;color:var(--text-dim);font-size:13px">${desc}</p>
      <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:12px">
        ${items.map(renderTypeCard).join('') || '<div class="alert alert-info">暂无配置</div>'}
      </div>
    </div>
  `;
}

function renderTypeCard(item) {
  const unavailable = item.available ? '' : 'unavailable';
  const stateClass = `state-${item.mode}`;
  const stateLabel = item.mode === 'direct' ? '可直接练' : item.mode === 'needs_ai' ? '需 AI' : '建设中';
  const badgeClass = item.mode === 'direct' ? 'badge-direct' : item.mode === 'needs_ai' ? 'badge-needs_ai' : 'badge-construction';
  return `
    <div class="type-card ${stateClass} ${unavailable}"
         data-section="${item.section}"
         data-type="${item.id}"
         data-exam="${_activeExam}"
         data-available="${item.available ? '1' : '0'}"
         style="background:var(--bg);border:1px solid var(--border);border-radius:12px;padding:14px;cursor:${item.available ? 'pointer' : 'not-allowed'};opacity:${item.available ? 1 : 0.62}">
      <div style="font-weight:700;margin-bottom:6px;font-size:14px">${item.name}</div>
      <div style="font-size:12px;color:var(--text-dim);line-height:1.45;min-height:34px">${item.description}</div>
      <div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin-top:10px">
        <span class="type-card-badge ${badgeClass}">${stateLabel}</span>
        ${item.badge ? `<span class="type-card-badge">${item.badge}</span>` : ''}
      </div>
      <div style="margin-top:10px;font-size:11px;color:var(--text-dim);line-height:1.45">${item.reason || ''}</div>
    </div>
  `;
}

function legendItem(mode, label) {
  const cls = mode === 'direct' ? 'badge-direct' : mode === 'needs_ai' ? 'badge-needs_ai' : 'badge-construction';
  return `<span class="type-card-badge ${cls}">${label}</span>`;
}

function bindPracticeEvents(el) {
  el.querySelector('#btn-go-mock')?.addEventListener('click', () => navigate('mock-exam'));
  el.querySelector('#btn-clear-coach-task')?.addEventListener('click', () => {
    sessionStorage.removeItem('coach_task_context');
    render(el);
  });
  el.querySelectorAll('.coach-task-btn[data-task]').forEach(btn => {
    btn.addEventListener('click', () => {
      const task = parseTask(btn.dataset.task);
      if (!task) return;
      sessionStorage.setItem('coach_task_context', JSON.stringify(task));
      if (['reading', 'listening', 'writing', 'speaking'].includes(task.route_page)) {
        sessionStorage.setItem('practice_mode', JSON.stringify({
          section: task.route_page,
          type: task.task_type || null,
          exam: task.exam || 'general',
          started_at: Date.now(),
          source: 'coach_plan',
          task_key: task.task_key || '',
          category: task.category || '',
        }));
        navigate(task.route_page);
        return;
      }
      navigate(task.route_page || 'practice');
    });
  });
  el.querySelectorAll('.practice-exam-tab').forEach(btn => {
    btn.addEventListener('click', () => {
      _activeExam = btn.dataset.exam;
      renderPracticeShell(el);
      bindPracticeEvents(el);
    });
  });
  el.querySelectorAll('.type-card').forEach(card => {
    card.addEventListener('click', () => {
      if (card.dataset.available !== '1') return;
      startPractice(card.dataset.section, card.dataset.type, card.dataset.exam);
    });
  });
}

function startPractice(section, type, exam) {
  const task = getCoachTaskContext();
  sessionStorage.setItem('practice_mode', JSON.stringify({
    section,
    type,
    exam,
    started_at: Date.now(),
    source: task ? 'coach_plan' : 'practice',
    task_key: task?.task_key || '',
    category: task?.category || '',
  }));
  navigate(section);
}

function getCoachTaskContext() {
  try { return JSON.parse(sessionStorage.getItem('coach_task_context')); } catch { return null; }
}

function parseTask(value) {
  try { return JSON.parse(value); } catch { return null; }
}

function categoryLabel(category) {
  return { core: '核心', growth: '成长', sprint: '冲刺', ai_enhanced: 'AI 增强' }[category] || category || '任务';
}

function escAttr(value) {
  return escHtml(value).replace(/"/g, '&quot;');
}

function escHtml(value) {
  return String(value || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}
