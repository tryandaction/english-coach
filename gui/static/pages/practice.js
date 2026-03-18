// pages/practice.js — Practice catalog with real capability states

let _profile = {};
let _catalog = null;
let _activeExam = 'toefl';

export async function render(el) {
  _profile = {};
  _catalog = null;

  try {
    [_profile, _catalog] = await Promise.all([
      api.get('/api/progress').catch(() => ({})),
      api.get('/api/practice/catalog').catch(() => null),
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

  el.innerHTML = `
    <div style="display:flex;align-items:flex-start;justify-content:space-between;gap:16px;flex-wrap:wrap;margin-bottom:18px">
      <div>
        <h1 style="margin:0 0 6px 0">🎯 Practice Mode</h1>
        <p style="margin:0;color:var(--text-dim)">按考试和题型进入专项训练。当前页面会明确告诉你哪些能直接练、哪些需要 AI、哪些还没打通。</p>
      </div>
      <button class="btn btn-outline" id="btn-go-mock">⏱ Mock Exam</button>
    </div>

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

    <div id="practice-sections">${renderSections(examData.sections || {})}</div>

    <style>
      .practice-selector {
        display: flex;
        flex-direction: column;
        gap: 18px;
      }
      .section-card {
        background: var(--bg2);
        border: 1px solid var(--border);
        border-radius: 12px;
        padding: 18px;
      }
      .section-card h2 {
        margin: 0 0 6px 0;
        font-size: 18px;
      }
      .section-card p {
        margin: 0 0 14px 0;
        color: var(--text-dim);
        font-size: 13px;
      }
      .question-type-grid {
        display: grid;
        grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
        gap: 12px;
      }
      .type-card {
        background: var(--bg);
        border: 1px solid var(--border);
        border-radius: 12px;
        padding: 14px;
        cursor: pointer;
        transition: transform .18s, border-color .18s;
      }
      .type-card:hover {
        border-color: var(--accent);
        transform: translateY(-2px);
      }
      .type-card.state-direct {
        border-color: rgba(57, 181, 74, .35);
      }
      .type-card.state-needs_ai {
        border-color: rgba(255, 176, 32, .35);
      }
      .type-card.state-construction {
        border-style: dashed;
      }
      .type-card.unavailable {
        opacity: .62;
        cursor: not-allowed;
      }
      .type-card.unavailable:hover {
        transform: none;
        border-color: var(--border);
      }
      .type-card-title {
        font-weight: 700;
        margin-bottom: 6px;
        font-size: 14px;
      }
      .type-card-desc {
        font-size: 12px;
        color: var(--text-dim);
        line-height: 1.45;
        min-height: 34px;
      }
      .type-card-meta {
        display: flex;
        gap: 8px;
        align-items: center;
        flex-wrap: wrap;
        margin-top: 10px;
      }
      .type-card-badge {
        display: inline-block;
        font-size: 10px;
        font-weight: 700;
        padding: 3px 7px;
        border-radius: 999px;
        background: var(--bg3);
        border: 1px solid var(--border);
      }
      .type-card-badge.badge-direct {
        color: var(--green);
        border-color: var(--green);
      }
      .type-card-badge.badge-needs_ai {
        color: var(--yellow);
        border-color: var(--yellow);
      }
      .type-card-badge.badge-construction {
        color: var(--text-dim);
      }
      .type-card-reason {
        margin-top: 10px;
        font-size: 11px;
        color: var(--text-dim);
        line-height: 1.45;
      }
    </style>
  `;
}

function renderSections(sections) {
  return `
    <div class="practice-selector">
      ${sectionCard('Reading', '支持按题型进入专项训练，并在无 AI 时尽量开放离线可练部分。', sections.reading || [])}
      ${sectionCard('Listening', '当前重点是保留真实听力页，按题型精确专项仍在建设。', sections.listening || [])}
      ${sectionCard('Writing', '写作题面可直接练；若 AI 已配置，可进一步获得反馈闭环。', sections.writing || [])}
      ${sectionCard('Speaking', '口语任务可直接练；若 AI 已配置，可进一步获得评分反馈。', sections.speaking || [])}
    </div>
  `;
}

function sectionCard(title, desc, items) {
  return `
    <div class="section-card">
      <h2>${title}</h2>
      <p>${desc}</p>
      <div class="question-type-grid">
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
         data-available="${item.available ? '1' : '0'}">
      <div class="type-card-title">${item.name}</div>
      <div class="type-card-desc">${item.description}</div>
      <div class="type-card-meta">
        <span class="type-card-badge ${badgeClass}">${stateLabel}</span>
        ${item.badge ? `<span class="type-card-badge">${item.badge}</span>` : ''}
      </div>
      <div class="type-card-reason">${item.reason || ''}</div>
    </div>
  `;
}

function legendItem(mode, label) {
  const cls = mode === 'direct' ? 'badge-direct' : mode === 'needs_ai' ? 'badge-needs_ai' : 'badge-construction';
  return `<span class="type-card-badge ${cls}">${label}</span>`;
}

function bindPracticeEvents(el) {
  el.querySelector('#btn-go-mock')?.addEventListener('click', () => navigate('mock-exam'));

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
  sessionStorage.setItem('practice_mode', JSON.stringify({
    section,
    type,
    exam,
    started_at: Date.now(),
  }));
  navigate(section);
}
